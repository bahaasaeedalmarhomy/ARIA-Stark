"""
Task completion handler — extracted from task_router.py to break circular import.

Handles post-execution cleanup: updates Firestore session status to "complete"
and emits the canonical `task_complete` SSE event.

Story 3.1 (AC: 4) — original implementation in task_router.py.
Story 3.2 — extracted here so executor_service.py can import without circular dependency.
"""
import logging

from handlers.audit_writer import update_session_status as audit_update_session_status
from services.sse_service import emit_event

logger = logging.getLogger(__name__)


async def handle_task_complete(session_id: str, steps_completed: int) -> None:
    """
    Handle task completion — AC: 4 (Story 3.1).

    Called when the executor finishes all steps successfully.
    Emits the canonical `task_complete` SSE event and updates Firestore session status.

    Args:
        session_id: The active session ID.
        steps_completed: Count of executor steps completed.
    """
    try:
        await audit_update_session_status(session_id, "complete")
    except Exception:
        logger.warning("Failed to update Firestore status to 'complete' for session %s", session_id)

    try:
        emit_event(
            session_id,
            "task_complete",
            {
                "steps_completed": steps_completed,
                "session_id": session_id,
            },
        )
    except Exception:
        logger.warning("Failed to emit task_complete SSE event for session %s", session_id)
