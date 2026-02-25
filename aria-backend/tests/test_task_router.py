"""
Unit tests for POST /api/task/start route.

Firebase Admin SDK and Firestore are mocked via conftest.py and per-test patches.
Run with: cd aria-backend && pytest tests/test_task_router.py -v
"""
import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper: build a mock session result
# ---------------------------------------------------------------------------

_MOCK_SESSION = {
    "session_id": "sess_00000000-0000-0000-0000-000000000000",
    "stream_url": "/api/stream/sess_00000000-0000-0000-0000-000000000000",
}


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
# Test: valid token + valid body → 200 with session_id and stream_url
# ---------------------------------------------------------------------------

def test_start_task_valid_token_returns_200():
    mock_decoded = {"uid": "test-uid-123"}

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value=mock_decoded),
        patch(
            "routers.task_router.create_session",
            new_callable=AsyncMock,
            return_value=_MOCK_SESSION,
        ),
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


# ---------------------------------------------------------------------------
# Test: session_id must use sess_ prefix + UUID4 format
# ---------------------------------------------------------------------------

def test_start_task_session_id_format():
    mock_decoded = {"uid": "uid-abc"}
    session_id = "sess_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    mock_session = {
        "session_id": session_id,
        "stream_url": f"/api/stream/{session_id}",
    }

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value=mock_decoded),
        patch(
            "routers.task_router.create_session",
            new_callable=AsyncMock,
            return_value=mock_session,
        ),
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
    mock_decoded = {"uid": "uid-xyz"}

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value=mock_decoded),
        patch(
            "routers.task_router.create_session",
            new_callable=AsyncMock,
            return_value=_MOCK_SESSION,
        ),
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
    mock_decoded = {"uid": "uid-fail"}

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value=mock_decoded),
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

