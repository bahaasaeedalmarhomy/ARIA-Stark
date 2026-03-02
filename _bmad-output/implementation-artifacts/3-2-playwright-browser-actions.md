# Story 3.2: Playwright Browser Actions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want ARIA to navigate, click, type, scroll, and read web pages in a real browser,
So that it can perform any web task on my behalf.

## Acceptance Criteria

1. **Given** the Executor receives a step with `action_type: "navigate"`, **When** it executes the step, **Then** Playwright navigates to the specified URL and waits for `networkidle` (max 15s timeout) before marking the step complete (FR8, FR15).

2. **Given** the Executor receives a step with `action_type: "click"`, **When** it executes the step, **Then** Playwright locates the target element using the bounding box from the Computer Use screenshot interpretation and performs a click; if the element is not found, the step enters retry logic (FR9, FR14).

3. **Given** the Executor receives a step with `action_type: "type"`, **When** it executes the step, **Then** Playwright types the specified text into the targeted input field character by character with a 30ms delay to avoid triggering bot detection (FR10).

4. **Given** the Executor receives a step with `action_type: "scroll"`, **When** it executes the step, **Then** Playwright scrolls the page by the specified pixel delta in the specified direction (FR11).

5. **Given** the Executor receives a step with `action_type: "read"`, **When** it executes the step, **Then** Playwright extracts visible text content from the specified selector or full page and returns it as the step result (FR13).

6. **Given** any Playwright action throws an error, **When** the error is caught, **Then** the Executor re-takes a screenshot, re-evaluates the page state, and retries the action. After 2 retries, it emits a `step_error` SSE event with the error description and pauses for user input (FR16).

## Tasks / Subtasks

- [x] Task 1: Create `aria-backend/services/executor_service.py` with per-session execution loop (AC: 1–6)
  - [x] Import: `LlmAgent`, `ComputerUseToolset`, `EXECUTOR_SYSTEM_PROMPT`, `PlaywrightComputer`, `BargeInException`, `build_executor_context`, `emit_event`, `get_cancel_flag`
  - [x] Implement `async def run_executor(session_id: str, step_plan: dict) -> None`:
    - [x] Create `pc = PlaywrightComputer(session_id=session_id)` then `await pc.start()`; wrap everything in `try/finally` so `await pc.stop()` always fires
    - [x] Build a per-session `LlmAgent` named `f"executor_{session_id}"` using `model="gemini-2.0-flash"`, `instruction=EXECUTOR_SYSTEM_PROMPT`, `tools=[ComputerUseToolset(computer=pc)]` — do NOT reuse the module-level `executor_agent` (it has the placeholder computer)
    - [x] Create an ADK `InMemorySessionService` + `Runner` for this agent; check `google.adk.runners` and `google.adk.sessions` for exact import paths (pattern mirrors what `root_agent.py` shows for ADK agent composition)
    - [x] Assemble initial context string with `build_executor_context(step_plan, completed_steps=[], current_screenshot_b64="")` and send it as the first user message via `runner.run_async()`
    - [x] Iterate the async runner event stream; for each `step_complete`-equivalent event, append to `completed_steps` and call `build_executor_context` with updated state for the next turn
    - [x] On `BargeInException`: log it, emit SSE `task_paused` event with `{"paused_at_step": current_step_index}` via `emit_event`, and `return` cleanly (do NOT re-raise)
    - [x] On any other exception per step: retry up to 2 times; after exhausting retries emit `step_error` SSE event with `{"step_index": N, "error": str(exc), "description": step_description}` and `return` (pause for user input — Story 3.4 wires the resume path)
    - [x] On successful completion call `await handle_task_complete(session_id, steps_completed=len(completed_steps))`

- [x] Task 2: Update `aria-backend/routers/task_router.py` to launch the executor after planning (AC: 1)
  - [x] Add import: `from services.executor_service import run_executor`
  - [x] After step 6 (`update_session_status(session_id, "plan_ready", ...)` succeeds), update session status to `"executing"` via `update_session_status(session_id, "executing")`
  - [x] Launch the executor as a background task: `asyncio.create_task(run_executor(session_id, step_plan))` — do NOT await it; the endpoint returns immediately while the executor runs
  - [x] Add error guard: wrap the `create_task` call in try/except; if it raises, log and emit `task_failed` SSE event then return HTTP 500 (same pattern as the planner error block above it)
  - [x] No change to the final response envelope — `data.step_plan` is already returned; add no new fields

- [x] Task 3: Write unit tests in `aria-backend/tests/test_playwright_computer.py` (AC: 1–6)
  - [x] Test: `PlaywrightComputer.navigate` — mock `page.goto`; assert it's called with `wait_until="networkidle"` and `timeout=15_000` (AC: 1)
  - [x] Test: `PlaywrightComputer.navigate` — assert `_check_cancel` is called before and after `page.goto` (cancel flag guard)
  - [x] Test: `PlaywrightComputer.click` with bbox dict `{x:10, y:20, width:50, height:30}` — mock `page.mouse.click`; assert it's called at center `(35, 35)` (AC: 2)
  - [x] Test: `PlaywrightComputer.click` with CSS selector string — mock `page.click`; assert called with the selector (AC: 2)
  - [x] Test: `PlaywrightComputer.click` retry — mock `page.mouse.click` to raise on first 2 calls and succeed on 3rd; assert no exception raised (retry logic, AC: 6)
  - [x] Test: `PlaywrightComputer.click` exhausted retries — mock `page.mouse.click` to always raise; assert exception propagates after 3 attempts
  - [x] Test: `PlaywrightComputer.type_text` — mock `page.click` and `page.keyboard.type`; assert `delay=30` is passed (AC: 3)
  - [x] Test: `PlaywrightComputer.type_text_at` — mock `page.mouse.click` and `page.keyboard.type`; assert `delay=30` is passed (AC: 3)
  - [x] Test: `PlaywrightComputer.scroll_document("down")` — mock `page.mouse.wheel`; assert called with `delta_y=500` (AC: 4)
  - [x] Test: `PlaywrightComputer.scroll_document("up")` — assert `delta_y=-500` (AC: 4)
  - [x] Test: `PlaywrightComputer.read_page(None)` — mock `page.inner_text`; assert called with `"body"` and output wrapped in `<page_content>` tag (AC: 5)
  - [x] Test: `PlaywrightComputer.read_page("#main")` — assert called with `"#main"` (AC: 5)
  - [x] Test: `BargeInException` is raised when cancel flag is set (already in `test_executor_agent.py` — DO NOT duplicate; reference it in docstring)

- [x] Task 4: Write unit tests for `executor_service.run_executor` in `aria-backend/tests/test_executor_service.py` (AC: 6)
  - [x] Test: `run_executor` — when ADK runner completes successfully, `handle_task_complete` is called once
  - [x] Test: `run_executor` — when `BargeInException` is raised mid-run, `task_paused` SSE event is emitted and `handle_task_complete` is NOT called
  - [x] Test: `run_executor` — when an action raises twice then succeeds (retry), execution continues
  - [x] Test: `run_executor` — when retries exhausted (3rd failure), `step_error` SSE event is emitted and executor stops
  - [x] Test: `run_executor` — `pc.stop()` is always called in finally block (even on exception) — use mock to verify
  - [x] Use `AsyncMock` throughout; mock `PlaywrightComputer.start`, `PlaywrightComputer.stop`, `emit_event`, `handle_task_complete`, ADK Runner

- [x] Task 5: Git commit
  - [x] `git add -A && git commit -m "feat(story-3.2): playwright browser actions executor service"`

## Dev Notes

### Current State — What's Already Done vs. What Story 3.2 Must Build

| File | Current State | Story 3.2 Action |
|---|---|---|
| `tools/playwright_computer.py` | **COMPLETE** — all action methods implemented with cancel checks | No changes needed |
| `tools/playwright_computer.py::BargeInException` | **COMPLETE** | No changes needed |
| `agents/executor_agent.py` | **COMPLETE** — module-level `executor_agent` with `_default_computer=""` placeholder | No changes needed; per-session agent created in executor_service |
| `agents/executor_agent.py::build_executor_context` | **COMPLETE** | Import and use it in executor_service |
| `services/executor_service.py` | **DOES NOT EXIST** | Create from scratch (Task 1) |
| `routers/task_router.py` | Runs planner, returns response — executor never launched | Add `run_executor` background task after plan_ready (Task 2) |
| `tests/test_playwright_computer.py` | **DOES NOT EXIST** | Create from scratch (Task 3) |
| `tests/test_executor_service.py` | **DOES NOT EXIST** | Create from scratch (Task 4) |

**DO NOT TOUCH:**
- `tools/playwright_computer.py` — fully implemented; all story 3.2 ACs are satisfied at the PlaywrightComputer level already
- `agents/executor_agent.py` — module-level agent is correct as-is; per-session agents are created in executor_service
- `agents/root_agent.py` — `SequentialAgent([planner_agent, executor_agent])` is wired correctly; the executor_service bypasses the SequentialAgent wiring and runs the executor LlmAgent directly for per-session browser control

### PlaywrightComputer Action Method Reference (Already Implemented)

All methods check `_check_cancel()` before and after every `await`. Key methods for ACs:

```python
# AC 1 — Navigate (FR8, FR15)
async def navigate(self, url: str) -> ComputerState:
    # goto(url, wait_until="networkidle", timeout=15_000)

# AC 2 — Click with bbox or selector (FR9, FR14)
async def click(self, target) -> ComputerState:
    # bbox dict → mouse.click(center_x, center_y); retries up to 2 times on failure
    # string → page.click(selector)

# AC 2 — Click by coordinates (FR9, FR14) — used by ComputerUseToolset directly
async def click_at(self, x: int, y: int) -> ComputerState:
    # page.mouse.click(x, y)

# AC 3 — Type at coordinates (FR10)
async def type_text_at(self, x: int, y: int, text: str, press_enter=True, clear_before_typing=True) -> ComputerState:
    # mouse.click(x, y), keyboard.type(text, delay=30)

# AC 3 — Type at selector (FR10) — convenience wrapper
async def type_text(self, selector: str, text: str) -> ComputerState:
    # page.click(selector), keyboard.type(text, delay=30)

# AC 4 — Scroll whole page (FR11)
async def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> ComputerState:
    # mouse.wheel(delta_x=±500, delta_y=±500)

# AC 4 — Scroll at coordinates (FR11)
async def scroll_at(self, x, y, direction, magnitude) -> ComputerState:
    # mouse.move(x, y), mouse.wheel(delta_x, delta_y)

# AC 5 — Read page text (FR13) — wraps in <page_content> tag (NFR9)
async def read_page(self, selector: str | None = None) -> str:
    # inner_text(selector or "body"), wrapped in <page_content>...</page_content>
```

### Per-Session Executor Agent Pattern (CRITICAL)

The module-level `executor_agent` uses `_default_computer = PlaywrightComputer(session_id="")` — this is a placeholder for import-time agent definition only. Story 3.2 must create a **per-session** `LlmAgent` so each session has its own isolated Playwright browser:

```python
# services/executor_service.py  — executor_service creation pattern

from google.adk.agents import LlmAgent
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from prompts.executor_system import EXECUTOR_SYSTEM_PROMPT
from tools.playwright_computer import PlaywrightComputer, BargeInException
from agents.executor_agent import build_executor_context

async def run_executor(session_id: str, step_plan: dict) -> None:
    pc = PlaywrightComputer(session_id=session_id)
    await pc.start()
    try:
        # Per-session agent with actual computer (NOT the module-level placeholder)
        agent = LlmAgent(
            name=f"executor_{session_id}",
            model="gemini-2.0-flash",
            instruction=EXECUTOR_SYSTEM_PROMPT,
            tools=[ComputerUseToolset(computer=pc)],
        )
        # Use ADK Runner — check google.adk.runners for Runner; google.adk.sessions for InMemorySessionService
        # Pattern: Runner(agent=agent, app_name="aria_executor", session_service=InMemorySessionService())
        # Verify exact API with: python -c "from google.adk.runners import Runner; help(Runner)"
        ...
    except BargeInException as e:
        logger.warning("Barge-in during executor for session %s: %s", session_id, e)
        emit_event(session_id, "task_paused", {"paused_at_step": current_step_index})
    except Exception as e:
        logger.error("Executor failed for session %s: %s", session_id, e)
        emit_event(session_id, "task_failed", {"reason": str(e)})
    finally:
        await pc.stop()   # ALWAYS clean up browser resources
```

**VERIFY ADK Runner API before implementing** — the exact imports and constructor may differ from the pattern above:
```bash
python -c "from google.adk.runners import Runner; import inspect; print(inspect.signature(Runner.__init__))"
python -c "from google.adk import sessions; print(dir(sessions))"
```

### Background Task Launch Pattern (Task Router)

The executor runs asynchronously after the planner — the `/api/task/start` endpoint returns the step plan immediately while execution proceeds in the background:

```python
# routers/task_router.py — after step 6 (plan_ready status update)

# Update status to executing before background task starts
await update_session_status(session_id, "executing")

# Launch executor as background task — do NOT await; returns immediately to caller
asyncio.create_task(run_executor(session_id, step_plan))
```

This mirrors the `_emit()` pattern already used in `task_router.py` for staggered SSE step_planned events (`asyncio.create_task(_emit())`). Use the same error guard pattern (try/except around the create_task).

### Cancel Flag Integration — Already Wired

The `PlaywrightComputer._check_cancel()` already calls `session_service.get_cancel_flag(session_id).is_set()`. The cancel flag is set by the interrupt endpoint (`POST /api/task/{session_id}/interrupt`) — that endpoint is wired in Story 3.4. For Story 3.2, the executor_service just needs to catch `BargeInException` after it propagates up from any PlaywrightComputer action.

```python
# services/session_service.py — already implemented (Story 3.1)
_cancel_flags: dict[str, asyncio.Event] = {}

def get_cancel_flag(session_id: str) -> asyncio.Event:  # lazy create
def reset_cancel_flag(session_id: str) -> None:          # set() was called externally
def signal_barge_in(session_id: str) -> None:            # check if exists, verify
```

### SSE Events Emitted by Story 3.2

Story 3.2 introduces the following new SSE event emissions (using existing `emit_event` function from `services/sse_service.py`):

| Event Type | When | Payload |
|---|---|---|
| `task_paused` | `BargeInException` caught | `{paused_at_step: int}` |
| `step_error` | Step fails after 2 retries | `{step_index: int, error: str, description: str}` |
| `task_failed` | Unrecoverable executor error | `{reason: str}` |

**Story 3.3** adds `step_start` and `step_complete` events with screenshots — do NOT emit those in Story 3.2.

### Step Plan Schema Reference

Each step from the Planner has these fields (validated in `planner_service._validate_step_plan`):

```python
{
    "step_index": int,          # 0-based
    "description": str,         # Human-readable step description
    "action": str,              # "navigate" | "click" | "type" | "scroll" | "screenshot" | "wait"
    "target": str,              # URL, selector, or direction
    "value": str,               # Text to type, pixel count for scroll, etc.
    "confidence": float,        # 0.0–1.0
    "is_destructive": bool,     # Story 4.5 guard — executor checks this
    "requires_user_input": bool, # Story 3.5 — missing data pause
    "user_input_reason": str,   # Reason if requires_user_input=True
}
```

### Audit Writer Stub (Important)

`handlers/audit_writer.py::write_audit_log` is currently a **no-op stub** — it will be implemented in Story 3.5. Story 3.2 does NOT need to call it. Only `update_session_status` (already implemented) and SSE `emit_event` are needed in this story.

### Testing Pattern from Story 3.1 (Use Same Style)

Tests in `test_executor_agent.py` use `unittest.mock.MagicMock` and `AsyncMock` with `patch` decorators. Follow the exact same pattern for `test_playwright_computer.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_navigate_calls_goto_with_networkidle():
    pc = PlaywrightComputer(session_id="test-session")
    pc.page = AsyncMock()
    pc.page.screenshot = AsyncMock(return_value=b"png")
    pc.page.url = "https://example.com"
    
    with patch.object(pc, "_check_cancel"):
        await pc.navigate("https://example.com")
    
    pc.page.goto.assert_called_once_with(
        "https://example.com",
        wait_until="networkidle",
        timeout=15_000,
    )
```

The `conftest.py` in `tests/` has shared fixtures — check it before adding new fixtures.

### Project Structure Notes

All new files follow existing patterns:
- New service: `aria-backend/services/executor_service.py` — mirrors `planner_service.py` structure (module docstring, logger = `logging.getLogger(__name__)`, private helpers)
- New tests: `aria-backend/tests/test_playwright_computer.py` and `test_executor_service.py` — mirror `test_executor_agent.py` structure (module docstring with AC coverage map, grouped tests with separator comments)
- No new dependencies needed — all imports already in `requirements.txt`

### References

- PlaywrightComputer implementation: [aria-backend/tools/playwright_computer.py](aria-backend/tools/playwright_computer.py)
- Existing executor agent + build_executor_context: [aria-backend/agents/executor_agent.py](aria-backend/agents/executor_agent.py)
- Task router (where to add background task): [aria-backend/routers/task_router.py](aria-backend/routers/task_router.py)
- SSE emit_event signature: [aria-backend/services/sse_service.py](aria-backend/services/sse_service.py)
- Session service (cancel flags): [aria-backend/services/session_service.py](aria-backend/services/session_service.py)
- Audit writer stub (do not implement yet): [aria-backend/handlers/audit_writer.py](aria-backend/handlers/audit_writer.py)
- Previous story (3.1 learnings + dev notes): [_bmad-output/implementation-artifacts/3-1-executor-agent-with-adk-sequentialagent-wiring.md](_bmad-output/implementation-artifacts/3-1-executor-agent-with-adk-sequentialagent-wiring.md)
- Story requirements source: [_bmad-output/planning-artifacts/epics.md#Story-3.2](_bmad-output/planning-artifacts/epics.md) (Epic 3 section)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Story 3.1 dev notes state: `executor_agent` module-level uses `_default_computer = PlaywrightComputer(session_id="")` as placeholder — per-session computers wired here in Story 3.2
- `audit_writer.write_audit_log` is a stub — do not try to use it; Story 3.5 implements it
- `ComputerUseToolset` import path confirmed in Story 3.1: `google.adk.tools.computer_use.computer_use_toolset`
- ADK `Runner` requires `app_name` + `agent` + `session_service`; `LlmAgent` names must be valid Python identifiers — session_id hyphens sanitized to underscores
- `run_executor` is imported by `task_router.py` and must be mocked in ALL test files that POST to `/api/task/start` (added to `test_task_router.py` and `test_sse_handler.py`)
- Added `timeout = 60` to `pyproject.toml` pytest config to prevent future hangs from stopping the full suite
- 90/90 tests pass in ~54s (28s ADK import overhead + 26s test execution)

### File List

- `aria-backend/services/executor_service.py` ← **CREATED**
- `aria-backend/routers/task_router.py` ← **MODIFIED** (added `run_executor` import, `executing` status update, executor background task launch with error guard)
- `aria-backend/tests/test_playwright_computer.py` ← **CREATED** (12 tests, AC 1–5)
- `aria-backend/tests/test_executor_service.py` ← **CREATED** (5 tests, AC 6)
- `aria-backend/tests/test_task_router.py` ← **MODIFIED** (added `run_executor` mock to all happy-path tests)
- `aria-backend/tests/test_sse_handler.py` ← **MODIFIED** (added `run_executor` mock; fixed unreliable background-task SSE assertion)
- `aria-backend/pyproject.toml` ← **MODIFIED** (added `timeout = 60` to pytest config)

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-03-02 | Implemented Story 3.2: executor_service.py (per-session executor loop with retry, barge-in handling, pc lifecycle); task_router.py wired to launch executor as background task; 17 new tests added (12 PlaywrightComputer + 5 executor_service); test suite fixed for run_executor mock in task_router/sse_handler tests; pytest timeout=60 added | claude-sonnet-4-6 |
