"""
Unit tests for SSE stream endpoint (GET /api/stream/{session_id})
and the SSE event manager service (services/sse_service.py).

Firebase Admin SDK is mocked globally by conftest.py.
Firestore get_session() is mocked per-test.

Run with:
    cd aria-backend && pytest tests/test_sse_handler.py -v
"""
import asyncio
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=False)

_SESSION_ID = "sess_11111111-2222-3333-4444-555555555555"

_MOCK_SESSION = {
    "session_id": _SESSION_ID,
    "stream_url": f"/api/stream/{_SESSION_ID}",
    "status": "plan_ready",
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
            "confidence": 0.95,
            "is_destructive": False,
            "requires_user_input": False,
            "user_input_reason": None,
        }
    ],
}


# ---------------------------------------------------------------------------
# Helper: reset module-level SSE queue state between tests
# ---------------------------------------------------------------------------

def _reset_sse_queues():
    """Clear the module-level _event_queues dict to prevent test bleed-through."""
    import services.sse_service as svc
    svc._event_queues.clear()


# ---------------------------------------------------------------------------
# Test 1: Unknown session_id → 404 with canonical error envelope (AC5)
# ---------------------------------------------------------------------------

def test_stream_unknown_session_returns_404():
    with patch("handlers.sse_handler.get_session", new_callable=AsyncMock, return_value=None), \
         patch("handlers.sse_handler.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}):
        response = client.get(f"/api/stream/sess_nonexistent-session-id", headers={"Authorization": "Bearer valid.token"})

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "SESSION_NOT_FOUND"
    assert "Session not found" in body["error"]["message"]


# ---------------------------------------------------------------------------
# Test 2: Valid session_id → Content-Type: text/event-stream (AC1)
# ---------------------------------------------------------------------------

def test_stream_valid_session_content_type():
    """Endpoint opens stream with correct Content-Type for valid session.

    Uses a mock subscribe() that yields one event and exits so the
    StreamingResponse completes and headers can be inspected without blocking.
    """
    _reset_sse_queues()

    async def _finite_gen(session_id: str):
        yield '{"event_type":"plan_ready","session_id":"' + session_id + '","step_index":null,"timestamp":"2026-02-26T14:30:00.000Z","payload":{}}'

    with (
        patch("handlers.sse_handler.get_session", new_callable=AsyncMock, return_value=_MOCK_SESSION),
        patch("handlers.sse_handler.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}),
        patch("handlers.sse_handler.subscribe", side_effect=_finite_gen),
    ):
        response = client.get(f"/api/stream/{_SESSION_ID}", headers={"Authorization": "Bearer valid.token"})

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/event-stream" in content_type


# ---------------------------------------------------------------------------
# Test 3: emit_event creates a canonical SSE envelope (AC3)
# ---------------------------------------------------------------------------

def test_emit_event_creates_canonical_envelope():
    """emit_event puts a JSON string matching the canonical envelope on the queue."""
    _reset_sse_queues()

    import services.sse_service as svc

    # Manually register a queue so emit_event can broadcast to it
    queue: asyncio.Queue = asyncio.Queue()
    svc._event_queues[_SESSION_ID] = [queue]

    svc.emit_event(
        session_id=_SESSION_ID,
        event_type="plan_ready",
        payload={"steps": [], "task_summary": "test task"},
        step_index=None,
    )

    assert not queue.empty()
    raw = queue.get_nowait()
    event = json.loads(raw)

    # Check all required canonical fields are present and correct
    assert event["event_type"] == "plan_ready"
    assert event["session_id"] == _SESSION_ID
    assert "step_index" in event
    assert "timestamp" in event
    assert "payload" in event

    _reset_sse_queues()


# ---------------------------------------------------------------------------
# Test 4: SSE envelope always has all required fields (AC3)
# ---------------------------------------------------------------------------

def test_envelope_all_required_fields():
    """Canonical envelope must contain event_type, session_id, step_index, timestamp, payload."""
    _reset_sse_queues()

    import services.sse_service as svc

    queue: asyncio.Queue = asyncio.Queue()
    svc._event_queues[_SESSION_ID] = [queue]
    svc.emit_event(_SESSION_ID, "task_complete", {"result": "success"})

    raw = queue.get_nowait()
    event = json.loads(raw)

    required_fields = {"event_type", "session_id", "step_index", "timestamp", "payload"}
    missing = required_fields - set(event.keys())
    assert not missing, f"Missing fields in SSE envelope: {missing}"

    _reset_sse_queues()


# ---------------------------------------------------------------------------
# Test 5: timestamp field is ISO 8601 with Z suffix (AC3)
# ---------------------------------------------------------------------------

def test_timestamp_iso8601_format():
    """timestamp must match YYYY-MM-DDTHH:MM:SS.mmmZ format."""
    _reset_sse_queues()

    import services.sse_service as svc

    queue: asyncio.Queue = asyncio.Queue()
    svc._event_queues[_SESSION_ID] = [queue]
    svc.emit_event(_SESSION_ID, "plan_ready", {})

    raw = queue.get_nowait()
    event = json.loads(raw)
    ts = event["timestamp"]

    # ISO 8601 with milliseconds and Z suffix: 2026-02-26T14:30:00.000Z
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
    assert re.match(pattern, ts), f"timestamp does not match ISO 8601 format: {ts!r}"

    _reset_sse_queues()


# ---------------------------------------------------------------------------
# Test 6: step_index is null when not provided (AC3)
# ---------------------------------------------------------------------------

def test_step_index_null_for_non_step_events():
    """step_index must be None/null for events emitted without a step_index argument."""
    _reset_sse_queues()

    import services.sse_service as svc

    queue: asyncio.Queue = asyncio.Queue()
    svc._event_queues[_SESSION_ID] = [queue]
    svc.emit_event(_SESSION_ID, "plan_ready", {"steps": []})  # no step_index

    raw = queue.get_nowait()
    event = json.loads(raw)

    assert event["step_index"] is None, f"Expected step_index to be null, got {event['step_index']!r}"

    _reset_sse_queues()


# ---------------------------------------------------------------------------
# Test 7: client disconnect → queue is cleaned up (AC4, memory leak prevention)
# ---------------------------------------------------------------------------

def test_unsubscribe_cleans_up_queue():
    """unsubscribe() removes the session_id entry from the _event_queues dict."""
    _reset_sse_queues()

    import services.sse_service as svc

    # Simulate a subscribe by adding a queue for the session
    queue: asyncio.Queue = asyncio.Queue()
    svc._event_queues[_SESSION_ID] = [queue]

    assert _SESSION_ID in svc._event_queues

    svc.unsubscribe(_SESSION_ID)

    assert _SESSION_ID not in svc._event_queues, (
        "unsubscribe() should remove the session entry from _event_queues to prevent memory leak"
    )


# ---------------------------------------------------------------------------
# Test 8: task_router emits plan_ready after planner succeeds (AC2)
# ---------------------------------------------------------------------------

def test_task_router_emits_plan_ready_on_success():
    """start_task endpoint emits 'plan_ready' SSE event after successful planning."""
    _reset_sse_queues()

    mock_session = {
        "session_id": _SESSION_ID,
        "stream_url": f"/api/stream/{_SESSION_ID}",
    }

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=mock_session),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch("routers.task_router.run_planner", new_callable=AsyncMock, return_value=_MOCK_STEP_PLAN),
        patch("routers.task_router.emit_event") as mock_emit,
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Search for cats"},
            headers={"Authorization": "Bearer valid.firebase.token"},
        )

    assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.json()}"

    # Verify emit_event was called with plan_ready
    assert mock_emit.called, "emit_event was not called at all"
    call_args = mock_emit.call_args
    assert call_args[0][1] == "plan_ready", (
        f"Expected emit_event called with 'plan_ready', got {call_args[0][1]!r}"
    )
    assert "steps" in call_args[0][2], "plan_ready payload must contain 'steps'"
    assert "task_summary" in call_args[0][2], "plan_ready payload must contain 'task_summary'"


# ---------------------------------------------------------------------------
# Test 9: task_router emits task_failed on planner failure (AC2, error handling)
# ---------------------------------------------------------------------------

def test_task_router_emits_task_failed_on_planner_error():
    """start_task endpoint emits 'task_failed' SSE event when planner raises an exception."""
    _reset_sse_queues()

    mock_session = {
        "session_id": _SESSION_ID,
        "stream_url": f"/api/stream/{_SESSION_ID}",
    }

    with (
        patch("routers.task_router.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}),
        patch("routers.task_router.create_session", new_callable=AsyncMock, return_value=mock_session),
        patch("routers.task_router.update_session_status", new_callable=AsyncMock),
        patch(
            "routers.task_router.run_planner",
            new_callable=AsyncMock,
            side_effect=Exception("Planner API timeout"),
        ),
        patch("routers.task_router.emit_event") as mock_emit,
    ):
        response = client.post(
            "/api/task/start",
            json={"task_description": "Search for cats"},
            headers={"Authorization": "Bearer valid.firebase.token"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "PLANNER_ERROR"

    # Verify emit_event was called with task_failed
    assert mock_emit.called, "emit_event was not called after Planner failure"
    call_args = mock_emit.call_args
    assert call_args[0][1] == "task_failed", (
        f"Expected emit_event called with 'task_failed', got {call_args[0][1]!r}"
    )


# ---------------------------------------------------------------------------
# Test 10: emit_event formatting over HTTP (API integration)
# ---------------------------------------------------------------------------

def test_stream_integration_payload_formatting():
    """Verify that the payload formatting over HTTP matches data: <json>\\n\\n format."""
    _reset_sse_queues()

    async def _finite_gen(session_id: str):
        yield '{"event_type":"plan_ready","session_id":"sess_mock","step_index":null,"timestamp":"2026-02-26T14:30:00.000Z","payload":{}}'

    with patch("handlers.sse_handler.get_session", new_callable=AsyncMock, return_value=_MOCK_SESSION), \
         patch("handlers.sse_handler.firebase_auth.verify_id_token", return_value={"uid": "test-uid"}), \
         patch("handlers.sse_handler.subscribe", side_effect=_finite_gen):

        response = client.get(f"/api/stream/{_SESSION_ID}", headers={"Authorization": "Bearer valid.token"})
        
        # FastAPI TestClient will consume the finite generator
        assert response.status_code == 200
        text = response.text
        assert ": keepalive" in text
        assert "data: " in text
        assert '{"event_type":"plan_ready"' in text
