import logging

import firebase_admin.auth as firebase_auth
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from services.session_service import create_session, update_session_status
from services.planner_service import run_planner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task")


class StartTaskRequest(BaseModel):
    task_description: str = Field(..., min_length=1)
    context: Optional[str] = Field(None, description="Optional supplementary context for the Planner (FR3)")


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
    3. Runs the Planner agent to produce a canonical step plan.
    4. Stores the step plan in Firestore and returns it in the response.

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

    # 3. Create Firestore session document (status: "pending")
    try:
        session_data = await create_session(uid, body.task_description)
    except Exception:
        logger.exception("Firestore session creation failed for uid=%s", uid)
        return _error_response("INTERNAL_ERROR", "Session creation failed", 500)

    session_id = session_data["session_id"]

    # 4. Update session status to "planning" before invoking Planner
    try:
        await update_session_status(session_id, "planning")
    except Exception:
        logger.warning("Failed to update session %s status to 'planning' — continuing", session_id)

    # 5. Invoke Planner agent
    try:
        step_plan = await run_planner(
            task_description=body.task_description,
            context=body.context,
        )
    except Exception:
        logger.exception("Planner failed for session_id=%s", session_id)
        try:
            await update_session_status(session_id, "failed")
        except Exception:
            logger.warning("Failed to update session %s status to 'failed'", session_id)
        return _error_response("PLANNER_ERROR", "Planner agent failed to produce a step plan", 500)

    # 6. Store step plan in Firestore and update status to "plan_ready"
    try:
        await update_session_status(
            session_id,
            "plan_ready",
            extra_fields={"steps": step_plan.get("steps", []), "task_summary": step_plan.get("task_summary", "")},
        )
    except Exception:
        logger.warning("Failed to update session %s with step plan — returning plan anyway", session_id)

    # 7. Return canonical success envelope with session data + step plan
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                **session_data,
                "step_plan": step_plan,
            },
            "error": None,
        },
    )
