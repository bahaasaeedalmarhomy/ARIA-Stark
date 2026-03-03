import logging
import asyncio
from typing import Optional

import firebase_admin.auth as firebase_auth
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.executor_service import run_executor
from services.planner_service import run_planner
from services.session_service import create_session, update_session_status, get_cancel_flag, set_user_cancel_flag, signal_barge_in
from services.sse_service import emit_event
from services.input_queue_service import has_input_queue, put_user_input

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task")


class UserInputRequest(BaseModel):
    value: str = Field(..., min_length=1)


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
    except Exception as exc:
        logger.warning("verify_id_token failed: %s", exc)
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)

    uid = decoded["uid"]

    # 3. Create Firestore session document (status: "pending")
    try:
        session_data = await create_session(uid, body.task_description, context=body.context)
    except Exception:
        logger.exception("Firestore session creation failed for uid=%s", uid)
        return _error_response("INTERNAL_ERROR", "Session creation failed", 500)

    session_id = session_data["session_id"]
    warnings = []

    # 4. Update session status to "planning" before invoking Planner
    try:
        await update_session_status(session_id, "planning")
    except Exception:
        logger.warning("Failed to update session %s status to 'planning' — continuing", session_id)
        warnings.append("Session status update to 'planning' failed — Firestore may be stale")

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
        # Emit task_failed SSE event so connected clients receive the failure
        try:
            emit_event(session_id, "task_failed", {"reason": "Planner agent failed to produce a step plan"})
        except Exception:
            logger.warning("Failed to emit task_failed SSE event for session %s", session_id)
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
        warnings.append("Step plan storage in Firestore failed — plan returned but session may be incomplete")

    # 7. Update status to executing and launch executor as background task
    try:
        await update_session_status(session_id, "executing")
    except Exception:
        logger.warning(
            "Failed to update session %s status to 'executing' — continuing", session_id
        )
        warnings.append(
            "Session status update to 'executing' failed — Firestore may be stale"
        )

    try:
        asyncio.create_task(run_executor(session_id, step_plan))
    except Exception:
        logger.exception("Failed to launch executor for session_id=%s", session_id)
        try:
            emit_event(session_id, "task_failed", {"reason": "Executor launch failed"})
        except Exception:
            logger.warning(
                "Failed to emit task_failed SSE event for session %s", session_id
            )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": {"code": "EXECUTOR_LAUNCH_ERROR", "message": "Executor failed to start"},
            },
        )

    try:
        async def _emit():
            await asyncio.sleep(0.2)
            emit_event(
                session_id,
                "plan_ready",
                {
                    "steps": [],
                    "task_summary": step_plan.get("task_summary", ""),
                },
            )
            steps = step_plan.get("steps", [])
            for step in steps:
                await asyncio.sleep(0.1)
                emit_event(
                    session_id,
                    "step_planned",
                    {"step": step},
                    step_index=step.get("step_index"),
                )
        asyncio.create_task(_emit())
    except Exception:
        logger.warning("Failed to schedule plan_ready SSE event for session %s", session_id)
        warnings.append("SSE plan_ready event scheduling failed — frontend may not receive live update")

    # 8. Return canonical success envelope with session data + step plan
    response_data = {
        **session_data,
        "step_plan": step_plan,
    }
    if warnings:
        response_data["warnings"] = warnings

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": response_data,
            "error": None,
        },
    )


@router.post("/{session_id}/interrupt")
async def interrupt_task(session_id: str):
    """
    POST /api/task/{session_id}/interrupt

    Sets the per-session cancel flag so the Executor's _check_cancel() raises
    BargeInException on the next playwright action. The executor then emits
    task_failed with reason "user_cancelled" and updates Firestore status to
    "cancelled".

    No auth check — session_id is treated as the implicit ownership token (UUID v4).
    Returns 200 immediately; actual stop is async (within current action boundary).
    """
    set_user_cancel_flag(session_id)
    get_cancel_flag(session_id).set()
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": {"interrupted": True}, "error": None},
    )


@router.post("/{session_id}/barge-in")
async def barge_in_task(session_id: str):
    """
    POST /api/task/{session_id}/barge-in

    Signals a voice barge-in — sets the cancel flag WITHOUT setting is_user_cancel().
    The executor will emit task_paused (not task_failed) and schedule re-plan.
    The re-plan waits for a voice transcription via voice_instruction_service.

    No auth check — session_id (UUID v4) acts as implicit ownership token,
    consistent with /interrupt and /input endpoints.
    """
    signal_barge_in(session_id)
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": {"barge_in": True}, "error": None},
    )


@router.post("/{session_id}/input")
async def submit_user_input(session_id: str, body: UserInputRequest):
    """
    POST /api/task/{session_id}/input

    Delivers user-provided text input to a paused executor session.
    No auth check — session_id acts as the implicit ownership token (UUID v4).
    Same pattern as /interrupt.

    Returns 404 if no active input queue exists for the session (executor not waiting).
    """
    if not has_input_queue(session_id):
        return _error_response("INPUT_NOT_EXPECTED", f"No paused session awaiting input: {session_id}", 404)

    put_user_input(session_id, body.value)
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": {"queued": True}, "error": None},
    )
