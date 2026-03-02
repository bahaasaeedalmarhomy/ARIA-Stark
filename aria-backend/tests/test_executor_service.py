"""
Unit tests for Story 3.2: Playwright Browser Actions — executor_service.run_executor.

AC coverage map:
  AC 1–5 (browser actions)  : Covered by test_playwright_computer.py (PlaywrightComputer methods)
  AC 6 (error handling)     : All tests below

Tests:
  1. run_executor — successful completion calls handle_task_complete once
  2. run_executor — BargeInException emits task_paused SSE; handle_task_complete NOT called
  3. run_executor — retry: action raises twice then succeeds; execution continues
  4. run_executor — retries exhausted: step_error SSE emitted; executor stops
  5. run_executor — pc.stop() always called in finally block (even on exception)
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
    ):
        # Wire up the mock computer
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
        MockPC.return_value = mock_pc

        # Wire up mock session service
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
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
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
        # Suppress retry sleep to keep tests fast
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
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
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
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
        patch("services.executor_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_pc = AsyncMock()
        mock_pc.screenshot = AsyncMock(return_value=b"\x89PNG")
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
