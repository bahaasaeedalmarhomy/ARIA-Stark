import asyncio
import uuid
from datetime import datetime, timezone
from google.cloud import firestore

_db = None


def _get_db() -> firestore.AsyncClient:
    """Lazy Firestore client — avoids ADC lookup at import time (needed for tests)."""
    global _db
    if _db is None:
        _db = firestore.AsyncClient()
    return _db


async def create_session(uid: str, task_description: str) -> dict:
    """
    Creates a new Firestore session document under sessions/{session_id}.

    Document fields (per architecture spec):
    - session_id  : "sess_" + UUID v4
    - uid         : Firebase anonymous auth uid
    - task_description: verbatim from request body
    - status      : "pending" (pre-execution state; ADK runner not started here)
    - created_at  : ISO 8601 UTC timestamp with "Z" suffix
    - steps       : [] (populated in Stories 2+)

    Returns the dict used in the API success response data envelope.
    """
    session_id = "sess_" + str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    doc_data = {
        "session_id": session_id,
        "uid": uid,
        "task_description": task_description,
        "status": "pending",
        "created_at": created_at,
        "steps": [],
    }

    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    await doc_ref.set(doc_data)

    return {
        "session_id": session_id,
        "stream_url": f"/api/stream/{session_id}",
    }


async def get_session(session_id: str) -> dict:
    """Retrieve a session document by session_id."""
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    doc = await doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {}


async def update_session_status(session_id: str, status: str, extra_fields: dict | None = None) -> None:
    """
    Update the status (and any extra fields) on an existing Firestore session document.

    Args:
        session_id: The session document ID (e.g., "sess_<uuid>")
        status: New status string (e.g., "planning", "plan_ready", "failed")
        extra_fields: Optional dict of additional fields to merge (e.g., {"steps": [...]})
    """
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    update_data = {"status": status}
    if extra_fields:
        update_data.update(extra_fields)
    await doc_ref.update(update_data)


# ──────────────────────────── Barge-in cancel flags ───────────────────────────

# Per-session asyncio.Event flags used for barge-in cancellation (Story 3.1+).
# The PlaywrightComputer checks these before/after every await to raise BargeInException.
_cancel_flags: dict[str, asyncio.Event] = {}


def get_cancel_flag(session_id: str) -> asyncio.Event:
    """
    Return (or lazily create) the cancel Event for a session.

    The flag is shared between the SSE barge-in handler (writer)
    and PlaywrightComputer._check_cancel() (reader).
    """
    if session_id not in _cancel_flags:
        _cancel_flags[session_id] = asyncio.Event()
    return _cancel_flags[session_id]


def reset_cancel_flag(session_id: str) -> None:
    """
    Clear the cancel flag for a session.
    Called at the start of a new execution to ensure a clean state.
    """
    if session_id in _cancel_flags:
        _cancel_flags[session_id].clear()
    else:
        _cancel_flags[session_id] = asyncio.Event()
    clear_user_cancel_flag(session_id)
    _paused_step_indices.pop(session_id, None)


# ──────────────────────────── User-cancel flags ───────────────────────────

# Per-session flags used to distinguish user-initiated cancel from barge-in cancel
_user_cancel_flags: dict[str, bool] = {}


def set_user_cancel_flag(session_id: str) -> None:
    """Mark a session as user-cancelled (called from /interrupt endpoint)."""
    _user_cancel_flags[session_id] = True


def is_user_cancel(session_id: str) -> bool:
    """Return True if the cancel was triggered by the user via /interrupt."""
    return _user_cancel_flags.get(session_id, False)


def clear_user_cancel_flag(session_id: str) -> None:
    """Clear the user-cancel marker (call on session reset)."""
    _user_cancel_flags.pop(session_id, None)


# ──────────────────────────── Barge-in signal (voice, not user cancel) ────────

def signal_barge_in(session_id: str) -> None:
    """
    Signal a voice barge-in for a session.
    Sets the cancel flag ONLY — does NOT set is_user_cancel().
    The executor will emit task_paused (not task_failed) in response.
    Called from POST /api/task/{session_id}/barge-in.
    """
    get_cancel_flag(session_id).set()


# ──────────────────────────── Paused step tracking ────────────────────────────

_paused_step_indices: dict[str, int] = {}


def set_paused_step(session_id: str, step_index: int) -> None:
    """Store the step index at which execution was paused (for re-plan)."""
    _paused_step_indices[session_id] = step_index


def get_paused_step(session_id: str) -> int:
    """Return the paused step index, or 0 if not set."""
    return _paused_step_indices.get(session_id, 0)
