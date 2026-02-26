"""
Unit tests for POST /api/task/start route.

Firebase Admin SDK, Firestore, and Planner agent are mocked via conftest.py and per-test patches.
Run with: cd aria-backend && pytest tests/test_task_router.py -v
"""
import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper: build mock session and planner results
# ---------------------------------------------------------------------------

_MOCK_SESSION = {
    "session_id": "sess_00000000-0000-0000-0000-000000000000",
    "stream_url": "/api/stream/sess_00000000-0000-0000-0000-000000000000",
}

_MOCK_STEP_PLAN = {
    "task_summary": "Search for cats on Google",
    "steps": [
        {
            "step_index": 0,
            "description": "Navigate to Google",
            "action": "navigate",
            "target": "https://google.com",
            "value": None,
            "confidence": 0.98,
            "is_destructive": False,
            "requires_user_input": False,
            "user_input_reason": None,
        }
    ],
}


def _mock_patches(mock_session=_MOCK_SESSION, mock_plan=_MOCK_STEP_PLAN):
    """Return context manager tuple that mocks all external dependencies."""
    return (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=mock_session),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=mock_plan),
    )


# ---------------------------------------------------------------------------
# Test: missing Authorization header → 401
# ---------------------------------------------------------------------------

def test_start_task_no_auth_header():
    response = client.post(
        "/api/task/start",
        json={"task_description": "Search for cats"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Test: Authorization header without "Bearer " prefix → 401
# ---------------------------------------------------------------------------

def test_start_task_malformed_auth_header():
    response = client.post(
        "/api/task/start",
        json={"task_description": "Search for cats"},
        headers={"Authorization": "Token not-a-bearer-token"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Test: invalid / expired token (firebase_auth.verify_id_token raises) → 401
# ---------------------------------------------------------------------------

def test_start_task_invalid_token():
    with patch("routers.task_router.firebase_auth.verify_id_token", side_effect=Exception("Invalid")):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Search for cats"},
            headers={"Authorization": "Bearer bad.token.here"},
        )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Test: valid token + valid body → 200 with session_id, stream_url, and step_plan
# ---------------------------------------------------------------------------

def test_start_task_valid_token_returns_200():
    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "test-uid-123"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=_MOCK_SESSION),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=_MOCK_STEP_PLAN),
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Search for cats"},
            headers={"Authorization": "Bearer valid.firebase.token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert "session_id" in body["data"]
    assert "stream_url" in body["data"]
    assert body["data"]["session_id"].startswith("sess_")
    assert body["data"]["stream_url"] == f"/api/stream/{body['data']['session_id']}"
    assert "step_plan" in body["data"]
    assert body["data"]["step_plan"]["task_summary"] == "Search for cats on Google"


# ---------------------------------------------------------------------------
# Test: session_id must use sess_ prefix + UUID4 format
# ---------------------------------------------------------------------------

def test_start_task_session_id_format():
    session_id = "sess_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    mock_session = {
        "session_id": session_id,
        "stream_url": f"/api/stream/{session_id}",
    }

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "uid-abc"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=mock_session),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=_MOCK_STEP_PLAN),
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Open Gmail"},
            headers={"Authorization": "Bearer some.valid.token"},
        )

    assert response.status_code == 200
    returned_id = response.json()["data"]["session_id"]
    pattern = r"^sess_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(pattern, returned_id), f"session_id format invalid: {returned_id}"


# ---------------------------------------------------------------------------
# Test: response envelope always has success, data, error keys
# ---------------------------------------------------------------------------

def test_start_task_response_envelope_shape():
    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "uid-xyz"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=_MOCK_SESSION),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=_MOCK_STEP_PLAN),
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Book a flight"},
            headers={"Authorization": "Bearer valid.token"},
        )

    body = response.json()
    assert "success" in body
    assert "data" in body
    assert "error" in body


# ---------------------------------------------------------------------------
# Test: empty task_description → 422 with canonical envelope
# ---------------------------------------------------------------------------

def test_start_task_empty_description_returns_422():
    response = client.post(
        "/api/task/start",
        json={"task_description": ""},
        headers={"Authorization": "Bearer valid.token"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Test: Firestore failure → 500 with canonical envelope (H1)
# ---------------------------------------------------------------------------

def test_start_task_firestore_failure_returns_500():
    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "uid-fail"}),
        patch(
            "routers.task_router.create_session",
            new_callable=AsyncMock,
            side_effect=Exception("Firestore unavailable"),
        ),
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Test task"},
            headers={"Authorization": "Bearer valid.token"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Test: Planner failure → 500 with PLANNER_ERROR code
# ---------------------------------------------------------------------------

def test_start_task_planner_failure_returns_500():
    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "uid-plan-fail"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=_MOCK_SESSION),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch(
            "routers.task_router.run_planner",
            new_callable=AsyncMock,
            side_effect=Exception("Planner API error"),
        ),
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Test task"},
            headers={"Authorization": "Bearer valid.token"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "PLANNER_ERROR"


# ---------------------------------------------------------------------------
# Test: optional context field is accepted (AC4)
# ---------------------------------------------------------------------------

def test_start_task_accepts_optional_context():
    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "uid-ctx"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=_MOCK_SESSION),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=_MOCK_STEP_PLAN) as mock_run_planner,
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Buy product", "context": "product_url: https://example.com/product"},
            headers={"Authorization": "Bearer valid.token"},
        )

    assert response.status_code == 200
    # Verify context was passed through to run_planner
    mock_run_planner.assert_called_once()
    call_kwargs = mock_run_planner.call_args
    assert call_kwargs.kwargs.get("context") == "product_url: https://example.com/product"
