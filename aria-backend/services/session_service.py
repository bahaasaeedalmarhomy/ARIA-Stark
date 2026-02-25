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
