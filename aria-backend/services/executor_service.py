"""
Executor service — Story 3.2: Playwright Browser Actions.

Per-session execution loop that creates a PlaywrightComputer browser,
builds a per-session LlmAgent + ADK Runner, and drives the agent through
the step plan, handling barge-in and per-step error retry logic.

SSE events emitted by this module:
  - task_paused   : BargeInException caught mid-execution
  - step_error    : Step fails after 2 retries (exhausted)
  - task_failed   : Unrecoverable executor error
"""
import asyncio
import base64
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from google.genai import types as genai_types

from agents.executor_agent import build_executor_context
from prompts.executor_system import EXECUTOR_SYSTEM_PROMPT
from services.session_service import update_session_status
from services.sse_service import emit_event
from services.task_complete_service import handle_task_complete
from tools.playwright_computer import BargeInException, PlaywrightComputer

logger = logging.getLogger(__name__)

_APP_NAME = "aria_executor"
_MAX_STEP_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.3


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
        for step in steps:
            current_step_index = step.get("step_index", current_step_index)
            step_description = step.get("description", f"step {current_step_index}")

            last_exc: Exception | None = None
            for attempt in range(_MAX_STEP_ATTEMPTS):
                try:
                    # Capture fresh browser state for each attempt (AC 6:
                    # "re-takes a screenshot, re-evaluates the page state")
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
                    )

                    async for _event in runner.run_async(
                        user_id=session_id,
                        session_id=adk_session.id,
                        new_message=genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(text=context)],
                        ),
                    ):
                        pass  # ADK toolset fires browser actions internally via ComputerUseToolset

                    completed_steps.append(
                        {
                            "step_index": current_step_index,
                            "description": step_description,
                            "result": "done",
                        }
                    )
                    last_exc = None
                    break  # Step succeeded — move to next step

                except BargeInException:
                    raise  # Propagate immediately to outer barge-in handler

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

            if last_exc is not None:
                # All attempts exhausted — emit step_error and stop execution
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
                    logger.warning("Failed to update session %s status to 'error'", session_id)
                return

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
        await pc.stop()  # ALWAYS clean up browser resources (AC: 6)

    if success:
        try:
            await handle_task_complete(session_id, steps_completed=len(completed_steps))
        except Exception:
            logger.error("handle_task_complete failed for session %s", session_id)
