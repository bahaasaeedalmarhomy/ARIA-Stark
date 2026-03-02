"""
Unit tests for Story 3.1: Executor Agent with ADK SequentialAgent Wiring.

Tests:
  1. executor_agent is an LlmAgent instance
  2. executor_agent.model == "gemini-2.0-flash"
  3. executor_agent.tools contains a ComputerUseToolset instance
  4. executor_agent.instruction contains required key phrases
  5. root_agent.sub_agents == [planner_agent, executor_agent]
  6. build_executor_context with 5 completed steps produces correct output
  7. PlaywrightComputer._check_cancel raises BargeInException when flag is set
  8. PlaywrightComputer.navigate calls _check_cancel before and after page.goto
  9. handle_task_complete updates Firestore status to "complete"
  10. handle_task_complete emits task_complete SSE event with correct payload
  11. handle_task_complete survives Firestore failure (still emits SSE)
  12. handle_task_complete survives SSE failure (does not raise)

AC coverage: AC1 (test 5), AC2 (tests 1-4), AC3 (test 6), AC4 (tests 9-12)
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.adk.agents import LlmAgent
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset

from agents.executor_agent import executor_agent, build_executor_context
from agents.planner_agent import planner_agent
from agents.root_agent import root_agent
from tools.playwright_computer import PlaywrightComputer, BargeInException


# ─────────────────────────────── Test 1 ──────────────────────────────────────

def test_executor_agent_is_llm_agent():
    """executor_agent must be an LlmAgent instance (AC: 2)."""
    assert isinstance(executor_agent, LlmAgent)


# ─────────────────────────────── Test 2 ──────────────────────────────────────

def test_executor_agent_model():
    """executor_agent must use gemini-2.0-flash (AC: 2)."""
    assert executor_agent.model == "gemini-2.0-flash"


# ─────────────────────────────── Test 3 ──────────────────────────────────────

def test_executor_agent_tools_contains_computer_use_toolset():
    """executor_agent.tools must contain a ComputerUseToolset instance (AC: 2)."""
    assert any(isinstance(t, ComputerUseToolset) for t in executor_agent.tools), (
        f"ComputerUseToolset not found in executor_agent.tools: {executor_agent.tools}"
    )


# ─────────────────────────────── Test 4 ──────────────────────────────────────

def test_executor_agent_instruction_key_phrases():
    """executor_agent.instruction must contain required key phrases (AC: 2)."""
    instruction = executor_agent.instruction
    assert instruction, "executor_agent.instruction must not be empty"
    assert "cancel" in instruction.lower(), "Prompt must mention cancel flag"
    assert "one" in instruction.lower() or "one action" in instruction.lower(), (
        "Prompt must mention executing one action per turn"
    )
    assert "page_content" in instruction, "Prompt must mention <page_content> for prompt injection sandboxing"


# ─────────────────────────────── Test 5 ──────────────────────────────────────

def test_root_agent_sub_agents():
    """root_agent.sub_agents must be [planner_agent, executor_agent] (AC: 1)."""
    assert root_agent.sub_agents == [planner_agent, executor_agent], (
        f"root_agent.sub_agents is {root_agent.sub_agents}, expected [planner_agent, executor_agent]"
    )


# ─────────────────────────────── Test 6 ──────────────────────────────────────

def test_build_executor_context_summarises_old_steps():
    """
    build_executor_context with 5 completed steps:
    - Steps 0-1 should appear in completed_steps_summary (summarised)
    - Steps 2-4 should appear in full detail (last 3)
    (AC: 3)
    """
    step_plan = {
        "task_summary": "Buy a product",
        "steps": [{"step_index": i, "description": f"Step {i}"} for i in range(5)],
    }
    completed_steps = [
        {"step_index": i, "description": f"Step {i}", "result": f"result_{i}"}
        for i in range(5)
    ]
    screenshot_b64 = "abc123"

    result = build_executor_context(step_plan, completed_steps, screenshot_b64)

    # Summarised section must contain steps 0 and 1
    assert "Step 0: Step 0 → result_0" in result
    assert "Step 1: Step 1 → result_1" in result

    # Full detail section must contain steps 2, 3, 4
    assert '"step_index": 2' in result
    assert '"step_index": 3' in result
    assert '"step_index": 4' in result

    # Screenshot data URI must be present
    assert f"data:image/png;base64,{screenshot_b64}" in result

    # Full step plan JSON must be present
    assert "Buy a product" in result


def test_build_executor_context_no_old_steps_when_fewer_than_4():
    """With <= 3 completed steps, completed_steps_summary should be (none)."""
    step_plan = {"task_summary": "Test", "steps": []}
    completed_steps = [
        {"step_index": 0, "description": "Step 0", "result": "done"},
    ]
    result = build_executor_context(step_plan, completed_steps, "")
    assert "(none)" in result  # completed_steps_summary is empty


def test_build_executor_context_empty_completed_steps():
    """With no completed steps, both summary and last-3 sections are (none)."""
    step_plan = {"task_summary": "Empty run", "steps": []}
    result = build_executor_context(step_plan, [], "b64data")
    assert result.count("(none)") >= 2  # both sections empty


# ─────────────────────────────── Test 7 ──────────────────────────────────────

def test_check_cancel_raises_barge_in_exception_when_flag_set():
    """PlaywrightComputer._check_cancel must raise BargeInException when cancel flag is set (AC: 2)."""
    computer = PlaywrightComputer(session_id="test-session-cancel")

    with patch("services.session_service.get_cancel_flag") as mock_get_flag:
        mock_event = MagicMock()
        mock_event.is_set.return_value = True
        mock_get_flag.return_value = mock_event

        with pytest.raises(BargeInException):
            computer._check_cancel()


def test_check_cancel_does_not_raise_when_flag_clear():
    """PlaywrightComputer._check_cancel must NOT raise when cancel flag is clear."""
    computer = PlaywrightComputer(session_id="test-session-no-cancel")

    with patch("services.session_service.get_cancel_flag") as mock_get_flag:
        mock_event = MagicMock()
        mock_event.is_set.return_value = False
        mock_get_flag.return_value = mock_event

        # Should not raise
        computer._check_cancel()


# ─────────────────────────────── Test 8 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_navigate_calls_check_cancel_twice():
    """
    PlaywrightComputer.navigate must call _check_cancel both BEFORE and AFTER
    the page.goto await (barge-in pattern — AC: 2).
    """
    computer = PlaywrightComputer(session_id="test-nav")
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"
    mock_page.screenshot = AsyncMock(return_value=b"\x89PNG")
    computer.page = mock_page

    check_count = 0

    def fake_check():
        nonlocal check_count
        check_count += 1

    computer._check_cancel = fake_check
    await computer.navigate("https://example.com")

    # Must have been called exactly twice: before and after page.goto
    assert check_count == 2, f"Expected _check_cancel called 2 times, got {check_count}"
    mock_page.goto.assert_called_once_with(
        "https://example.com", wait_until="networkidle", timeout=15_000
    )


@pytest.mark.asyncio
async def test_navigate_propagates_barge_in_before_goto():
    """BargeInException raised before page.goto must propagate (barge-in before await)."""
    computer = PlaywrightComputer(session_id="test-barge-before")
    mock_page = AsyncMock()
    computer.page = mock_page

    computer._check_cancel = MagicMock(side_effect=BargeInException("cancelled"))

    with pytest.raises(BargeInException):
        await computer.navigate("https://example.com")

    # page.goto should NOT have been called
    mock_page.goto.assert_not_called()


# ─────────────────────────── Tests 9-12: handle_task_complete (AC: 4) ────────

@pytest.mark.asyncio
async def test_handle_task_complete_updates_firestore_status():
    """handle_task_complete must call audit_update_session_status with 'complete' (AC: 4)."""
    from services.task_complete_service import handle_task_complete

    with (
        patch("services.task_complete_service.audit_update_session_status", new_callable=AsyncMock) as mock_audit,
        patch("services.task_complete_service.emit_event") as mock_emit,
    ):
        await handle_task_complete("sess_test-123", 5)

    mock_audit.assert_called_once_with("sess_test-123", "complete")


@pytest.mark.asyncio
async def test_handle_task_complete_emits_sse_event():
    """handle_task_complete must emit task_complete SSE event with correct payload (AC: 4)."""
    from services.task_complete_service import handle_task_complete

    with (
        patch("services.task_complete_service.audit_update_session_status", new_callable=AsyncMock),
        patch("services.task_complete_service.emit_event") as mock_emit,
    ):
        await handle_task_complete("sess_test-456", 7)

    mock_emit.assert_called_once_with(
        "sess_test-456",
        "task_complete",
        {
            "steps_completed": 7,
            "session_id": "sess_test-456",
        },
    )


@pytest.mark.asyncio
async def test_handle_task_complete_survives_firestore_failure():
    """handle_task_complete must still emit SSE even if Firestore update fails (AC: 4)."""
    from services.task_complete_service import handle_task_complete

    with (
        patch(
            "services.task_complete_service.audit_update_session_status",
            new_callable=AsyncMock,
            side_effect=Exception("Firestore down"),
        ),
        patch("services.task_complete_service.emit_event") as mock_emit,
    ):
        await handle_task_complete("sess_fail-fs", 3)

    # SSE event must still have been emitted despite Firestore failure
    mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_handle_task_complete_survives_sse_failure():
    """handle_task_complete must not raise if SSE emit fails (AC: 4)."""
    from services.task_complete_service import handle_task_complete

    with (
        patch("services.task_complete_service.audit_update_session_status", new_callable=AsyncMock) as mock_audit,
        patch("services.task_complete_service.emit_event", side_effect=Exception("SSE broken")),
    ):
        # Should not raise
        await handle_task_complete("sess_fail-sse", 2)

    # Firestore update should still have been attempted
    mock_audit.assert_called_once()
