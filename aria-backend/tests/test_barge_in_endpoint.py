"""
Unit tests for POST /api/task/{session_id}/barge-in endpoint and signal_barge_in().

Story 4.4 AC: 1, 2, 3
Tests:
  1. POST /barge-in returns 200 with {"barge_in": true}
  2. After barge-in, get_cancel_flag(session_id).is_set() returns True
  3. After barge-in, is_user_cancel(session_id) returns False (regression guard)
  4. signal_barge_in() sets cancel flag; reset_cancel_flag() clears it
  5. run_executor — barge-in (non-user-cancel) emits task_paused with reason "barge_in"
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test 1: POST /barge-in returns 200 with barge_in: true
# ---------------------------------------------------------------------------

def test_barge_in_returns_200():
    response = client.post("/api/task/sess_barge_in_test/barge-in")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["barge_in"] is True
    assert body["error"] is None


# ---------------------------------------------------------------------------
# Test 2: POST /barge-in sets cancel flag
# ---------------------------------------------------------------------------

def test_barge_in_sets_cancel_flag():
    from services.session_service import get_cancel_flag, reset_cancel_flag

    session_id = "sess_barge_in_cancel_flag_test"
    reset_cancel_flag(session_id)
    assert not get_cancel_flag(session_id).is_set()

    client.post(f"/api/task/{session_id}/barge-in")

    assert get_cancel_flag(session_id).is_set()


# ---------------------------------------------------------------------------
# Test 3: POST /barge-in does NOT set is_user_cancel() (regression guard)
# ---------------------------------------------------------------------------

def test_barge_in_does_not_set_user_cancel_flag():
    from services.session_service import is_user_cancel, reset_cancel_flag, clear_user_cancel_flag

    session_id = "sess_barge_in_no_user_cancel_test"
    reset_cancel_flag(session_id)
    clear_user_cancel_flag(session_id)
    assert not is_user_cancel(session_id)

    client.post(f"/api/task/{session_id}/barge-in")

    # Cancel flag should be set (barge-in), but is_user_cancel must NOT be set
    from services.session_service import get_cancel_flag
    assert get_cancel_flag(session_id).is_set()
    assert not is_user_cancel(session_id)


# ---------------------------------------------------------------------------
# Test 4: signal_barge_in() sets cancel flag; reset_cancel_flag() clears it
# ---------------------------------------------------------------------------

def test_signal_barge_in_and_reset():
    from services.session_service import (
        signal_barge_in, get_cancel_flag, reset_cancel_flag, is_user_cancel
    )

    session_id = "sess_signal_barge_in_test"
    reset_cancel_flag(session_id)
    assert not get_cancel_flag(session_id).is_set()

    signal_barge_in(session_id)

    assert get_cancel_flag(session_id).is_set()
    assert not is_user_cancel(session_id)  # must not set user-cancel

    reset_cancel_flag(session_id)
    assert not get_cancel_flag(session_id).is_set()


# ---------------------------------------------------------------------------
# Test 5: run_executor emits task_paused with reason "barge_in" on barge-in
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_executor_barge_in_emits_task_paused_with_reason():
    """
    When BargeInException is raised and is_user_cancel() is False (voice barge-in),
    task_paused is emitted with reason="barge_in" and status updated to "paused".
    """
    from tools.playwright_computer import BargeInException

    _SESSION_ID = "sess_barge_in_reason_exec_test"

    _SAMPLE_STEP_PLAN = {
        "task_summary": "Test task",
        "steps": [
            {
                "step_index": 0,
                "description": "Navigate",
                "action": "navigate",
                "target": "https://example.com",
                "value": "",
                "confidence": 0.9,
                "is_destructive": False,
                "requires_user_input": False,
                "user_input_reason": "",
            }
        ],
    }

    mock_adk_session = MagicMock()
    mock_adk_session.id = "adk-session-barge-in-z"

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock),
        patch("services.executor_service.update_session_status", new_callable=AsyncMock) as mock_update,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.is_user_cancel", return_value=False),
        patch("services.executor_service.clear_user_cancel_flag"),
        patch("services.executor_service.set_paused_step"),
        # Prevent actual replan coroutine from running in test
        patch("services.replan_service.wait_for_voice_instruction_and_replan", new_callable=AsyncMock),
        patch("asyncio.create_task"),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        async def _raise_barge_in(**kwargs):
            raise BargeInException("barge-in")
            yield

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _raise_barge_in(**kw))
        MockRunner.return_value = mock_runner

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, _SAMPLE_STEP_PLAN)

    # task_paused emitted, NOT task_failed
    paused_calls = [c for c in mock_emit.call_args_list if c.args[1] == "task_paused"]
    failed_calls = [c for c in mock_emit.call_args_list if c.args[1] == "task_failed"]
    assert len(paused_calls) == 1, "Expected exactly 1 task_paused event"
    assert len(failed_calls) == 0, "Expected 0 task_failed events for barge-in"

    # Verify reason: "barge_in" is in the payload
    payload = paused_calls[0].args[2]
    assert payload.get("reason") == "barge_in", f"Expected reason='barge_in', got {payload}"

    # Status updated to "paused"
    paused_update_calls = [c for c in mock_update.call_args_list if "paused" in c.args]
    assert len(paused_update_calls) == 1
