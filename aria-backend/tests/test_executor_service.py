"""
Unit tests for executor_service.run_executor.

Story 3.2 AC coverage:
  AC 1-5 (browser actions)  : Covered by test_playwright_computer.py (PlaywrightComputer methods)
  AC 6 (error handling)     : Tests 1-5 below

Story 3.3 AC coverage:
  AC 1 (step_start SSE)     : Test 6 — step_start emitted per step with correct payload
  AC 2 (step_complete SSE)  : Test 7 — step_complete with screenshot_url; Test 8 — empty URL maps to None

Tests:
  1. run_executor — successful completion calls handle_task_complete once
  2. run_executor — BargeInException emits task_paused SSE; handle_task_complete NOT called
  3. run_executor — retry: action raises twice then succeeds; execution continues
  4. run_executor — retries exhausted: step_error SSE emitted; executor stops
  5. run_executor — pc.stop() always called in finally block (even on exception)
  6. run_executor — step_start emitted for each step with correct payload (Story 3.3 AC 1)
  7. run_executor — step_complete emitted with screenshot_url (Story 3.3 AC 2)
  8. run_executor — step_complete with empty screenshot_url uses None (Story 3.3 AC 2)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

# ─────────────────────────────── Fixtures ────────────────────────────────────

_SAMPLE_STEP_PLAN = {
    "task_summary": "Buy a widget",
    "steps": [
        {
            "step_index": 0,
            "description": "Navigate to shop",
            "action": "navigate",
            "target": "https://shop.example.com",
            "value": "",
            "confidence": 0.9,
            "is_destructive": False,
            "requires_user_input": False,
            "user_input_reason": "",
        },
        {
            "step_index": 1,
            "description": "Click buy button",
            "action": "click",
            "target": "#buy-btn",
            "value": "",
            "confidence": 0.85,
            "is_destructive": False,
            "requires_user_input": False,
            "user_input_reason": "",
        },
    ],
}

_SESSION_ID = "sess_test-executor-001"


def _make_mock_adk_session():
    """Create a mock ADK session with an id attribute."""
    session = MagicMock()
    session.id = "adk-session-001"
    return session


# ─────────────────────────────── Test 1 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_success_calls_handle_task_complete():
    """
    When the ADK runner completes all steps successfully,
    handle_task_complete must be called exactly once (AC: 6 success path).
    """
    mock_adk_session = _make_mock_adk_session()

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent") as MockLlmAgent,
        patch("services.executor_service.ComputerUseToolset") as MockCUT,
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value="https://storage.googleapis.com/bucket/sessions/sess/steps/0000.png"),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        # Wire runner to yield no events (success) — fresh generator per call
        async def _no_events(**kwargs):
            return
            yield  # make it an async generator

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _no_events(**kw))
        MockRunner.return_value = mock_runner

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, _SAMPLE_STEP_PLAN)

    mock_htc.assert_called_once_with(
        _SESSION_ID, steps_completed=len(_SAMPLE_STEP_PLAN["steps"])
    )
    # No error events should have been emitted
    for emit_call in mock_emit.call_args_list:
        assert emit_call.args[1] not in ("task_paused", "step_error", "task_failed"), (
            f"Unexpected error event emitted: {emit_call}"
        )


# ─────────────────────────────── Test 2 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_barge_in_emits_task_paused_and_skips_handle_complete():
    """
    When BargeInException is raised during runner.run_async,
    task_paused SSE is emitted and handle_task_complete is NOT called (AC: 6).
    """
    from tools.playwright_computer import BargeInException

    mock_adk_session = _make_mock_adk_session()

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent") as MockLlmAgent,
        patch("services.executor_service.ComputerUseToolset") as MockCUT,
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.update_session_status", new_callable=AsyncMock) as mock_update_status,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        # Runner raises BargeInException on first step
        async def _barge_in(**kwargs):
            raise BargeInException("cancelled")
            yield  # make it an async generator

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _barge_in(**kw))
        MockRunner.return_value = mock_runner

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, _SAMPLE_STEP_PLAN)

    # Must emit task_paused
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "task_paused" in emit_types, f"Expected 'task_paused' in {emit_types}"

    # Must update Firestore status to paused (H1 fix)
    mock_update_status.assert_called_once_with(_SESSION_ID, "paused")

    # Must NOT call handle_task_complete
    mock_htc.assert_not_called()

    # pc.stop() must still be called
    mock_pc.stop.assert_called_once()


# ─────────────────────────────── Test 3 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_retry_succeeds_on_third_attempt():
    """
    When an action raises on attempts 1 and 2 but succeeds on attempt 3,
    execution should continue without emitting an error event (AC: 6 retry path).
    """
    mock_adk_session = _make_mock_adk_session()

    attempt_counter = {"n": 0}

    async def _flaky_gen(*args, **kwargs):
        attempt_counter["n"] += 1
        if attempt_counter["n"] < 3:
            raise RuntimeError("transient error")
        # Third attempt: success — yield nothing
        return
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent") as MockLlmAgent,
        patch("services.executor_service.ComputerUseToolset") as MockCUT,
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        # Suppress retry sleep to keep tests fast
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        # Each call to run_async returns a new generator (one per attempt per step)
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _flaky_gen(**kw))
        MockRunner.return_value = mock_runner

        # Only test with the first step to keep things simple
        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # No step_error or task_failed events should be emitted
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "step_error" not in emit_types, f"Unexpected step_error in {emit_types}"
    assert "task_failed" not in emit_types, f"Unexpected task_failed in {emit_types}"

    # handle_task_complete should have been called (success after retry)
    mock_htc.assert_called_once()


# ─────────────────────────────── Test 4 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_exhausted_retries_emits_step_error():
    """
    When all 3 attempts raise, step_error SSE is emitted with correct payload
    and the executor stops (handle_task_complete NOT called) (AC: 6).

    In Story 3.4's new flow, after step_error is emitted the executor waits for
    user input via _wait_for_user_input. We mock it to return None (simulating
    the 300s timeout path) so the executor returns without hanging in the test.
    """
    mock_adk_session = _make_mock_adk_session()

    async def _always_fail(*args, **kwargs):
        raise RuntimeError("persistent error")
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent") as MockLlmAgent,
        patch("services.executor_service.ComputerUseToolset") as MockCUT,
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.update_session_status", new_callable=AsyncMock) as mock_update_status,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
        patch("services.executor_service._wait_for_user_input", new_callable=AsyncMock, return_value=None),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _always_fail(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # step_error must be emitted with step_index and error fields
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "step_error" in emit_types, f"Expected 'step_error' in {emit_types}"

    step_error_call = next(c for c in mock_emit.call_args_list if c.args[1] == "step_error")
    payload = step_error_call.args[2]
    assert "step_index" in payload
    assert "error" in payload
    assert "description" in payload

    # Must update Firestore status to error (H1 fix)
    mock_update_status.assert_called_once_with(_SESSION_ID, "error")

    # handle_task_complete must NOT be called (executor stopped early)
    mock_htc.assert_not_called()


# ─────────────────────────────── Test 5 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_pc_stop_called_in_finally():
    """
    pc.stop() must be called even when an unhandled exception occurs,
    ensuring browser resources are always cleaned up (AC: 6).

    Story 3.4: The RuntimeError exhausts generic retries → step_error → _wait_for_user_input.
    We mock _wait_for_user_input to return None (timeout path) so the test exits quickly.
    """
    mock_adk_session = _make_mock_adk_session()

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent") as MockLlmAgent,
        patch("services.executor_service.ComputerUseToolset") as MockCUT,
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event"),
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock),
        patch("services.executor_service.update_session_status", new_callable=AsyncMock),
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
        patch("services.executor_service._wait_for_user_input", new_callable=AsyncMock, return_value=None),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        # Simulate an unrecoverable exception from the runner
        async def _crash(*args, **kwargs):
            raise RuntimeError("catastrophic failure")
            yield

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _crash(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        # Should NOT raise — exception is caught and task_failed is emitted
        await run_executor(_SESSION_ID, plan)

    # pc.stop() MUST have been called despite the exception
    mock_pc.stop.assert_called_once()


# ─────────────────────────────── Test 6 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_emits_step_start_for_each_step():
    """
    step_start SSE is emitted for each step with correct step_index, action_type,
    description, and confidence before the ADK runner executes the step (AC: 1).
    """
    mock_adk_session = _make_mock_adk_session()

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock),
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        async def _no_events(**kwargs):
            return
            yield

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _no_events(**kw))
        MockRunner.return_value = mock_runner

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, _SAMPLE_STEP_PLAN)

    # Extract all step_start calls
    step_start_calls = [c for c in mock_emit.call_args_list if c.args[1] == "step_start"]
    assert len(step_start_calls) == len(_SAMPLE_STEP_PLAN["steps"]), (
        f"Expected {len(_SAMPLE_STEP_PLAN['steps'])} step_start events, got {len(step_start_calls)}"
    )

    for i, step in enumerate(_SAMPLE_STEP_PLAN["steps"]):
        payload = step_start_calls[i].args[2]
        assert payload["step_index"] == step["step_index"]
        assert payload["action_type"] == step["action"]
        assert payload["description"] == step["description"]
        assert payload["confidence"] == step["confidence"]


# ─────────────────────────────── Test 7 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_emits_step_complete_with_screenshot_url():
    """
    step_complete SSE is emitted after each successful step with screenshot_url
    returned by upload_screenshot (AC: 2).
    """
    mock_adk_session = _make_mock_adk_session()
    expected_url = "https://storage.googleapis.com/bucket/sessions/sess/steps/0000.png"

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock),
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=expected_url),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        async def _no_events(**kwargs):
            return
            yield

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _no_events(**kw))
        MockRunner.return_value = mock_runner

        # Use single step for simplicity
        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    step_complete_calls = [c for c in mock_emit.call_args_list if c.args[1] == "step_complete"]
    assert len(step_complete_calls) == 1, f"Expected 1 step_complete, got {len(step_complete_calls)}"

    payload = step_complete_calls[0].args[2]
    assert payload["step_index"] == 0
    assert payload["screenshot_url"] == expected_url
    assert "result_summary" in payload
    assert "confidence" in payload


# ─────────────────────────────── Test 8 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_run_executor_step_complete_with_empty_screenshot_url_uses_none():
    """
    When upload_screenshot returns "", step_complete is still emitted with
    screenshot_url: None (AC: 2 non-fatal path).
    """
    mock_adk_session = _make_mock_adk_session()

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock),
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        async def _no_events(**kwargs):
            return
            yield

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _no_events(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    step_complete_calls = [c for c in mock_emit.call_args_list if c.args[1] == "step_complete"]
    assert len(step_complete_calls) == 1

    payload = step_complete_calls[0].args[2]
    # "" maps to None in the payload (screenshot_url or None)
    assert payload["screenshot_url"] is None, (
        f"Expected None when upload returns '', got {payload['screenshot_url']!r}"
    )


# ─────────────────────────────── Test 9 (Story 3.4) ──────────────────────────

@pytest.mark.asyncio
async def test_run_executor_page_load_timeout_emits_step_error():
    """
    When runner.run_async raises PlaywrightTimeoutError, step_error SSE is emitted
    with message "Page did not load within 15 seconds" and session status is set to
    "error". No retry is attempted (AC: 1).

    _wait_for_user_input is mocked to return None (timeout path) so the test exits fast.
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    mock_adk_session = _make_mock_adk_session()

    async def _timeout_gen(**kwargs):
        raise PlaywrightTimeoutError("Navigation timeout")
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.update_session_status", new_callable=AsyncMock) as mock_update_status,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
        patch("services.executor_service._wait_for_user_input", new_callable=AsyncMock, return_value=None),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _timeout_gen(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # step_error must be emitted with the specific timeout message
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "step_error" in emit_types, f"Expected 'step_error' in {emit_types}"

    step_error_call = next(c for c in mock_emit.call_args_list if c.args[1] == "step_error")
    payload = step_error_call.args[2]
    assert payload["error"] == "Page did not load within 15 seconds", (
        f"Expected timeout message, got: {payload['error']!r}"
    )
    assert "step_index" in payload
    assert "description" in payload

    # Session status must be updated to "error"
    mock_update_status.assert_any_call(_SESSION_ID, "error")

    # handle_task_complete must NOT be called
    mock_htc.assert_not_called()


# ─────────────────────────────── Test 10 (Story 3.4) ─────────────────────────

@pytest.mark.asyncio
async def test_run_executor_gemini_api_error_retries_twice_then_succeeds():
    """
    When runner.run_async raises GoogleAPICallError on first 2 attempts but
    succeeds on attempt 3, asyncio.sleep is called twice with _GEMINI_BACKOFF_SECONDS
    and step_complete is emitted (AC: 2).
    """
    from google.api_core import exceptions as gapi_exceptions

    mock_adk_session = _make_mock_adk_session()

    attempt_counter = {"n": 0}

    async def _gemini_error_twice_gen(**kwargs):
        attempt_counter["n"] += 1
        if attempt_counter["n"] <= 2:
            raise gapi_exceptions.ServiceUnavailable("rate limit")
        return
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _gemini_error_twice_gen(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # No error events — step succeeded on 3rd attempt
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "step_error" not in emit_types, f"Unexpected step_error in {emit_types}"
    assert "task_failed" not in emit_types, f"Unexpected task_failed in {emit_types}"
    assert "step_complete" in emit_types, f"Expected step_complete in {emit_types}"

    # asyncio.sleep called twice with _GEMINI_BACKOFF_SECONDS (1.0)
    from services.executor_service import _GEMINI_BACKOFF_SECONDS
    gemini_sleep_calls = [c for c in mock_sleep.call_args_list if c.args[0] == _GEMINI_BACKOFF_SECONDS]
    assert len(gemini_sleep_calls) == 2, (
        f"Expected 2 Gemini backoff sleeps, got {len(gemini_sleep_calls)}: {mock_sleep.call_args_list}"
    )

    mock_htc.assert_called_once()


# ─────────────────────────────── Test 11 (Story 3.4) ─────────────────────────

@pytest.mark.asyncio
async def test_run_executor_gemini_api_error_exhausted_emits_task_failed():
    """
    When runner.run_async always raises GoogleAPICallError, after 3 total attempts
    (> _GEMINI_MAX_RETRIES=2) task_failed SSE is emitted and executor returns (AC: 2).
    """
    from google.api_core import exceptions as gapi_exceptions

    mock_adk_session = _make_mock_adk_session()

    async def _always_gemini_error(**kwargs):
        raise gapi_exceptions.ServiceUnavailable("rate limit exhausted")
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.update_session_status", new_callable=AsyncMock) as mock_update_status,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        mock_pc.detect_captcha = AsyncMock(return_value=False)
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _always_gemini_error(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # task_failed (NOT step_error) must be emitted
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "task_failed" in emit_types, f"Expected 'task_failed' in {emit_types}"
    assert "step_error" not in emit_types, f"Unexpected step_error in {emit_types}"

    # Session status must be updated to "failed"
    mock_update_status.assert_any_call(_SESSION_ID, "failed")

    # handle_task_complete NOT called
    mock_htc.assert_not_called()


# ─────────────────────────────── Test 12 (Story 3.4) ─────────────────────────

@pytest.mark.asyncio
async def test_run_executor_captcha_detected_emits_awaiting_input_then_retries():
    """
    When detect_captcha() returns True after a successful step action,
    awaiting_input SSE is emitted with captcha_detected reason; after user
    input arrives the step is retried and completes with step_complete (AC: 3).
    """
    mock_adk_session = _make_mock_adk_session()

    # Captcha detected on first pass, not on second (after user solved it)
    captcha_call_count = {"n": 0}

    async def _no_events(**kwargs):
        return
        yield

    with (
        patch("services.executor_service.PlaywrightComputer") as MockPC,
        patch("services.executor_service.LlmAgent"),
        patch("services.executor_service.ComputerUseToolset"),
        patch("services.executor_service.InMemorySessionService") as MockSessionSvc,
        patch("services.executor_service.Runner") as MockRunner,
        patch("services.executor_service.emit_event") as mock_emit,
        patch("services.executor_service.build_executor_context", return_value="ctx"),
        patch("services.executor_service.handle_task_complete", new_callable=AsyncMock) as mock_htc,
        patch("services.executor_service.upload_screenshot", new_callable=AsyncMock, return_value=""),
        patch("services.executor_service._wait_for_user_input", new_callable=AsyncMock, return_value="captcha solved") as mock_wait,
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")

        async def _detect_captcha_once():
            captcha_call_count["n"] += 1
            return captcha_call_count["n"] == 1  # True on first call, False on second

        mock_pc.detect_captcha = _detect_captcha_once
        MockPC.return_value = mock_pc

        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value=mock_adk_session)
        MockSessionSvc.return_value = mock_svc

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(side_effect=lambda **kw: _no_events(**kw))
        MockRunner.return_value = mock_runner

        plan = {"task_summary": "t", "steps": [_SAMPLE_STEP_PLAN["steps"][0]]}

        from services.executor_service import run_executor
        await run_executor(_SESSION_ID, plan)

    # awaiting_input must have been emitted with captcha_detected reason
    emit_types = [c.args[1] for c in mock_emit.call_args_list]
    assert "awaiting_input" in emit_types, f"Expected 'awaiting_input' in {emit_types}"

    awaiting_call = next(c for c in mock_emit.call_args_list if c.args[1] == "awaiting_input")
    payload = awaiting_call.args[2]
    assert payload.get("reason") == "captcha_detected", f"Expected captcha_detected, got {payload}"
    assert "message" in payload

    # _wait_for_user_input was called with paused_with="captcha"
    mock_wait.assert_called_once()
    assert mock_wait.call_args.kwargs.get("paused_with") == "captcha" or \
           (len(mock_wait.call_args.args) >= 3 and mock_wait.call_args.args[2] == "captcha"), \
           f"Expected paused_with='captcha', got: {mock_wait.call_args}"

    # After user resolved CAPTCHA, step_complete is eventually emitted
    assert "step_complete" in emit_types, f"Expected step_complete after CAPTCHA retry in {emit_types}"

    # handle_task_complete called (full success)
    mock_htc.assert_called_once()
