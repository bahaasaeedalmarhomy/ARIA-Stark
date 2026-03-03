"""
Per-session audio queue management for the voice relay.

Follows the same module-level dict pattern as `_cancel_flags` in session_service.py.
The `None` sentinel signals shutdown to the drain coroutine.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_audio_queues: dict[str, asyncio.Queue[bytes | None]] = {}


def create_audio_queue(session_id: str) -> asyncio.Queue[bytes | None]:
    """
    Create and store a new unbounded asyncio.Queue for inbound audio chunks.
    Returns the queue for immediate use by the relay.
    """
    if session_id in _audio_queues:
        logger.warning("Overwriting existing audio queue for session %s (rapid reconnect?)", session_id)
    q: asyncio.Queue[bytes | None] = asyncio.Queue()
    _audio_queues[session_id] = q
    return q


def get_audio_queue(session_id: str) -> asyncio.Queue[bytes | None] | None:
    """Return existing queue or None if not found."""
    return _audio_queues.get(session_id)


def release_audio_queue(session_id: str) -> None:
    """
    Remove queue from the dict.
    Caller must cancel relay coroutines before calling this.
    """
    _audio_queues.pop(session_id, None)
