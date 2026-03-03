"""
Re-plan service — Story 4.4.

After a voice barge-in, this service:
  1. Waits for the user's voice instruction (transcription via voice_instruction_service)
  2. Invokes the Planner with the combined original task + user correction
  3. Emits a new plan_ready SSE event
  4. Resumes execution with run_executor from the current browser state
"""
import asyncio
import logging

from services.session_service import get_session, update_session_status, reset_cancel_flag, get_browser_instance
from services.sse_service import emit_event
from services.voice_instruction_service import (
    get_instruction,
    release_voice_instruction_queue,
)

logger = logging.getLogger(__name__)


async def wait_for_voice_instruction_and_replan(
    session_id: str,
    paused_at_step: int,
) -> None:
    """
    Wait for the user's voice instruction, invoke the Planner with the correction,
    emit a new plan_ready SSE event, and resume execution.

    Called as asyncio.create_task() from executor_service.py after task_paused is emitted.
    The task runs concurrently — the browser state is preserved (no page reload).
    """
    try:
        instruction = await get_instruction(session_id, timeout=60.0)
        if not instruction:
            logger.warning(
                "No voice instruction received for session %s within 60s — timing out",
                session_id,
            )
            emit_event(session_id, "task_failed", {"reason": "barge_in_timeout"})
            try:
                await update_session_status(session_id, "failed")
            except Exception:
                logger.warning("Failed to update session %s status to 'failed'", session_id)
            return

        # Load session to get original task description
        session = await get_session(session_id)
        task_desc = session.get("task_description", "")
        original_context = session.get("context", "")

        combined = (
            f"Original task: {task_desc}\n"
            f"User interrupted at step {paused_at_step} with correction: {instruction}"
        )

        # Invoke Planner with combined instruction (preserve original context)
        from services.planner_service import run_planner  # deferred import
        try:
            new_step_plan = await run_planner(
                task_description=combined,
                context=original_context if original_context else None,
            )
        except Exception:
            logger.exception("Planner failed during re-plan for session %s", session_id)
            emit_event(session_id, "task_failed", {"reason": "replan_planner_failed"})
            try:
                await update_session_status(session_id, "failed")
            except Exception:
                logger.warning("Failed to update session %s status to 'failed'", session_id)
            return

        # Emit new plan_ready with is_replan=True so frontend resets the step list
        emit_event(
            session_id,
            "plan_ready",
            {
                "steps": new_step_plan.get("steps", []),
                "task_summary": new_step_plan.get("task_summary", ""),
                "is_replan": True,
            },
        )

        try:
            await update_session_status(session_id, "executing")
        except Exception:
            logger.warning("Failed to update session %s status to 'executing'", session_id)

        # Clear cancel flag before resuming (it stays set from barge-in signal)
        reset_cancel_flag(session_id)

        # Resume executor from current browser state (no page reload, no session restart)
        from services.executor_service import run_executor  # deferred import
        pc = get_browser_instance(session_id)
        await run_executor(session_id, new_step_plan, existing_pc=pc)

    finally:
        release_voice_instruction_queue(session_id)
