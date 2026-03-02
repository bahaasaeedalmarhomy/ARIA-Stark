"""
Input Queue Service — Story 3.4: Error Handling, CAPTCHA Pause, and Input Resume.

Per-session asyncio.Queue for user-provided input during paused execution.
Mirrors the barge-in cancel flag dict pattern from session_service.py but uses
an asyncio.Queue[str] to deliver typed user responses to the waiting executor.

Usage:
    # In executor_service.py (waiting side):
    queue = get_input_queue(session_id)
    user_input = await asyncio.wait_for(queue.get(), timeout=300.0)

    # In task_router.py (delivery side):
    put_user_input(session_id, body.value)

    # In executor_service.py finally block (cleanup):
    clear_input_queue(session_id)
"""
import asyncio

_input_queues: dict[str, asyncio.Queue[str]] = {}


def get_input_queue(session_id: str) -> asyncio.Queue[str]:
    """
    Return the asyncio.Queue for `session_id`, creating it lazily if absent.
    Subsequent calls for the same session_id return the same queue instance.
    """
    if session_id not in _input_queues:
        _input_queues[session_id] = asyncio.Queue()
    return _input_queues[session_id]


def put_user_input(session_id: str, value: str) -> None:
    """
    Enqueue `value` for `session_id`.
    Creates the queue if it does not already exist.
    Uses put_nowait — non-blocking; the queue is unbounded.
    """
    get_input_queue(session_id).put_nowait(value)


def clear_input_queue(session_id: str) -> None:
    """
    Remove and discard the queue for `session_id`.
    Safe to call even if no queue exists (no-op).
    Should be called in the executor finally block to prevent goroutine leaks.
    """
    _input_queues.pop(session_id, None)


def has_input_queue(session_id: str) -> bool:
    """Return True if an active input queue exists for `session_id`."""
    return session_id in _input_queues
