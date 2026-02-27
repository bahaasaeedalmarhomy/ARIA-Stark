"""
SSE Event Manager Service

Provides module-level event queues for broadcasting Server-Sent Events
to subscribed clients per session. Supports multiple concurrent subscribers
per session (reconnection-safe).

Usage:
    emit_event(session_id, "plan_ready", {"steps": [...]})  # from request handlers
    async for event_str in subscribe(session_id):           # from SSE endpoint generator
        yield f"data: {event_str}\n\n"
    unsubscribe(session_id)                                 # in finally block on disconnect
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Module-level registry: session_id → list of asyncio.Queue
# Each connected SSE client gets its own Queue; supports multiple subscribers
# per session (e.g., reconnection creates a new queue before old one is removed).
_event_queues: dict[str, list[asyncio.Queue]] = {}


def emit_event(
    session_id: str,
    event_type: str,
    payload: dict,
    step_index: int | None = None,
) -> None:
    """Broadcast an SSE event to all subscribers of a session.

    Builds the canonical SSE envelope and puts it on every registered queue
    for the given session. If no subscribers exist, the event is silently
    dropped (correct behaviour — no listeners means no one to receive).

    Args:
        session_id:  The session to broadcast to.
        event_type:  Snake-case verb_noun event type (e.g. "plan_ready").
        payload:     Arbitrary dict attached to the event.
        step_index:  Optional step index for step-scoped events; None otherwise.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    event = json.dumps(
        {
            "event_type": event_type,
            "session_id": session_id,
            "step_index": step_index,
            "timestamp": timestamp,
            "payload": payload,
        }
    )

    queues = _event_queues.get(session_id, [])
    for queue in queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "SSE queue full for session %s — event %s dropped", session_id, event_type
            )


async def subscribe(session_id: str) -> AsyncGenerator[str, None]:
    """Subscribe to SSE events for a session.

    Registers a new asyncio.Queue for the session and yields JSON event
    strings as they arrive. Designed to run inside a FastAPI StreamingResponse
    async generator.

    Yields:
        JSON-serialised canonical SSE envelope strings (without "data:" prefix).
    """
    queue: asyncio.Queue = asyncio.Queue()
    if session_id not in _event_queues:
        _event_queues[session_id] = []
    _event_queues[session_id].append(queue)

    try:
        while True:
            event = await queue.get()
            yield event
            
            # Identify terminal events to securely close the stream
            try:
                event_data = json.loads(event)
                if event_data.get("event_type") in ("task_complete", "task_failed"):
                    break
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
    finally:
        unsubscribe(session_id, queue)


def unsubscribe(session_id: str, queue: asyncio.Queue | None = None) -> None:
    """Clean up queue(s) for a session on client disconnect."""
    if queue is not None:
        if session_id in _event_queues:
            try:
                _event_queues[session_id].remove(queue)
            except ValueError:
                pass
            if not _event_queues[session_id]:
                _event_queues.pop(session_id, None)
                logger.debug("Last SSE queue removed for session %s", session_id)
    else:
        removed = _event_queues.pop(session_id, None)
        if removed is not None:
            logger.debug("SSE queues cleaned up for session %s (%d queues)", session_id, len(removed))
