"""
Voice instruction service — Story 4.4.

Provides a per-session asyncio.Queue for delivering user voice transcriptions
to the re-plan endpoint after a barge-in pause.

Usage flow:
  1. executor_service.py schedules wait_for_voice_instruction_and_replan()
     after emitting task_paused — that call creates the queue.
  2. voice_handler.py calls try_put_instruction() when it receives a
     transcription (response.text) while the session is paused.
  3. replan_service.py awaits get_instruction() to receive the transcription.
  4. After re-plan is complete, release_voice_instruction_queue() cleans up.
"""
import asyncio

_queues: dict[str, asyncio.Queue[str]] = {}


def create_voice_instruction_queue(session_id: str) -> asyncio.Queue[str]:
    """Create a bounded (maxsize=1) queue for voice instructions for the session."""
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    _queues[session_id] = q
    return q


def try_put_instruction(session_id: str, text: str) -> None:
    """
    Non-blocking put. Silently drops if no queue exists or queue is full.
    Called from voice_handler.py relay loop (hot path).
    """
    q = _queues.get(session_id)
    if q:
        try:
            q.put_nowait(text)
        except asyncio.QueueFull:
            pass  # Already has an instruction queued; skip duplicate


async def get_instruction(session_id: str, timeout: float = 60.0) -> str | None:
    """
    Await an instruction from the user.
    Returns None on timeout.
    """
    q = _queues.get(session_id)
    if not q:
        return None
    try:
        return await asyncio.wait_for(q.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def release_voice_instruction_queue(session_id: str) -> None:
    """Remove the queue for a session (cleanup after re-plan completes or fails)."""
    _queues.pop(session_id, None)
