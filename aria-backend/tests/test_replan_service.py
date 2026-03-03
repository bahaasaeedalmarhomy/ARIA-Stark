"""
Unit tests for replan_service — Story 4.4 review fixes.

Tests the voice instruction → re-plan → executor resume flow.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_replan_timeout_emits_task_failed():
    """No voice instruction within timeout → task_failed with barge_in_timeout."""
    sid = "sess_replan_timeout"

    with (
        patch("services.replan_service.get_instruction", new_callable=AsyncMock, return_value=None),
        patch("services.replan_service.emit_event") as mock_emit,
        patch("services.replan_service.update_session_status", new_callable=AsyncMock),
        patch("services.replan_service.release_voice_instruction_queue"),
    ):
        from services.replan_service import wait_for_voice_instruction_and_replan
        await wait_for_voice_instruction_and_replan(sid, 2)

    failed_calls = [c for c in mock_emit.call_args_list if c.args[1] == "task_failed"]
    assert len(failed_calls) == 1
    assert failed_calls[0].args[2]["reason"] == "barge_in_timeout"


@pytest.mark.asyncio
async def test_replan_planner_failure_emits_task_failed():
    """Planner exception during replan → task_failed with replan_planner_failed."""
    sid = "sess_replan_planner_fail"

    with (
        patch(
            "services.replan_service.get_instruction",
            new_callable=AsyncMock,
            return_value="do something else",
        ),
        patch(
            "services.replan_service.get_session",
            new_callable=AsyncMock,
            return_value={"task_description": "original task", "context": ""},
        ),
        patch("services.replan_service.emit_event") as mock_emit,
        patch("services.replan_service.update_session_status", new_callable=AsyncMock),
        patch("services.replan_service.release_voice_instruction_queue"),
        patch(
            "services.planner_service.run_planner",
            new_callable=AsyncMock,
            side_effect=Exception("planner boom"),
        ),
    ):
        from services.replan_service import wait_for_voice_instruction_and_replan
        await wait_for_voice_instruction_and_replan(sid, 1)

    failed_calls = [c for c in mock_emit.call_args_list if c.args[1] == "task_failed"]
    assert len(failed_calls) == 1
    assert failed_calls[0].args[2]["reason"] == "replan_planner_failed"


@pytest.mark.asyncio
async def test_replan_success_emits_plan_ready_and_runs_executor():
    """Successful replan emits plan_ready with is_replan=True and launches executor."""
    sid = "sess_replan_success"
    plan = {
        "steps": [{"step_index": 0, "description": "New step"}],
        "task_summary": "Revised",
    }

    with (
        patch(
            "services.replan_service.get_instruction",
            new_callable=AsyncMock,
            return_value="navigate to dashboard",
        ),
        patch(
            "services.replan_service.get_session",
            new_callable=AsyncMock,
            return_value={"task_description": "go to homepage", "context": ""},
        ),
        patch("services.replan_service.emit_event") as mock_emit,
        patch("services.replan_service.update_session_status", new_callable=AsyncMock),
        patch("services.replan_service.release_voice_instruction_queue"),
        patch("services.replan_service.reset_cancel_flag") as mock_reset,
        patch("services.replan_service.get_browser_instance", return_value=None) as mock_get_pc,
        patch("services.planner_service.run_planner", new_callable=AsyncMock, return_value=plan),
        patch("services.executor_service.run_executor", new_callable=AsyncMock) as mock_exec,
    ):
        from services.replan_service import wait_for_voice_instruction_and_replan
        await wait_for_voice_instruction_and_replan(sid, 2)

    # plan_ready emitted with is_replan=True
    plan_ready_calls = [c for c in mock_emit.call_args_list if c.args[1] == "plan_ready"]
    assert len(plan_ready_calls) == 1
    payload = plan_ready_calls[0].args[2]
    assert payload["is_replan"] is True
    assert payload["steps"] == plan["steps"]

    # Cancel flag cleared before executor launch
    mock_reset.assert_called_once_with(sid)

    # Browser instance retrieved for reuse
    mock_get_pc.assert_called_once_with(sid)

    # Executor launched with correct args
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args
    assert call_args.args[0] == sid
    assert call_args.args[1] == plan
    assert call_args.kwargs.get("existing_pc") is None


@pytest.mark.asyncio
async def test_replan_passes_context_to_planner():
    """Replan preserves original context from session when calling planner."""
    sid = "sess_replan_context"
    plan = {"steps": [], "task_summary": "Revised"}

    with (
        patch(
            "services.replan_service.get_instruction",
            new_callable=AsyncMock,
            return_value="click the blue button",
        ),
        patch(
            "services.replan_service.get_session",
            new_callable=AsyncMock,
            return_value={
                "task_description": "fill out form",
                "context": "The form is at https://example.com/form",
            },
        ),
        patch("services.replan_service.emit_event"),
        patch("services.replan_service.update_session_status", new_callable=AsyncMock),
        patch("services.replan_service.release_voice_instruction_queue"),
        patch("services.replan_service.reset_cancel_flag"),
        patch("services.replan_service.get_browser_instance", return_value=None),
        patch(
            "services.planner_service.run_planner",
            new_callable=AsyncMock,
            return_value=plan,
        ) as mock_planner,
        patch("services.executor_service.run_executor", new_callable=AsyncMock),
    ):
        from services.replan_service import wait_for_voice_instruction_and_replan
        await wait_for_voice_instruction_and_replan(sid, 0)

    mock_planner.assert_called_once()
    call_kwargs = mock_planner.call_args.kwargs
    assert call_kwargs["context"] == "The form is at https://example.com/form"


@pytest.mark.asyncio
async def test_replan_uses_stored_browser_instance():
    """Replan retrieves stored PlaywrightComputer and passes it to run_executor."""
    sid = "sess_replan_browser"
    plan = {"steps": [], "task_summary": "Revised"}
    fake_pc = object()  # simulates a PlaywrightComputer

    with (
        patch(
            "services.replan_service.get_instruction",
            new_callable=AsyncMock,
            return_value="do it differently",
        ),
        patch(
            "services.replan_service.get_session",
            new_callable=AsyncMock,
            return_value={"task_description": "task", "context": ""},
        ),
        patch("services.replan_service.emit_event"),
        patch("services.replan_service.update_session_status", new_callable=AsyncMock),
        patch("services.replan_service.release_voice_instruction_queue"),
        patch("services.replan_service.reset_cancel_flag"),
        patch("services.replan_service.get_browser_instance", return_value=fake_pc),
        patch("services.planner_service.run_planner", new_callable=AsyncMock, return_value=plan),
        patch("services.executor_service.run_executor", new_callable=AsyncMock) as mock_exec,
    ):
        from services.replan_service import wait_for_voice_instruction_and_replan
        await wait_for_voice_instruction_and_replan(sid, 1)

    mock_exec.assert_called_once()
    assert mock_exec.call_args.kwargs.get("existing_pc") is fake_pc
