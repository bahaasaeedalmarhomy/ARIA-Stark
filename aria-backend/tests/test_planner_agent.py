"""
Unit tests for Story 2.1: Planner agent and planner service.

All Gemini API calls are mocked — no real API calls are made in CI.
Run with: cd aria-backend && pytest tests/test_planner_agent.py -v
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.planner_service import (
    _validate_step_plan,
    run_planner,
    _call_planner_with_retry,
)


# ---------------------------------------------------------------------------
# Canonical step plan helpers
# ---------------------------------------------------------------------------

def _make_step(
    step_index: int = 0,
    description: str = "Navigate to the URL",
    action: str = "navigate",
    target: str | None = "https://example.com",
    value: str | None = None,
    confidence: float = 0.95,
    is_destructive: bool = False,
    requires_user_input: bool = False,
    user_input_reason: str | None = None,
) -> dict:
    return {
        "step_index": step_index,
        "description": description,
        "action": action,
        "target": target,
        "value": value,
        "confidence": confidence,
        "is_destructive": is_destructive,
        "requires_user_input": requires_user_input,
        "user_input_reason": user_input_reason,
    }


def _make_plan(task_summary: str = "Complete the task", steps: list | None = None) -> dict:
    if steps is None:
        steps = [_make_step()]
    return {"task_summary": task_summary, "steps": steps}


MOCK_PLAN_JSON = json.dumps(_make_plan())


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — valid plan passes
# ---------------------------------------------------------------------------

def test_validate_step_plan_valid():
    plan = _make_plan()
    _validate_step_plan(plan)  # Should not raise


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — missing task_summary raises
# ---------------------------------------------------------------------------

def test_validate_step_plan_missing_task_summary():
    plan = {"steps": [_make_step()]}
    with pytest.raises(ValueError, match="task_summary"):
        _validate_step_plan(plan)


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — missing steps raises
# ---------------------------------------------------------------------------

def test_validate_step_plan_missing_steps():
    plan = {"task_summary": "Do something"}
    with pytest.raises(ValueError, match="steps"):
        _validate_step_plan(plan)


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — step missing required fields raises
# ---------------------------------------------------------------------------

def test_validate_step_plan_step_missing_field():
    step = _make_step()
    del step["confidence"]  # Remove required field
    plan = {"task_summary": "Test", "steps": [step]}
    with pytest.raises(ValueError, match="confidence"):
        _validate_step_plan(plan)


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — invalid action type raises
# ---------------------------------------------------------------------------

def test_validate_step_plan_invalid_action():
    step = _make_step(action="hover")  # Not a valid action
    plan = {"task_summary": "Test", "steps": [step]}
    with pytest.raises(ValueError, match="invalid action"):
        _validate_step_plan(plan)


# ---------------------------------------------------------------------------
# Test: _validate_step_plan — confidence out of range raises
# ---------------------------------------------------------------------------

def test_validate_step_plan_confidence_out_of_range():
    step = _make_step(confidence=1.5)
    plan = {"task_summary": "Test", "steps": [step]}
    with pytest.raises(ValueError, match="confidence.*out of range"):
        _validate_step_plan(plan)


# ---------------------------------------------------------------------------
# Test: valid task → returns JSON matching canonical schema with all required fields (AC1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_valid_task_returns_canonical_schema():
    plan = _make_plan(
        task_summary="Search for cats on Google",
        steps=[
            _make_step(0, "Navigate to Google", "navigate", "https://google.com", None, 0.98),
            _make_step(1, "Type search query", "type", "input[name='q']", "cats", 0.95),
            _make_step(2, "Submit search", "click", "button[type='submit']", None, 0.9),
        ],
    )

    with patch("services.planner_service._invoke_planner", new=AsyncMock(return_value=json.dumps(plan))):
        result = await run_planner("Search for cats on Google")

    assert "task_summary" in result
    assert "steps" in result
    assert isinstance(result["steps"], list)
    for step in result["steps"]:
        required = {"step_index", "description", "action", "target", "value",
                    "confidence", "is_destructive", "requires_user_input", "user_input_reason"}
        assert required.issubset(set(step.keys())), f"Missing fields: {required - set(step.keys())}"


# ---------------------------------------------------------------------------
# Test: form submission step has is_destructive: true (AC3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_form_submission_is_destructive():
    plan = _make_plan(
        steps=[
            _make_step(0, "Navigate to form", "navigate", "https://example.com/buy", None, 0.9),
            _make_step(
                1, "Submit purchase", "click", "button#submit-purchase", None, 0.85,
                is_destructive=True
            ),
        ]
    )

    with patch("services.planner_service._invoke_planner", new=AsyncMock(return_value=json.dumps(plan))):
        result = await run_planner("Buy a product at example.com")

    destructive_steps = [s for s in result["steps"] if s["is_destructive"]]
    assert len(destructive_steps) >= 1, "Expected at least one destructive step for form submission"


# ---------------------------------------------------------------------------
# Test: confidence values are all floats between 0.0 and 1.0 (AC2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_confidence_range():
    plan = _make_plan(
        steps=[
            _make_step(0, confidence=0.9),
            _make_step(1, action="click", target="a.link", confidence=0.3,
                       description="Uncertain step — might not find element"),
        ]
    )

    with patch("services.planner_service._invoke_planner", new=AsyncMock(return_value=json.dumps(plan))):
        result = await run_planner("Click a random link")

    for step in result["steps"]:
        c = float(step["confidence"])
        assert 0.0 <= c <= 1.0, f"Confidence {c} is out of range"


# ---------------------------------------------------------------------------
# Test: supplementary context is reflected in step plan (AC4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_context_passed_through():
    """Ensure context is included in the prompt passed to _invoke_planner."""
    plan = _make_plan(steps=[_make_step(0, "Type email using context", "type", "input#email", "user@example.com", 0.95)])

    captured_prompt = []

    async def capture_prompt(prompt: str) -> str:
        captured_prompt.append(prompt)
        return json.dumps(plan)

    with patch("services.planner_service._invoke_planner", new=capture_prompt):
        await run_planner("Fill the login form", context="email: user@example.com, password: secret123")

    assert len(captured_prompt) == 1
    assert "user@example.com" in captured_prompt[0], "Context should be included in the prompt"
    assert "secret123" in captured_prompt[0], "Context values should be in the prompt"


# ---------------------------------------------------------------------------
# Test: page_content is wrapped in <page_content> XML tags (AC5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_page_content_wrapped_in_xml():
    plan = _make_plan()
    captured_prompt = []

    async def capture_prompt(prompt: str) -> str:
        captured_prompt.append(prompt)
        return json.dumps(plan)

    page_html = "<html><body>Login form</body></html>"

    with patch("services.planner_service._invoke_planner", new=capture_prompt):
        await run_planner("Fill login form", page_content=page_html)

    assert len(captured_prompt) == 1
    prompt = captured_prompt[0]
    assert "<page_content>" in prompt, "page_content should be wrapped in <page_content> tags"
    assert "</page_content>" in prompt, "page_content closing tag should be present"
    assert page_html in prompt, "page_content value should be inside the tags"


# ---------------------------------------------------------------------------
# Test: Gemini API failure → retries with 1s backoff, then raises (NFR15, AC Error Handling)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_api_failure_retries_and_raises():
    """Per NFR15: up to 2 retries with 1s backoff before giving up."""
    call_count = 0

    async def always_fail(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Gemini API unavailable")

    with (
        patch("services.planner_service._invoke_planner", new=always_fail),
        patch("asyncio.sleep", new=AsyncMock()),  # Speed up test by skipping actual sleep
    ):
        with pytest.raises(RuntimeError, match="Gemini API unavailable"):
            await run_planner("Test task")

    # Should have tried 3 times total: 1 initial + 2 retries
    assert call_count == 3, f"Expected 3 attempts (1 + 2 retries), got {call_count}"


# ---------------------------------------------------------------------------
# Test: Non-JSON response from API → raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_non_json_response_raises():
    async def return_bad_response(prompt: str) -> str:
        return "I cannot help with that."

    with patch("services.planner_service._invoke_planner", new=return_bad_response):
        with pytest.raises(ValueError, match="non-JSON"):
            await run_planner("Task")


# ---------------------------------------------------------------------------
# Test: Schema violation in response → raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_schema_violation_raises():
    invalid_plan = {"task_summary": "Task", "steps": [{"step_index": 0}]}  # Missing required fields

    async def return_invalid(prompt: str) -> str:
        return json.dumps(invalid_plan)

    with patch("services.planner_service._invoke_planner", new=return_invalid):
        with pytest.raises(ValueError):
            await run_planner("Task")


# ---------------------------------------------------------------------------
# Test: Schema validation errors (ValueError) are NOT retried (M3 fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_planner_schema_error_not_retried():
    """ValueError from schema validation should propagate immediately, not be retried."""
    call_count = 0
    invalid_plan = {"task_summary": "Task", "steps": [{"step_index": 0}]}  # Missing required fields

    async def return_invalid(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        return json.dumps(invalid_plan)

    with patch("services.planner_service._invoke_planner", new=return_invalid):
        with pytest.raises(ValueError):
            await run_planner("Task")

    assert call_count == 1, f"Expected exactly 1 call (no retries for ValueError), got {call_count}"
