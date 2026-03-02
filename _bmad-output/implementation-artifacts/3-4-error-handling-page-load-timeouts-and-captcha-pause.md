# Story 3.4: Error Handling, Page Load Timeouts, and CAPTCHA Pause

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want ARIA to handle browser errors gracefully — page timeouts, navigation failures, and CAPTCHAs — without crashing my session,
So that I can intervene and continue rather than having to restart from scratch.

## Acceptance Criteria

1. **Given** a page navigation times out after 15 seconds, **When** the timeout fires, **Then** the Executor emits a `step_error` SSE event with `description: "Page did not load within 15 seconds"`, calls `update_session_status(session_id, "error")`, and returns from the step without retrying (retrying a 15s timeout wastes 30–45s; it must be treated as non-retryable) (FR41, NFR14).

2. **Given** a Gemini API rate-limit or transient network error occurs during `runner.run_async()`, **When** the error is caught, **Then** the backend retries up to 2 times with 1-second backoff. If all 3 attempts fail, a `task_failed` SSE event is emitted with the error reason and session status is set to `"failed"` (NFR15).

3. **Given** the Computer Use model (or CAPTCHA detection helper) identifies a CAPTCHA element on the current page, **When** ARIA determines it cannot proceed autonomously, **Then** execution pauses, an `awaiting_input` SSE event is emitted with `payload: {reason: "captcha_detected", message: "CAPTCHA encountered — manual intervention required"}`, and the thinking panel displays the message inline in the active step (FR42).

4. **Given** a `step_error` or `awaiting_input` state is active (execution paused), **When** the user sends `POST /api/task/{session_id}/input` with `{"value": "<instructions>"}`, **Then** the Executor receives the input via its per-session `asyncio.Queue`, re-evaluates the current page state (fresh screenshot + context), and resumes execution from the paused step.

5. **Given** an `awaiting_input` SSE event is received by the frontend, **When** the `thinkingPanelSlice` processes it, **Then** `taskStatus` transitions to `"awaiting_input"`, `awaitingInputMessage` is set to the event's `message` payload, and an `InputRequestBanner` component renders inside the thinking panel with the message text and a text input + "Send" button.

6. **Given** the user submits input via the `InputRequestBanner`, **When** the "Send" button is clicked, **Then** `POST /api/task/{session_id}/input` is called with the user's text, the banner shows a loading state, and upon `200 OK` the banner hides and `taskStatus` transitions back to `"running"`.

## Tasks / Subtasks

- [ ] Task 1: Add `detect_captcha()` helper to `aria-backend/tools/playwright_computer.py` (AC: 3)
  - [ ] Add `async def detect_captcha(self) -> bool:` method to `PlaywrightComputer`
  - [ ] Implementation: use `await self.page.content()` to get full HTML; check for captcha keyword patterns using `re.search` (case-insensitive): `r"captcha|recaptcha|hCaptcha|cf-challenge|challenge-form|turnstile"`.
  - [ ] Also check page title: `title = await self.page.title()` and apply same regex
  - [ ] Return `True` if any match found, `False` otherwise
  - [ ] Wrap in `try/except` — return `False` on any error (non-fatal; do not crash execution)
  - [ ] Do NOT import `re` at top of file if not already there — add it

- [ ] Task 2: Create `aria-backend/services/input_queue_service.py` — per-session user input queue (AC: 4)
  - [ ] Module-level `_input_queues: dict[str, asyncio.Queue[str]] = {}`
  - [ ] `def get_input_queue(session_id: str) -> asyncio.Queue[str]:` — creates queue if absent, returns it
  - [ ] `def put_user_input(session_id: str, value: str) -> None:` — `get_input_queue(session_id).put_nowait(value)`
  - [ ] `def clear_input_queue(session_id: str) -> None:` — `_input_queues.pop(session_id, None)`
  - [ ] Pattern mirrors the barge-in cancel flag dict in `session_service.py` (module-level dict, lazily initialized per session)

- [ ] Task 3: Add `POST /api/task/{session_id}/input` endpoint to `aria-backend/routers/task_router.py` (AC: 4, 6)
  - [ ] Define `class UserInputRequest(BaseModel): value: str = Field(..., min_length=1)`
  - [ ] `@router.post("/{session_id}/input")` route
  - [ ] Body: `UserInputRequest`; no auth check required (session_id is the ownership token for now — same pattern as `/interrupt`)
  - [ ] Call `put_user_input(session_id, body.value)` from `input_queue_service`
  - [ ] Return `{"success": True, "data": {"queued": True}, "error": None}` on success
  - [ ] Return `404` with canonical error envelope if session_id is unknown (check `get_input_queue` — if queue doesn't exist yet and no running session, return error)
  - [ ] Import `put_user_input` from `services.input_queue_service`

- [ ] Task 4: Refactor step retry logic in `aria-backend/services/executor_service.py` to handle 3 error classes differently (AC: 1, 2, 3, 4)
  - [ ] Add imports:
    ```python
    import re
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from services.input_queue_service import get_input_queue, clear_input_queue
    ```
  - [ ] **PlaywrightTimeoutError handling (AC: 1)**: In the per-attempt `except` block, add a specific check _before_ the generic handler:
    ```python
    except PlaywrightTimeoutError as exc:
        # Non-retryable: page load timeout is deterministic — retrying wastes 15s each time
        logger.error("Page load timeout at step %d session %s: %s", current_step_index, session_id, exc)
        emit_event(
            session_id,
            "step_error",
            {
                "step_index": current_step_index,
                "error": "Page did not load within 15 seconds",
                "description": step_description,
            },
        )
        try:
            await update_session_status(session_id, "error")
        except Exception:
            logger.warning("Failed to update session %s status to 'error'", session_id)
        return
    ```
    - [ ] This `except PlaywrightTimeoutError` MUST appear BEFORE the generic `except Exception` in the attempt loop
    - [ ] Do NOT include in the `_MAX_STEP_ATTEMPTS` retry loop — break out immediately
  - [ ] **Gemini API retry with 1s backoff (AC: 2)**: Wrap `runner.run_async(...)` in a dedicated retry helper. Add a module-level constant `_GEMINI_MAX_RETRIES = 2` and `_GEMINI_BACKOFF_SECONDS = 1.0`. Detect Gemini API errors by checking for `google.api_core.exceptions.GoogleAPICallError` or `google.generativeai` exceptions:
    ```python
    from google.api_core import exceptions as gapi_exceptions
    ```
    - [ ] In the existing `except Exception as exc:` branch (after `PlaywrightTimeoutError` is already handled), check: `if isinstance(exc, gapi_exceptions.GoogleAPICallError):` → set a `gemini_error_count` counter per step; if `gemini_error_count > _GEMINI_MAX_RETRIES` → emit `task_failed` SSE and return. If within retries → `await asyncio.sleep(_GEMINI_BACKOFF_SECONDS)` before next attempt.
    - [ ] Generic non-Gemini exceptions → existing retry with `_RETRY_DELAY_SECONDS` unchanged.
  - [ ] **CAPTCHA detection (AC: 3)**: After the `last_exc is None` check (step succeeded), before emitting `step_complete`, call CAPTCHA detection:
    ```python
    if await pc.detect_captcha():
        logger.warning("CAPTCHA detected at step %d session %s", current_step_index, session_id)
        emit_event(
            session_id,
            "awaiting_input",
            {
                "step_index": current_step_index,
                "reason": "captcha_detected",
                "message": "CAPTCHA encountered — manual intervention required",
            },
            step_index=current_step_index,
        )
        # Wait for user input via queue
        input_queue = get_input_queue(session_id)
        try:
            user_input = await asyncio.wait_for(input_queue.get(), timeout=300.0)
            logger.info("Received user input after CAPTCHA for session %s: %s", session_id, user_input)
            # Re-evaluate: re-emit step_start and retry current step once
            # (fall through to re-run this step by using continue with step index unchanged)
        except asyncio.TimeoutError:
            emit_event(session_id, "task_failed", {"reason": "Input wait timeout after CAPTCHA"})
            try:
                await update_session_status(session_id, "failed")
            except Exception:
                pass
            return
        continue  # Retry this step after user has solved the CAPTCHA
    ```
    - [ ] CAPTCHA check happens after `last_exc is None` (step action completed) but before `step_complete` SSE
    - [ ] After the input arrives, `continue` loops back to re-run the step from the top of the `for step in steps:` loop body — this re-takes a screenshot and re-runs the ADK step. **IMPORTANT**: to re-run the SAME step, we must NOT `continue` the outer `for step in steps` loop. Instead:
      - Use an inner `while True:` or `retry_after_input` flag that restarts the attempt block for the same step.
      - Simpler: after `user_input = await input_queue.get()`, reset `last_exc = Exception("re-evaluating")` and `break` to exit the attempt loop, then check: if the outer `if last_exc is None` check fails, it falls into the retry-step-error path which emits `step_error`. That's wrong.
      - **Correct approach**: extract captcha-pause-and-resume into a helper. After pausing and getting input, re-start the current step's retry loop from scratch by using a `should_retry_step` boolean flag. Set it before `continue`, and in the step outer loop check it.
      - **Simpler still**: wrap the entire `for attempt in range(_MAX_STEP_ATTEMPTS)` block and the post-success logic in a `while True:` with a `step_done = False` flag. When input received, take a new screenshot and loop back.
      - [ ] See the Dev Notes section for the exact `while True:` restructure pattern.
  - [ ] **Input resume after step_error (AC: 4)**: After emitting `step_error` (exhausted retries), await user input from queue before returning. If input arrives, retry the current step (reset attempt count). If `asyncio.TimeoutError` (300s), emit `task_failed` and return.
    ```python
    # After emit step_error, wait for user input
    input_queue = get_input_queue(session_id)
    try:
        user_input = await asyncio.wait_for(input_queue.get(), timeout=300.0)
        logger.info("Resuming step %d session %s after user input", current_step_index, session_id)
        # Reset last_exc and retry the step
        last_exc = None
        # Use should_retry_step flag to loop back (see Dev Notes)
    except asyncio.TimeoutError:
        emit_event(session_id, "task_failed", {"reason": "Input wait timeout after step error"})
        try:
            await update_session_status(session_id, "failed")
        except Exception:
            pass
        return
    ```
  - [ ] In the `finally` block, add `clear_input_queue(session_id)` after `await pc.stop()` to clean up the queue

- [ ] Task 5: Update `aria-frontend/src/store/ariaStore.ts` (or equivalent Zustand store) to add `awaiting_input` state (AC: 5, 6)
  - [ ] Add field `awaitingInputMessage: string | null` to the `thinkingPanelSlice` (or whichever slice owns `taskStatus`)
  - [ ] Add reset of `awaitingInputMessage` to `null` in the initial state and reset action
  - [ ] The `taskStatus: "awaiting_input"` type already exists in `aria.ts`

- [ ] Task 6: Add `awaiting_input` SSE event handler in `aria-frontend/src/lib/hooks/useSSEConsumer.ts` (AC: 5)
  - [ ] In the `switch (event.event_type)` block, add:
    ```typescript
    case "awaiting_input": {
      const payload = event.payload as { reason?: string; message?: string };
      useARIAStore.setState({
        taskStatus: "awaiting_input",
        awaitingInputMessage: payload.message ?? "ARIA needs your input to continue",
      });
      break;
    }
    ```
  - [ ] Place after the existing `"task_failed"` case
  - [ ] Also add reset of `awaitingInputMessage` in the `"task_complete"` and `"task_failed"` handlers (set to `null`)

- [ ] Task 7: Create `aria-frontend/src/components/thinking-panel/InputRequestBanner.tsx` (AC: 5, 6)
  - [ ] Component props: `{ message: string; sessionId: string; onSubmitted?: () => void }`
  - [ ] Render a `<div>` with class `mt-3 p-3 rounded-md border border-amber-500/40 bg-amber-950/20`
  - [ ] Inside: amber warning icon (`⚠`), the `message` text in `text-sm text-amber-300`
  - [ ] Below: a `<textarea>` (single-row, expandable) with placeholder "Type your response..." + Geist Mono font class
  - [ ] "Send" button: calls `POST /api/task/{sessionId}/input` with `{value: userInput}` via `fetch`
  - [ ] Loading state: disable button + show spinner while fetch is in-flight
  - [ ] On success: call `onSubmitted?.()` which triggers parent to set `taskStatus` back to `"running"` and clear `awaitingInputMessage`; clear the input field
  - [ ] On error: show error message below the textarea in rose text; re-enable button
  - [ ] `data-testid="input-request-banner"` on the wrapper div
  - [ ] Export as named export `InputRequestBanner` and default export

- [ ] Task 8: Integrate `InputRequestBanner` into thinking panel (AC: 5, 6)
  - [ ] In `ThinkingPanel.tsx`, import `InputRequestBanner`
  - [ ] Read `awaitingInputMessage` and `taskStatus` from `useARIAStore`
  - [ ] Render conditionally after the `StepItem` list:
    ```tsx
    {taskStatus === "awaiting_input" && awaitingInputMessage && (
      <InputRequestBanner
        message={awaitingInputMessage}
        sessionId={sessionId}
        onSubmitted={() => useARIAStore.setState({ taskStatus: "running", awaitingInputMessage: null })}
      />
    )}
    ```
  - [ ] `sessionId` is already available in `ThinkingPanel` via props or store

- [ ] Task 9: Write backend tests (AC: 1, 2, 3, 4)
  - [ ] `aria-backend/tests/test_playwright_computer.py` — add `test_detect_captcha_true_when_recaptcha_in_page` (mock `page.content()` to return `"<div class='g-recaptcha'></div>"`), `test_detect_captcha_false_when_normal_page`, `test_detect_captcha_returns_false_on_exception`
  - [ ] `aria-backend/tests/test_input_queue_service.py` — new file: test `get_input_queue` creates queue, `put_user_input` populates it, `clear_input_queue` removes it, consecutive `get_input_queue` calls return same queue instance
  - [ ] `aria-backend/tests/test_executor_service.py` — add:
    - `test_run_executor_page_load_timeout` — patch `runner.run_async` to raise `playwright.async_api.TimeoutError`; assert `step_error` SSE emitted with message "Page did not load within 15 seconds" and session status updated to "error"
    - `test_run_executor_gemini_api_error_retries_twice` — patch `runner.run_async` to raise `gapi_exceptions.ServiceUnavailable("rate limit")` twice then succeed; assert retry happened with 1s backoff (mock `asyncio.sleep`) and `step_complete` emitted on 3rd attempt
    - `test_run_executor_gemini_api_error_exhausted_emits_task_failed` — patch `runner.run_async` to always raise `gapi_exceptions.ServiceUnavailable`; assert `task_failed` SSE emitted (not `step_error`)
    - `test_run_executor_captcha_detected_emits_awaiting_input` — patch `pc.detect_captcha` to return `True`; patch `input_queue.get` to return user input immediately; assert `awaiting_input` SSE emitted, then step retried, then `step_complete`
    - All existing tests for `task_paused`, `step_error`, `step_complete`, `step_start` must continue passing — do NOT break them

- [ ] Task 10: Write frontend tests (AC: 5, 6)
  - [ ] `InputRequestBanner.test.tsx` — renders with message text; `data-testid="input-request-banner"` present; send button calls `POST /api/task/{sessionId}/input`; shows loading state while fetching; calls `onSubmitted` on success; shows error text on fetch failure
  - [ ] `useSSEConsumer.test.ts` — add test: `awaiting_input` event sets `taskStatus: "awaiting_input"` and `awaitingInputMessage`
  - [ ] Follow existing test patterns: Vitest + React Testing Library + `vi.spyOn(global, "fetch")`

- [ ] Task 11: Git commit
  - [ ] `git add -A && git commit -m "feat(story-3.4): error handling, page load timeouts, and CAPTCHA pause"`

## Dev Notes

### Error Classification in `executor_service.py`

Story 3.4 requires **three distinct error categories** handled differently. Current code has one unified `except Exception` that retries all errors the same way. The new classification:

| Error Type | Detection | Retry Policy | SSE on Failure |
|---|---|---|---|
| `PlaywrightTimeoutError` (page load) | `except PlaywrightTimeoutError` | **No retry** (non-retryable) | `step_error` with specific message |
| `GoogleAPICallError` (Gemini API) | `isinstance(exc, gapi_exceptions.GoogleAPICallError)` | 2 retries, 1s backoff → `task_failed` | `task_failed` |
| All other exceptions | generic `except Exception` | 2 retries, 0.3s delay → `step_error` + pause for input | `step_error` → await input |

**Import required for Gemini API error detection:**
```python
from google.api_core import exceptions as gapi_exceptions
```
`GoogleAPICallError` is the base class for all Google API errors including `ServiceUnavailable`, `ResourceExhausted` (rate limit), `DeadlineExceeded`, `InternalServerError`.

### Step Retry Loop Restructure for Input Resume

The current `for attempt in range(_MAX_STEP_ATTEMPTS)` does not support re-running the same step after user input. The correct pattern uses a `while True:` outer loop with a "step resolved" flag:

```python
steps = step_plan.get("steps", [])
step_idx = 0
while step_idx < len(steps):
    step = steps[step_idx]
    current_step_index = step.get("step_index", current_step_index)
    step_description = step.get("description", f"step {current_step_index}")
    gemini_error_count = 0

    # emit step_start...

    step_resolved = False  # Set to True when step succeeds; loop exits
    while not step_resolved:
        last_exc: Exception | None = None
        for attempt in range(_MAX_STEP_ATTEMPTS):
            try:
                # ... ADK runner ...
                last_exc = None
                break
            except BargeInException:
                raise
            except PlaywrightTimeoutError as exc:
                # emit step_error + wait for input or return
                user_input = await _wait_for_user_input(session_id)
                if user_input is None:
                    return  # timeout → already emitted task_failed
                break  # retry attempt loop with same step
            except gapi_exceptions.GoogleAPICallError as exc:
                gemini_error_count += 1
                if gemini_error_count > _GEMINI_MAX_RETRIES:
                    emit_event(session_id, "task_failed", ...)
                    return
                await asyncio.sleep(_GEMINI_BACKOFF_SECONDS)
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_STEP_ATTEMPTS - 1:
                    await asyncio.sleep(_RETRY_DELAY_SECONDS)

        if last_exc is not None:
            # All attempts exhausted → await user input
            user_input = await _wait_for_user_input(session_id, paused_with="step_error")
            if user_input is None:
                return
            # loop back: while not step_resolved → retry same step
            continue

        # Step succeeded: check CAPTCHA
        if await pc.detect_captcha():
            user_input = await _wait_for_user_input(session_id, paused_with="captcha")
            if user_input is None:
                return
            continue  # retry same step

        # All good: emit step_complete, append to completed_steps
        # ... existing step_complete emit code ...
        step_resolved = True

    step_idx += 1

success = True
```

Extract a helper `_wait_for_user_input(session_id, emit_type)` to avoid code duplication.

### CAPTCHA Detection Strategy

`detect_captcha()` is a heuristic approach — it scans the page HTML for common CAPTCHA vendor signatures. It does NOT rely on the Computer Use model explicitly calling out "CAPTCHA found" (which it may or may not do in its reasoning).

Common patterns covered:
- `g-recaptcha` / `recaptcha` — Google reCAPTCHA (v2/v3)
- `hcaptcha` — hCaptcha
- `cf-challenge-body` / `challenge-form` — Cloudflare Turnstile / Basic Challenge
- `turnstile` — Cloudflare Turnstile explicit

This is sufficient for demo MVP. Full CAPTCHA classification is not required.

### Per-Session Input Queue Pattern

Mirrors the barge-in cancel flag architecture:
- **Architecture spec**: `Barge-in cancel flag: asyncio.Event per session stored in module-level dict in session_service.py`
- **Story 3.4 pattern**: `asyncio.Queue[str] per session stored in module-level dict in input_queue_service.py`
- Both use lazy initialization: queue created on first `get_input_queue(session_id)` call
- Both need cleanup in `executor_service.py`'s `finally` block

The 300-second (5 minute) timeout on `asyncio.wait_for(queue.get(), 300)` prevents goroutine leaks if a tab is closed mid-session without cancelling.

### `POST /api/task/{session_id}/input` — No Auth Required

The architecture spec lists this alongside `/interrupt` and `/confirm` which also have no Firebase auth check (they use `session_id` as the implicit ownership token since it's a UUID v4 and unpredictable). Keep it consistent — no `Authorization` header required.

### Frontend: Zustand Store Fields to Add

The `awaitingInputMessage` field needs to be added to whichever store slice currently holds `taskStatus`. Based on Stories 2.3 and 2.4, `taskStatus` lives in the root `useARIAStore`. The field addition:

```typescript
// In ariaStore initial state:
awaitingInputMessage: null as string | null,
```

No new slice needed — add to existing store alongside `taskStatus`.

### `useSSEConsumer.ts` — Existing Handler Coverage

| Event Type | Currently Handled | Story 3.4 Changes |
|---|---|---|
| `step_start` | ✅ Sets step `status: "active"` | No change |
| `step_complete` | ✅ Sets `status: "complete"`, stores `screenshot_url` | No change |
| `step_error` | ✅ Sets step `status: "error"` | No change |
| `task_complete` | ✅ Sets `taskStatus: "completed"` | Add `awaitingInputMessage: null` reset |
| `task_failed` | ✅ Sets `taskStatus: "failed"`, `errorMessage` | Add `awaitingInputMessage: null` reset |
| `awaiting_input` | ❌ Not handled | **ADD** — sets `taskStatus: "awaiting_input"`, `awaitingInputMessage` |

### Files Created / Modified by Story 3.4

| File | Action |
|---|---|
| `aria-backend/tools/playwright_computer.py` | Add `detect_captcha()` method + `import re` |
| `aria-backend/services/input_queue_service.py` | **CREATE** — per-session async input queue |
| `aria-backend/routers/task_router.py` | Add `POST /{session_id}/input` endpoint |
| `aria-backend/services/executor_service.py` | Refactor retry loop; add 3-tier error classification; add input-pause-resume; add CAPTCHA detection; cleanup queue |
| `aria-frontend/src/store/ariaStore.ts` | Add `awaitingInputMessage: string \| null` field |
| `aria-frontend/src/lib/hooks/useSSEConsumer.ts` | Add `awaiting_input` case + reset in `task_complete`/`task_failed` |
| `aria-frontend/src/components/thinking-panel/InputRequestBanner.tsx` | **CREATE** |
| `aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx` | Integrate `InputRequestBanner` |
| `aria-backend/tests/test_playwright_computer.py` | Add CAPTCHA detection tests |
| `aria-backend/tests/test_input_queue_service.py` | **CREATE** |
| `aria-backend/tests/test_executor_service.py` | Add timeout/retry/captcha/input-resume tests |
| `aria-frontend/src/components/thinking-panel/InputRequestBanner.test.tsx` | **CREATE** |
| `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts` | Add `awaiting_input` handler test |

**DO NOT TOUCH:**
- `aria-backend/handlers/audit_writer.py` — stub intentionally left for Story 3.5
- `aria-backend/services/gcs_service.py` — complete, no changes needed
- `aria-backend/services/sse_service.py` — complete, no changes needed
- `aria-backend/tools/playwright_computer.py` existing methods — only ADD `detect_captcha`, do not modify navigate/click/type/scroll
- `aria-frontend/src/types/aria.ts` — `TaskStatus: "awaiting_input"` already exists; no changes needed

### Architecture Spec References

- `FR41`: ARIA handles page load failures and network errors without crashing the session
- `FR42`: ARIA handles CAPTCHA encounters by pausing and notifying the user that manual intervention is required
- `NFR14`: Page load timeout: report failure to user within 15 seconds without crashing
- `NFR15`: Gemini API errors retry max 2 times before surfacing error to user
- SSE event types: `step_error`, `awaiting_input`, `task_failed` all defined in architecture spec
- `POST /api/task/{session_id}/input` — defined in architecture REST endpoint list
- `asyncio.Event` per session pattern for barge-in (architecture spec) → mirrors `asyncio.Queue` for input

### Previous Story Learnings (from Story 3.3)

- `emit_event` is **synchronous** — no `await`. Always call as `emit_event(session_id, event_type, payload)`
- `upload_screenshot` is **async** — must be `await`ed
- Non-fatal failures (screenshot, GCS) must NOT abort execution — wrap in `try/except`, log, continue
- `post_screenshot_bytes = await pc.screenshot()` — always call fresh, never reuse bytes from earlier in the same step
- `BargeInException` must propagate immediately (no retry, no catch) — `raise` it in the `except` block
- The `finally` block in `run_executor` runs `await pc.stop()` unconditionally — add `clear_input_queue(session_id)` there

### Git Context (Recent Commits)

- `e6d5933`: feat: mark Story 3.3 as done, implement error handling for screenshot capture, update tests
- `c6a8af5`: feat(story-3.3): screenshot capture, GCS upload, and step SSE events
- `8f287a8`: feat: update status to done for Story 3.2 and extract task completion handler to avoid circular imports

Key patterns from Story 3.2/3.3 commits: task completion was extracted to `task_complete_service.py` to avoid circular imports — follow this pattern if new service files are needed.

### Project Structure Notes

- New service file `input_queue_service.py` follows existing pattern (single-responsibility service files under `aria-backend/services/`)
- New router test file `test_input_queue_service.py` follows existing pattern under `aria-backend/tests/`
- New frontend component `InputRequestBanner.tsx` follows the `thinking-panel/` component co-location pattern established in Stories 2.4 and 3.3
- All test files use `@pytest.mark.asyncio` for async backend tests and Vitest + RTL for frontend tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4 AC] — FR41, FR42, NFR14, NFR15
- [Source: _bmad-output/planning-artifacts/epics.md#Architecture — API & Communication] — SSE event types, REST endpoints
- [Source: aria-backend/services/executor_service.py] — existing retry loop structure (`_MAX_STEP_ATTEMPTS`, `_RETRY_DELAY_SECONDS`, barge-in handling)
- [Source: aria-backend/services/planner_service.py#_call_planner_with_retry] — NFR15 pattern (2 retries, 1s backoff)
- [Source: aria-backend/tools/playwright_computer.py#navigate] — `timeout=15_000` already set; `PlaywrightTimeoutError` will be raised by Playwright on expiry
- [Source: aria-frontend/src/types/aria.ts] — `TaskStatus: "awaiting_input"` already defined
- [Source: aria-frontend/src/lib/hooks/useSSEConsumer.ts] — existing SSE handler switch pattern
- [Source: _bmad-output/implementation-artifacts/3-3-screenshot-capture-gcs-upload-and-step-sse-events.md#Dev Notes] — emit_event is synchronous, non-fatal error patterns

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### File List
