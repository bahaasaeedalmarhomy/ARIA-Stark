import logging
from datetime import datetime, timezone

from google.cloud import firestore

logger = logging.getLogger(__name__)
_db = None


def _get_db() -> firestore.AsyncClient:
    global _db
    if _db is None:
        _db = firestore.AsyncClient()
    return _db


async def write_audit_log(session_id: str, step_index: int, data: dict) -> None:
    """Append a completed step entry to Firestore sessions/{session_id}.steps[]."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    entry = {
        "step_index": step_index,
        "action_type": data.get("action_type"),
        "description": data.get("description", ""),
        "result": data.get("result", "done"),
        "screenshot_url": data.get("screenshot_url"),
        "confidence": data.get("confidence", 1.0),
        "timestamp": timestamp,
        "status": "complete",
    }
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    await doc_ref.update({"steps": firestore.ArrayUnion([entry])})
    logger.debug(
        "Audit log written for session %s step %d", session_id, step_index
    )


async def update_session_status(session_id: str, status: str) -> None:
    """
    Update the Firestore session document status field.

    Delegates to session_service.update_session_status so the audit writer
    can be the single call-site for completion state changes (AC: 4).

    Args:
        session_id: The session document ID (e.g., "sess_<uuid>").
        status: New status string (e.g., "complete", "failed").
    """
    from services.session_service import update_session_status as _update
    await _update(session_id, status)
