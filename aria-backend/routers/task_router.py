import logging

import firebase_admin.auth as firebase_auth
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.session_service import create_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task")


class StartTaskRequest(BaseModel):
    task_description: str = Field(..., min_length=1)


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    """Return a canonical error envelope: { success, data, error }."""
    return JSONResponse(
        status_code=status,
        content={"success": False, "data": None, "error": {"code": code, "message": message}},
    )


@router.post("/start")
async def start_task(request: Request, body: StartTaskRequest):
    """
    POST /api/task/start

    1. Extracts and verifies Firebase ID token from Authorization header.
    2. Creates a Firestore session document via session_service.
    3. Returns canonical success envelope with session_id and stream_url.

    All error responses use the same { success, data, error } envelope.
    HTTP 401 (not 403) for any auth failure per architecture spec.
    """
    # 1. Extract Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)

    id_token = auth_header.split("Bearer ", 1)[1].strip()
    if not id_token:
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)

    # 2. Verify Firebase ID token
    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception:
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)

    uid = decoded["uid"]

    # 3. Create Firestore session document
    try:
        session_data = await create_session(uid, body.task_description)
    except Exception:
        logger.exception("Firestore session creation failed for uid=%s", uid)
        return _error_response("INTERNAL_ERROR", "Session creation failed", 500)

    return JSONResponse(
        status_code=200,
        content={"success": True, "data": session_data, "error": None},
    )
