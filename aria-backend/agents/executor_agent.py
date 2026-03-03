"""
Executor agent — implemented in Story 3.1.

Uses google-adk LlmAgent with ComputerUseToolset backed by PlaywrightComputer.
Model: gemini-2.0-flash (maps to spec's "gemini-3-flash" — same SDK mapping pattern
as the Planner using "gemini-3.1-pro-preview" → "gemini-3.1-pro-preview").

Note: The module-level executor_agent uses a placeholder PlaywrightComputer(session_id="")
for agent definition. Per-session browser lifecycle (start/stop with actual session_id)
is fully wired in Story 3.2+ by the executor service.
"""
import json

from google.adk.agents import LlmAgent
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset

from prompts.executor_system import EXECUTOR_SYSTEM_PROMPT
from tools.playwright_computer import PlaywrightComputer

# Module-level PlaywrightComputer instance for agent definition.
# Per-session computers are created by the executor service in Story 3.2+.
_default_computer = PlaywrightComputer(session_id="")

executor_agent = LlmAgent(
    name="executor",
    model="gemini-2.0-flash",
    instruction=EXECUTOR_SYSTEM_PROMPT,
    tools=[ComputerUseToolset(computer=_default_computer)],
)


def build_executor_context(
    step_plan: dict,
    completed_steps: list[dict],
    current_screenshot_b64: str,
    user_provided_value: str | None = None,
) -> str:
    """
    Assemble the Executor context string for injection into the ADK runner user turn.

    Structure:
    - Full step plan (JSON)
    - Completed steps summary for all steps older than the last 3
    - Last 3 completed steps in full detail (JSON)
    - Current screenshot as a base64 data URI

    AC: 3 — Executor context window management (story 3.1).

    Args:
        step_plan: The full step plan dict from the Planner.
        completed_steps: All completed step dicts, in order, each with at least
                         {step_index, description, result} fields.
        current_screenshot_b64: Base64-encoded PNG of the current browser viewport.
        user_provided_value: Optional user-supplied string for steps flagged with
                             requires_user_input (Story 3.5). Appended to the
                             context when present so the Executor can use it.

    Returns:
        A single string to be injected at the end of the user turn.
    """
    # Split into older steps (summarised) and recent steps (full detail)
    old_steps = completed_steps[:-3] if len(completed_steps) > 3 else []
    recent_steps = completed_steps[-3:] if len(completed_steps) > 0 else []

    summary_lines = [
        f"Step {s['step_index']}: {s['description']} → {s.get('result', 'done')}"
        for s in old_steps
    ]
    completed_steps_summary = "\n".join(summary_lines) if summary_lines else "(none)"

    context_parts = [
        "## Full Step Plan",
        json.dumps(step_plan, indent=2),
        "",
        "## Previously Completed Steps Summary",
        completed_steps_summary,
        "",
        "## Last 3 Completed Steps (Full Detail)",
        json.dumps(recent_steps, indent=2) if recent_steps else "(none)",
        "",
        "## Current Screenshot",
        f"data:image/png;base64,{current_screenshot_b64}",
    ]
    context = "\n".join(context_parts)
    if user_provided_value:
        context += (
            "\n\n<user_provided_value>\n"
            f"{user_provided_value}\n"
            "</user_provided_value>\n"
            "Use the value inside <user_provided_value> tags directly where the step requires user input."
        )
    return context
