"""
Executor service — Story 3.4: Error Handling, Page Load Timeouts, and CAPTCHA Pause.

Per-session execution loop that creates a PlaywrightComputer browser,
builds a per-session LlmAgent + ADK Runner, and drives the agent through
the step plan, handling barge-in and per-step error retry logic.

SSE events emitted by this module:
  - task_paused      : BargeInException caught mid-execution
  - step_error       : Step fails after 2 retries (exhausted) — waits for user input before continuing
  - task_failed      : Unrecoverable executor error (Gemini API exhausted, input wait timeout)
  - awaiting_input   : CAPTCHA detected or step failed — execution paused for user input
"""
import asyncio
import base64
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from google.api_core import exceptions as gapi_exceptions
from google.genai import types as genai_types
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from agents.executor_agent import build_executor_context
from handlers.audit_writer import write_audit_log
from prompts.executor_system import EXECUTOR_SYSTEM_PROMPT
from services.gcs_service import upload_screenshot
from services.input_queue_service import clear_input_queue, get_input_queue
from services.session_service import update_session_status
from services.sse_service import emit_event
from services.task_complete_service import handle_task_complete
from tools.playwright_computer import BargeInException, PlaywrightComputer

logger = logging.getLogger(__name__)

_APP_NAME = "aria_executor"
_MAX_STEP_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.3
_GEMINI_MAX_RETRIES = 2
_GEMINI_BACKOFF_SECONDS = 1.0
_INPUT_WAIT_TIMEOUT_SECONDS = 300.0


async def _wait_for_user_input(
    session_id: str,
    step_index: int,
    paused_with: str = "step_error",
    step_description: str = "",
) -> str | None:
    """
    Wait for the user to deliver input via the per-session queue.

    The caller is responsible for emitting any "paused" SSE event (awaiting_input,
    step_error, etc.) BEFORE calling this function.

    Returns the user-provided string, or None on timeout (after emitting task_failed).
    """
    input_queue = get_input_queue(session_id)
    try:
        user_input = await asyncio.wait_for(
            input_queue.get(), timeout=_INPUT_WAIT_TIMEOUT_SECONDS
        )
        logger.info(
            "Received user input for session %s at step %d (paused_with=%s): %s",
            session_id,
            step_index,
            paused_with,
            user_input,
        )
        return user_input
    except asyncio.TimeoutError:
        logger.error(
            "Input wait timeout for session %s step %d (paused_with=%s)",
            session_id,
            step_index,
            paused_with,
        )
        emit_event(
            session_id,
            "task_failed",
            {"reason": f"Input wait timeout after {paused_with}"},
        )
        try:
            await update_session_status(session_id, "failed")
        except Exception:
            logger.warning("Failed to update session %s status to 'failed'", session_id)
        return None


async def run_executor(session_id: str, step_plan: dict) -> None:
    """
    Per-session executor loop.

    Creates a dedicated PlaywrightComputer for the session, builds a per-session
    LlmAgent (NOT the module-level placeholder in executor_agent.py), and runs
    the agent through each step in step_plan using the ADK Runner.

    Retry logic (AC: 6):
      - Each step is attempted up to 3 times (_MAX_STEP_ATTEMPTS).
      - On BargeInException: immediately emit task_paused SSE and return.
      - On other exception: retry with _RETRY_DELAY_SECONDS delay.
      - After exhausting retries: emit step_error SSE and return.

    Cleanup:
      - pc.stop() is ALWAYS called in the finally block, even on exception.
      - handle_task_complete is called only on full success (all steps executed).

    Args:
        session_id: The active Firestore session ID (e.g. "sess_<uuid>").
        step_plan: Validated canonical step plan dict from the Planner.
    """
    pc = PlaywrightComputer(session_id=session_id)
    await pc.start()

    completed_steps: list[dict] = []
    current_step_index: int = 0
    success = False

    try:
        # Build per-session agent with actual browser — NOT the module-level
        # executor_agent which uses PlaywrightComputer(session_id="") as placeholder.
        # Sanitize session_id → valid Python identifier (LlmAgent validates name).
        safe_agent_name = f"executor_{session_id}".replace("-", "_").replace(".", "_")
        agent = LlmAgent(
            name=safe_agent_name,
            model="gemini-2.0-flash",
            instruction=EXECUTOR_SYSTEM_PROMPT,
            tools=[ComputerUseToolset(computer=pc)],
        )

        session_svc = InMemorySessionService()
        runner = Runner(
            app_name=_APP_NAME,
            agent=agent,
            session_service=session_svc,
        )
        adk_session = await session_svc.create_session(
            app_name=_APP_NAME,
            user_id=session_id,
        )

        steps = step_plan.get("steps", [])
        step_idx = 0
        while step_idx < len(steps):
            step = steps[step_idx]
            current_step_index = step.get("step_index", current_step_index)
            step_description = step.get("description", f"step {current_step_index}")
            gemini_error_count = 0

            # Pre-step: request user input if the Planner flagged this step as needing it (AC: 2, FR33)
            if step.get("requires_user_input"):
                user_input_reason = (
                    step.get("user_input_reason")
                    or f"I need your input to complete step {current_step_index + 1}"
                )
                emit_event(
                    session_id,
                    "awaiting_input",
                    {
                        "step_index": current_step_index,
                        "reason": "requires_input",
                        "message": user_input_reason,
                    },
                    step_index=current_step_index,
                )
                pre_step_input = await _wait_for_user_input(
                    session_id,
                    current_step_index,
                    paused_with="requires_input",
                    step_description=step_description,
                )
                if pre_step_input is None:
                    return  # timeout already emitted task_failed
                # Shallow-copy step dict (do NOT mutate shared step_plan) and inject user value
                step = dict(step)
                step["user_provided_value"] = pre_step_input

            # Emit step_start BEFORE retry loop (AC: 1, 5)
            emit_event(
                session_id,
                "step_start",
                {
                    "step_index": current_step_index,
                    "action_type": step.get("action"),
                    "description": step_description,
                    "confidence": step.get("confidence", 1.0),
                },
                step_index=current_step_index,
            )

            step_resolved = False
            while not step_resolved:
                last_exc: Exception | None = None
                playwright_timeout_hit = False

                for attempt in range(_MAX_STEP_ATTEMPTS):
                    try:
                        # Capture fresh browser state for each attempt
                        screenshot_bytes = await pc.screenshot()
                        screenshot_b64 = (
                            base64.b64encode(screenshot_bytes).decode()
                            if screenshot_bytes
                            else ""
                        )

                        context = build_executor_context(
                            step_plan,
                            completed_steps,
                            screenshot_b64,
                            user_provided_value=step.get("user_provided_value"),
                        )

                        async for _event in runner.run_async(
                            user_id=session_id,
                            session_id=adk_session.id,
                            new_message=genai_types.Content(
                                role="user",
                                parts=[genai_types.Part(text=context)],
                            ),
                        ):
                            pass  # ADK toolset fires browser actions internally

                        last_exc = None
                        break  # Step action succeeded

                    except BargeInException:
                        raise  # Propagate immediately to outer handler

                    except PlaywrightTimeoutError as exc:
                        # Non-retryable: page load timeout wastes 15s per retry (AC: 1)
                        logger.error(
                            "Page load timeout at step %d session %s: %s",
                            current_step_index,
                            session_id,
                            exc,
                        )
                        emit_event(
                            session_id,
                            "step_error",
                            {
                                "step_index": current_step_index,
                                "error": "Page did not load within 15 seconds",
                                "description": step_description,
                            },
                        )
                        try:
                            await update_session_status(session_id, "error")
                        except Exception:
                            logger.warning(
                                "Failed to update session %s status to 'error'", session_id
                            )
                        playwright_timeout_hit = True
                        break  # Exit attempt loop; handled below

                    except gapi_exceptions.GoogleAPICallError as exc:
                        # Gemini API errors: retry up to _GEMINI_MAX_RETRIES times (AC: 2)
                        gemini_error_count += 1
                        logger.warning(
                            "Gemini API error at step %d session %s attempt %d/%d: %s",
                            current_step_index,
                            session_id,
                            gemini_error_count,
                            _GEMINI_MAX_RETRIES + 1,
                            exc,
                        )
                        if gemini_error_count > _GEMINI_MAX_RETRIES:
                            logger.error(
                                "Gemini API retries exhausted at step %d session %s",
                                current_step_index,
                                session_id,
                            )
                            emit_event(
                                session_id,
                                "task_failed",
                                {
                                    "reason": f"Gemini API error after {_GEMINI_MAX_RETRIES + 1} attempts: {exc}",
                                },
                            )
                            try:
                                await update_session_status(session_id, "failed")
                            except Exception:
                                logger.warning(
                                    "Failed to update session %s status to 'failed'", session_id
                                )
                            return
                        await asyncio.sleep(_GEMINI_BACKOFF_SECONDS)
                        # Continue attempt loop (gemini retry)

                    except Exception as exc:
                        last_exc = exc
                        logger.warning(
                            "Executor step %d attempt %d/%d failed for session %s: %s",
                            current_step_index,
                            attempt + 1,
                            _MAX_STEP_ATTEMPTS,
                            session_id,
                            exc,
                        )
                        if attempt < _MAX_STEP_ATTEMPTS - 1:
                            await asyncio.sleep(_RETRY_DELAY_SECONDS)

                # --- Post-attempt-loop handling ---

                if playwright_timeout_hit:
                    # Emit awaiting_input so frontend shows InputRequestBanner (H1 fix)
                    emit_event(
                        session_id,
                        "awaiting_input",
                        {
                            "step_index": current_step_index,
                            "reason": "page_timeout",
                            "message": "Page did not load within 15 seconds — provide instructions or retry",
                        },
                        step_index=current_step_index,
                    )
                    # Wait for user input to resume or timeout → task_failed (AC: 1, 4)
                    user_input = await _wait_for_user_input(
                        session_id, current_step_index, paused_with="page_timeout",
                        step_description=step_description,
                    )
                    if user_input is None:
                        return  # timeout already emitted task_failed
                    # Restore session status to executing before retrying (H2 fix)
                    try:
                        await update_session_status(session_id, "executing")
                    except Exception:
                        logger.warning("Failed to restore session %s status to 'executing'", session_id)
                    # Reset and retry same step
                    playwright_timeout_hit = False
                    gemini_error_count = 0
                    continue  # while not step_resolved

                if last_exc is not None:
                    # All generic attempts exhausted — emit step_error, await user input (AC: 4)
                    logger.error(
                        "Executor step %d exhausted retries for session %s: %s",
                        current_step_index,
                        session_id,
                        last_exc,
                    )
                    emit_event(
                        session_id,
                        "step_error",
                        {
                            "step_index": current_step_index,
                            "error": str(last_exc),
                            "description": step_description,
                        },
                    )
                    try:
                        await update_session_status(session_id, "error")
                    except Exception:
                        logger.warning(
                            "Failed to update session %s status to 'error'", session_id
                        )
                    # Emit awaiting_input so frontend shows InputRequestBanner (H1 fix)
                    emit_event(
                        session_id,
                        "awaiting_input",
                        {
                            "step_index": current_step_index,
                            "reason": "step_error",
                            "message": f"Step failed after {_MAX_STEP_ATTEMPTS} attempts — provide instructions or retry",
                        },
                        step_index=current_step_index,
                    )
                    user_input = await _wait_for_user_input(
                        session_id, current_step_index, paused_with="step_error",
                        step_description=step_description,
                    )
                    if user_input is None:
                        return  # timeout already emitted task_failed
                    # Restore session status to executing before retrying (H2 fix)
                    try:
                        await update_session_status(session_id, "executing")
                    except Exception:
                        logger.warning("Failed to restore session %s status to 'executing'", session_id)
                    # Reset error state and retry same step
                    gemini_error_count = 0
                    continue  # while not step_resolved

                # Step action succeeded — check for CAPTCHA before accepting (AC: 3)
                if await pc.detect_captcha():
                    logger.warning(
                        "CAPTCHA detected at step %d session %s",
                        current_step_index,
                        session_id,
                    )
                    emit_event(
                        session_id,
                        "awaiting_input",
                        {
                            "step_index": current_step_index,
                            "reason": "captcha_detected",
                            "message": "CAPTCHA encountered — manual intervention required",
                        },
                        step_index=current_step_index,
                    )
                    user_input = await _wait_for_user_input(
                        session_id, current_step_index, paused_with="captcha",
                        step_description=step_description,
                    )
                    if user_input is None:
                        return  # timeout already emitted task_failed
                    # Retry same step after user resolves CAPTCHA
                    gemini_error_count = 0
                    continue  # while not step_resolved

                # Step fully succeeded — capture post-action screenshot, upload, emit step_complete (AC: 2)
                try:
                    post_screenshot_bytes = await pc.screenshot()
                except Exception:
                    logger.warning(
                        "Post-step screenshot failed for session %s step %d",
                        session_id,
                        current_step_index,
                    )
                    post_screenshot_bytes = b""
                screenshot_url = await upload_screenshot(
                    session_id, current_step_index, post_screenshot_bytes
                )
                emit_event(
                    session_id,
                    "step_complete",
                    {
                        "step_index": current_step_index,
                        "screenshot_url": screenshot_url or None,
                        "result_summary": step_description,
                        "confidence": step.get("confidence", 1.0),
                    },
                    step_index=current_step_index,
                )
                # Write step to Firestore audit log (non-fatal — must not halt execution) (AC: 1)
                try:
                    await write_audit_log(
                        session_id,
                        current_step_index,
                        {
                            "action_type": step.get("action"),
                            "description": step_description,
                            "result": "done",
                            "screenshot_url": screenshot_url or None,
                            "confidence": step.get("confidence", 1.0),
                        },
                    )
                except Exception:
                    logger.warning(
                        "Audit log write failed for session %s step %d — continuing",
                        session_id,
                        current_step_index,
                    )
                completed_steps.append(
                    {
                        "step_index": current_step_index,
                        "description": step_description,
                        "action_type": step.get("action"),
                        "confidence": step.get("confidence", 1.0),
                        "result": "done",
                        "screenshot_url": screenshot_url or None,
                    }
                )
                step_resolved = True  # move to next step

            step_idx += 1

        # All steps completed successfully
        success = True


    except BargeInException as e:
        logger.warning(
            "Barge-in during executor for session %s at step %d: %s",
            session_id,
            current_step_index,
            e,
        )
        emit_event(
            session_id,
            "task_paused",
            {"paused_at_step": current_step_index},
        )
        try:
            await update_session_status(session_id, "paused")
        except Exception:
            logger.warning("Failed to update session %s status to 'paused'", session_id)

    except Exception as e:
        logger.error(
            "Executor failed for session %s: %s",
            session_id,
            e,
        )
        emit_event(
            session_id,
            "task_failed",
            {"reason": str(e)},
        )
        try:
            await update_session_status(session_id, "failed")
        except Exception:
            logger.warning("Failed to update session %s status to 'failed'", session_id)

    finally:
        await pc.stop()  # ALWAYS clean up browser resources
        clear_input_queue(session_id)  # Clean up per-session input queue (AC: 4)

    if success:
        try:
            await handle_task_complete(session_id, steps_completed=len(completed_steps))
        except Exception:
            logger.error("handle_task_complete failed for session %s", session_id)
