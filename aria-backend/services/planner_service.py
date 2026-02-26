"""
Planner service — implemented in Story 2.1.

Provides run_planner() which calls the Planner agent (or falls back to direct genai.Client
call if ADK auto-config isn't compatible with Vertex AI Express keys), validates the response
against the canonical step plan schema, and returns the parsed dict.

Per NFR15: Gemini API errors retry max 2 times with 1 second backoff.
"""
import asyncio
import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import types as genai_types

from prompts.planner_system import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Required fields for each step in the canonical schema
_REQUIRED_STEP_FIELDS = {
    "step_index",
    "description",
    "action",
    "target",
    "value",
    "confidence",
    "is_destructive",
    "requires_user_input",
    "user_input_reason",
}

# Valid action types per spec
_VALID_ACTIONS = {"navigate", "click", "type", "scroll", "screenshot", "wait"}


def _validate_step_plan(plan: dict) -> None:
    """
    Validate that plan matches the canonical step plan schema.
    Raises ValueError if any required field is missing or has wrong type.
    """
    if "task_summary" not in plan:
        raise ValueError("Missing required field: task_summary")
    if not isinstance(plan.get("task_summary"), str):
        raise ValueError("task_summary must be a string")
    if "steps" not in plan:
        raise ValueError("Missing required field: steps")
    if not isinstance(plan.get("steps"), list):
        raise ValueError("steps must be an array")

    for i, step in enumerate(plan["steps"]):
        missing = _REQUIRED_STEP_FIELDS - set(step.keys())
        if missing:
            raise ValueError(f"Step {i} missing required fields: {missing}")

        # Validate step_index is an integer
        if not isinstance(step["step_index"], int):
            raise ValueError(f"Step {i} step_index must be an int, got {type(step['step_index']).__name__}")

        if step["action"] not in _VALID_ACTIONS:
            raise ValueError(
                f"Step {i} has invalid action '{step['action']}'. "
                f"Must be one of: {_VALID_ACTIONS}"
            )

        confidence = step["confidence"]
        if not isinstance(confidence, (int, float)):
            raise ValueError(f"Step {i} confidence must be a number, got {type(confidence)}")
        if not (0.0 <= float(confidence) <= 1.0):
            raise ValueError(f"Step {i} confidence {confidence} is out of range [0.0, 1.0]")

        # Validate boolean fields
        if not isinstance(step["is_destructive"], bool):
            raise ValueError(f"Step {i} is_destructive must be a bool, got {type(step['is_destructive']).__name__}")
        if not isinstance(step["requires_user_input"], bool):
            raise ValueError(f"Step {i} requires_user_input must be a bool, got {type(step['requires_user_input']).__name__}")


# Cached genai client — reused across invocations to avoid connection churn
_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    """Return a cached google-genai client using Vertex AI Express key."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(vertexai=True, api_key=api_key)
    return _client


async def run_planner(
    task_description: str,
    context: Optional[str] = None,
    page_content: Optional[str] = None,
) -> dict:
    """
    Invoke the Planner agent and return a validated canonical step plan.

    Args:
        task_description: The raw user task string
        context: Optional supplementary context (FR3) — form field values, URLs, etc.
        page_content: Optional page HTML/text — wrapped in <page_content> XML tags

    Returns:
        Parsed and validated step plan dict matching the canonical schema

    Raises:
        ValueError: If the response does not match the canonical schema
        RuntimeError: If all retries fail (re-raised from last attempt)
    """
    # Build the user prompt
    parts = [f"Task: {task_description}"]
    if context:
        parts.append(f"\nSupplementary context:\n{context}")
    if page_content:
        parts.append(f"\n<page_content>\n{page_content}\n</page_content>")
    user_prompt = "\n".join(parts)

    return await _call_planner_with_retry(user_prompt, max_retries=2)


async def _call_planner_with_retry(user_prompt: str, max_retries: int = 2) -> dict:
    """
    Call the Planner model with retry logic (NFR15: max 2 retries, 1s backoff).
    Uses the direct genai.Client approach for Vertex AI Express key compatibility.

    Only API/network errors are retried. Schema validation errors (ValueError)
    are raised immediately — retrying a deterministic model won't fix bad output.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            result_text = await _invoke_planner(user_prompt)

            # Parse JSON response
            try:
                plan = json.loads(result_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Planner returned non-JSON response: {e}\nResponse: {result_text[:500]}")

            # Validate against canonical schema — ValueError propagates immediately
            _validate_step_plan(plan)

            return plan

        except ValueError:
            # Schema / parse errors — retrying won't help
            raise

        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                logger.warning(
                    "Planner attempt %d/%d failed: %s. Retrying in 1s...",
                    attempt + 1,
                    max_retries + 1,
                    str(e),
                )
                await asyncio.sleep(1)
            else:
                logger.error(
                    "Planner failed after %d attempts: %s",
                    max_retries + 1,
                    str(e),
                )

    raise last_exc  # type: ignore[misc]


async def _invoke_planner(user_prompt: str) -> str:
    """
    Perform the actual Planner API call.
    Uses genai.Client directly (vertexai=True) for Vertex AI Express key compatibility.
    Runs the blocking SDK call in a thread pool to avoid blocking the event loop.
    """
    def _sync_call() -> str:
        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=PLANNER_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        return response.text

    return await asyncio.to_thread(_sync_call)
