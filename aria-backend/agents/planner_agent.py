"""
Planner agent — implemented in Story 2.1.

Uses google-adk LlmAgent with Gemini model configured for Vertex AI Express.
The ADK runner auto-picks up env var GOOGLE_GENAI_USE_VERTEXAI=true.
If ADK auto-config fails with 401, the planner_service.py fallback calls genai.Client directly.
"""
from google.adk.agents import LlmAgent
from google.genai import types as genai_types

from prompts.planner_system import PLANNER_SYSTEM_PROMPT

planner_agent = LlmAgent(
    name="planner",
    model="gemini-3.1-pro-preview",
    instruction=PLANNER_SYSTEM_PROMPT,
    generate_content_config=genai_types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
    ),
)
