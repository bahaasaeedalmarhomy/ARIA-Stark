# Story 3.5: Firestore Audit Log Writer and Mid-Task Input Request

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want every action ARIA takes to be recorded in a durable audit log, and to be prompted when ARIA needs information I haven't provided,
So that I have a complete record of what happened and ARIA can handle tasks that require my input mid-execution.

## Acceptance Criteria

1. **Given** a step completes, **When** `step_complete` is processed, **Then** the Firestore document `sessions/{session_id}` is updated: a new entry is appended to the `steps` array with `step_index`, `action_type`, `description`, `result`, `screenshot_url`, `confidence`, `timestamp` (ISO 8601 UTC with "Z" suffix), and `status: "complete"` — using `firestore.ArrayUnion` so no existing entries are overwritten (FR34, FR35).

2. **Given** the Executor encounters a step with `requires_user_input: true` (from the Planner step plan), **When** that step is about to execute, **Then** the Executor emits an `awaiting_input` SSE event with `payload: {step_index, reason: "requires_input", message: <user_input_reason or default>}` and pauses execution via the per-session `asyncio.Queue` — BEFORE the ADK runner is called for that step (FR33).

3. **Given** an `awaiting_input` SSE event is received by the frontend with `reason: "requires_input"`, **When** it is processed, **Then** `taskStatus` transitions to `"awaiting_input"` and the `InputRequestBanner` renders in the thinking panel with the message text and a text input + "Send" button. (Banner and SSE handler delivered in story 3.4 — no new frontend wiring needed; this AC confirms end-to-end coverage for the `requires_input` reason code.)

4. **Given** the user submits input via `POST /api/task/{session_id}/input`, **When** the backend receives it for a `requires_input`-paused step, **Then** the Executor resumes: the user-provided value is injected into the step's execution context via `build_executor_context`, the ADK runner runs with the enriched context, and the thinking panel transitions back to `"running"`.

5. **Given** a browser refresh occurs during or after an active session tab, **When** the page reloads and the session is still tracked in the component tree, **Then** a `useFirestoreSession` hook subscribes to `onSnapshot` of `sessions/{session_id}` in Firestore, reads the persisted `steps` array, and populates `auditLog: FirestoreAuditStep[]` in the store — no completed step data is lost (FR37).

6. **Given** the Firestore `onSnapshot` subscription fires with a session document, **When** the `steps` array is non-empty and `panelStatus === "complete"`, **Then** the `auditLog` in the store is rendered below the step plan in the `ThinkingPanel` as a summary list showing step number, description, and a `[screenshot]` indicator for entries with `screenshot_url`.

## Tasks / Subtasks

- [x] Task 1: Implement `write_audit_log` in `aria-backend/handlers/audit_writer.py` (AC: 1)
  - [x] Add imports at top of file:
    ```python
    import logging
    from datetime import datetime, timezone
    from google.cloud import firestore
    ```
  - [x] Add module-level lazy Firestore client (same pattern as `session_service.py`):
    ```python
    logger = logging.getLogger(__name__)
    _db = None

    def _get_db() -> firestore.AsyncClient:
        global _db
        if _db is None:
            _db = firestore.AsyncClient()
        return _db
    ```
  - [x] Replace the stub `write_audit_log` with the real implementation:
    ```python
    async def write_audit_log(session_id: str, step_index: int, data: dict) -> None:
        """Append a completed step entry to Firestore sessions/{session_id}.steps[]."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        entry = {
            "step_index": step_index,
            "action_type": data.get("action_type"),
            "description": data.get("description", ""),
            "result": data.get("result", "done"),
            "screenshot_url": data.get("screenshot_url"),
            "confidence": data.get("confidence", 1.0),
            "timestamp": timestamp,
            "status": "complete",
        }
        db = _get_db()
        doc_ref = db.collection("sessions").document(session_id)
        await doc_ref.update({"steps": firestore.ArrayUnion([entry])})
        logger.debug(
            "Audit log written for session %s step %d", session_id, step_index
        )
    ```
  - [x] Keep existing `update_session_status` wrapper (already correct — no changes)
  - [x] Remove `from dotenv import load_dotenv` and `load_dotenv()` — not needed in handlers

- [x] Task 2: Call `write_audit_log` from `aria-backend/services/executor_service.py` after each `step_complete` (AC: 1)
  - [x] Add import to the existing imports section in `executor_service.py`:
    ```python
    from handlers.audit_writer import write_audit_log
    ```
  - [x] Find the block after `emit_event(session_id, "step_complete", {...})` and BEFORE `completed_steps.append(...)`. Insert the audit write call:
    ```python
    # Write step to Firestore audit log (non-fatal — must not halt execution) (AC: 1)
    try:
        await write_audit_log(
            session_id,
            current_step_index,
            {
                "action_type": step.get("action"),
                "description": step_description,
                "result": "done",
                "screenshot_url": screenshot_url or None,
                "confidence": step.get("confidence", 1.0),
            },
        )
    except Exception:
        logger.warning(
            "Audit log write failed for session %s step %d — continuing",
            session_id,
            current_step_index,
        )
    ```
  - [x] This is placed between `emit_event(..., "step_complete", ...)` and `completed_steps.append(...)`
  - [x] Do NOT remove or change the `completed_steps.append(...)` call — it is still needed for the in-memory state used by `handle_task_complete`

- [x] Task 3: Handle `requires_user_input` steps in `aria-backend/services/executor_service.py` (AC: 2, 4)
  - [x] In the `while step_idx < len(steps):` loop, after extracting `step`, `current_step_index`, `step_description`, and resetting `gemini_error_count`, add a `requires_user_input` check BEFORE the `step_start` SSE emit:
    ```python
    # Pre-step: request user input if the Planner flagged this step as needing it (AC: 2, FR33)
    if step.get("requires_user_input"):
        user_input_reason = (
            step.get("user_input_reason")
            or f"I need your input to complete step {current_step_index + 1}"
        )
        emit_event(
            session_id,
            "awaiting_input",
            {
                "step_index": current_step_index,
                "reason": "requires_input",
                "message": user_input_reason,
            },
            step_index=current_step_index,
        )
        pre_step_input = await _wait_for_user_input(
            session_id,
            current_step_index,
            paused_with="requires_input",
            step_description=step_description,
        )
        if pre_step_input is None:
            return  # timeout already emitted task_failed
        # Shallow-copy step dict (do NOT mutate shared step_plan) and inject user value
        step = dict(step)
        step["user_provided_value"] = pre_step_input
    ```
  - [x] This check fires BEFORE `emit_event(session_id, "step_start", {...})` so the user sees the input request before the step begins
  - [x] `step = dict(step)` shallow copy ensures the original `step_plan["steps"]` list is not mutated — safe for retries
  - [x] Update the `build_executor_context` call inside the attempt loop to pass `user_provided_value`:
    ```python
    context = build_executor_context(
        step_plan,
        completed_steps,
        screenshot_b64,
        user_provided_value=step.get("user_provided_value"),
    )
    ```

- [x] Task 4: Extend `build_executor_context` in `aria-backend/agents/executor_agent.py` (AC: 4)
  - [x] Read current `executor_agent.py` to find the `build_executor_context` function signature and implementation
  - [x] Add optional parameter `user_provided_value: str | None = None` to the function signature (backward-compatible)
  - [x] At the end of the context string assembly, append the user value if provided:
    ```python
    if user_provided_value:
        context += f"\n\nUser-provided value for this step: {user_provided_value}\nUse this value directly where the step requires user input."
    ```
  - [x] This is an additive change — all existing callers without the new param continue to work

- [x] Task 5: Add `FirestoreAuditStep` type and `auditLog` state to frontend (AC: 5, 6)
  - [x] In `aria-frontend/src/types/aria.ts`, add the new interface after the existing `SSEEvent` interface:
    ```typescript
    export interface FirestoreAuditStep {
      step_index: number;
      action_type: string | null;
      description: string;
      result: string;
      screenshot_url: string | null;
      confidence: number;
      timestamp: string; // ISO 8601 UTC e.g. "2026-03-03T14:22:33.456Z"
      status: "complete" | "error";
    }
    ```
  - [x] In `aria-frontend/src/lib/store/aria-store.ts`:
    - Add `import type { ..., FirestoreAuditStep } from "@/types/aria"` (extend existing import)
    - Add `auditLog: FirestoreAuditStep[]` to `ThinkingPanelSlice` interface
    - Add `auditLog: []` to `ARIA_INITIAL_STATE`

- [x] Task 6: Create `aria-frontend/src/lib/hooks/useFirestoreSession.ts` (AC: 5)
  - [x] Create the new hook file

- [x] Task 7: Mount `useFirestoreSession` and render audit log in `ThinkingPanel.tsx` (AC: 5, 6)
  - [x] Import `useFirestoreSession` at top of `ThinkingPanel.tsx`
  - [x] Call `useFirestoreSession()` at the top of the component body (after existing store reads)
  - [x] Add `auditLog` to the existing `useARIAStore` reads
  - [x] After the step list `<ul>` and before the `InputRequestBanner` block, add the audit log section

- [x] Task 8: Write backend tests (AC: 1, 2, 4)
  - [x] Create `aria-backend/tests/test_audit_writer.py` with 4 tests
  - [x] In `aria-backend/tests/test_executor_service.py`, add 3 new tests (13, 14, 15)

- [x] Task 9: Write frontend tests (AC: 5, 6)
  - [x] Create `aria-frontend/src/lib/hooks/useFirestoreSession.test.ts` with 6 tests
  - [x] In `ThinkingPanel.test.tsx`, add 4 new audit log tests

- [x] Task 10: Git commit
  - [ ] `git add -A && git commit -m "feat(story-3.5): firestore audit log writer and mid-task input request"`
          (error) => {
            console.warn("[useFirestoreSession] onSnapshot error:", error);
          }
        );

        return () => unsubscribe();
      }, [sessionId]);
    }
    ```
  - [ ] `firebase/firestore` is already available — same `firebase` package already in `package.json`
  - [ ] Uses the same `app` singleton from `@/lib/firebase` — no new Firebase init needed

- [ ] Task 7: Mount `useFirestoreSession` and render audit log in `ThinkingPanel.tsx` (AC: 5, 6)
  - [ ] Import `useFirestoreSession` at top of `ThinkingPanel.tsx`
  - [ ] Import `FirestoreAuditStep` from `@/types/aria`
  - [ ] Call `useFirestoreSession()` at the top of the component body (after existing store reads)
  - [ ] Add `auditLog` to the existing `useARIAStore` reads:
    ```typescript
    const auditLog = useARIAStore((state) => state.auditLog);
    ```
  - [ ] After the step list `<ul>` and before the `InputRequestBanner` block, add the audit log section:
    ```tsx
    {panelStatus === "complete" && auditLog.length > 0 && (
      <div className="mt-4 pt-3 border-t border-border-aria" data-testid="audit-log-section">
        <p className="text-xs text-text-secondary mb-2 font-medium">
          Audit Log — {auditLog.length} step{auditLog.length !== 1 ? "s" : ""} recorded
        </p>
        <ul className="flex flex-col gap-1" role="list" aria-label="Audit log">
          {auditLog.map((entry) => (
            <li
              key={entry.step_index}
              className="text-xs font-mono text-text-secondary flex items-start gap-2"
            >
              <span className="text-text-primary shrink-0">
                #{entry.step_index + 1}
              </span>
              <span className="flex-1">{entry.description}</span>
              {entry.screenshot_url && (
                <span className="text-blue-400 shrink-0">[screenshot]</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    )}
    ```
  - [ ] Full `ScreenshotViewer` click-to-expand for audit entries is deferred to Story 3.6

- [ ] Task 8: Write backend tests (AC: 1, 2, 4)
  - [ ] Create `aria-backend/tests/test_audit_writer.py`:
    - `test_write_audit_log_appends_step_entry`:
      - Mock `_get_db()` to return a mock `AsyncClient`
      - Mock `doc_ref.update` as an async mock
      - Call `await write_audit_log("sess_123", 0, {"action_type": "navigate", "description": "Go to URL", "result": "done", "screenshot_url": "https://storage.googleapis.com/...", "confidence": 0.95})`
      - Assert `doc_ref.update` called once with `{"steps": firestore.ArrayUnion([{...}])}` where entry contains all 8 required fields
    - `test_write_audit_log_timestamp_is_iso8601_utc`:
      - Run `write_audit_log`, capture the entry passed to `ArrayUnion`
      - Assert `entry["timestamp"]` matches regex `r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"`
    - `test_write_audit_log_status_is_always_complete`:
      - Assert `entry["status"] == "complete"` (no input arg controls this)
    - `test_update_session_status_delegates`:
      - Patch `services.session_service.update_session_status` as `AsyncMock`
      - Call `await update_session_status("sess_123", "complete")`
      - Verify patched function called with `("sess_123", "complete")`
  - [ ] In `aria-backend/tests/test_executor_service.py`, add:
    - `test_run_executor_writes_audit_log_on_step_complete`:
      - Patch `write_audit_log` as `AsyncMock`
      - Run a successful single-step executor
      - Verify `write_audit_log` called once with correct `session_id`, `step_index=0`, and data dict containing `action_type`, `description`, `confidence`, `screenshot_url`
    - `test_run_executor_audit_write_failure_does_not_halt_execution`:
      - Patch `write_audit_log` to raise `Exception("Firestore unavailable")`
      - Run a successful single-step executor
      - Verify `step_complete` SSE still emitted and `handle_task_complete` still called
    - `test_run_executor_requires_user_input_emits_awaiting_input_before_step_start`:
      - Set up step with `requires_user_input=True`, `user_input_reason="What is the account email?"`
      - Patch `get_input_queue` to return a queue with `"test@example.com"` already enqueued
      - Run executor; capture all emitted SSE events in order
      - Assert `awaiting_input` event with `reason: "requires_input"` appears BEFORE any `step_start` event
      - Assert `build_executor_context` called with `user_provided_value="test@example.com"`

- [ ] Task 9: Write frontend tests (AC: 5, 6)
  - [ ] Create `aria-frontend/src/lib/hooks/useFirestoreSession.test.ts`:
    ```typescript
    // vi.mock("firebase/firestore") at top
    // Tests:
    ```
    - `test_subscribes_to_session_doc_when_sessionId_set`:
      - Set `sessionId` in store
      - Render hook
      - Verify `onSnapshot` called with a ref to `sessions/{sessionId}`
    - `test_populates_auditLog_from_snapshot_data`:
      - Mock `onSnapshot` to immediately call callback with `{exists: () => true, data: () => ({steps: [{step_index: 0, description: "Navigate", status: "complete", ...}]})}`
      - Assert `useARIAStore.getState().auditLog` has 1 entry with `step_index: 0`
    - `test_cleans_up_subscription_on_unmount`:
      - Capture the unsubscribe mock returned from `onSnapshot`
      - Unmount the hook
      - Assert unsubscribe was called
    - `test_no_subscription_when_sessionId_null`:
      - Do not set `sessionId`
      - Render hook
      - Assert `onSnapshot` was NOT called
  - [ ] Use `renderHook` + `cleanup` from `@testing-library/react` (same pattern as `useSSEConsumer.test.ts`)
  - [ ] In `ThinkingPanel.test.tsx`, add:
    - `test_renders_audit_log_section_when_complete_and_auditLog_non_empty`:
      - Set `panelStatus: "complete"` and `auditLog: [{step_index: 0, description: "Navigate to site", status: "complete", screenshot_url: "https://...", ...}]`
      - Assert `data-testid="audit-log-section"` is present
      - Assert "1 step recorded" text visible
      - Assert "[screenshot]" badge visible

- [ ] Task 10: Git commit
  - [ ] `git add -A && git commit -m "feat(story-3.5): firestore audit log writer and mid-task input request"`

## Dev Notes

### Firestore Step Entry Schema (AC: 1)

The step entry appended to `sessions/{session_id}.steps[]` via `firestore.ArrayUnion`:

```python
{
    "step_index":    int,          # 0-based; matches SSE step_index
    "action_type":  str | None,   # from step["action"]: "navigate", "click", "type", etc.
    "description":  str,          # human-readable from step_plan
    "result":       str,          # "done" on success (future: extracted page content for "read" steps)
    "screenshot_url": str | None, # GCS public URL, or None if GCS_BUCKET_NAME not configured
    "confidence":   float,        # Planner confidence score 0.0–1.0
    "timestamp":    str,          # ISO 8601 UTC: "2026-03-03T14:22:33.456Z"
    "status":       "complete",   # Always "complete" for success entries
}
```

**Why `ArrayUnion`?** Atomically appends without reading the existing array. Avoids any read-modify-write race conditions. Uses `google.cloud.firestore.ArrayUnion` — the same Firestore client already imported in `session_service.py`. No new dependency.

### `requires_user_input` Flow (AC: 2–4)

The Planner agent emits `requires_user_input: true` and `user_input_reason: "..."` when it identifies that a step needs data the user hasn't provided (e.g., passwords, file paths, account credentials). This is already specified in the Planner system prompt and enforced by the canonical step plan schema (story 2.1).

Execution flow for `requires_user_input` steps:

```
1. step extracted from step_plan.steps[]
2. CHECK step.get("requires_user_input")
3.   → emit "awaiting_input" SSE with reason="requires_input", message=user_input_reason
4.   → await _wait_for_user_input(...) (300s timeout — same as CAPTCHA / step_error)
5.   User types into InputRequestBanner → POST /api/task/{session_id}/input
6.   _wait_for_user_input returns the value
7. step = dict(step)  ← shallow copy!
8. step["user_provided_value"] = pre_step_input
9. emit "step_start" SSE  ← now fires, after user has acknowledged
10. build_executor_context(..., user_provided_value=step.get("user_provided_value"))
11. ADK runner executes with enriched context
```

**IMPORTANT**: `step = dict(step)` is a shallow copy done before assignment. This ensures:
- The original `step_plan["steps"]` list is not mutated (safe for potential retry paths)
- On a step retry (e.g., CAPTCHA detected after), `user_provided_value` is preserved in the copied `step` dict
- The pattern matches the defensive "don't mutate shared input" convention used throughout the executor

### `build_executor_context` Additive Extension (Task 4)

Current call signature (story 3.1–3.4):
```python
def build_executor_context(step_plan: dict, completed_steps: list[dict], screenshot_b64: str) -> str
```

After this story (backward-compatible, optional param):
```python
def build_executor_context(
    step_plan: dict,
    completed_steps: list[dict],
    screenshot_b64: str,
    user_provided_value: str | None = None,  # NEW
) -> str
```

Existing callers (none besides `executor_service.py`) continue to work unchanged. The new param is only passed when `step.get("user_provided_value")` is set.

### Firestore `onSnapshot` vs. SSE: Two Parallel Channels

| Channel | Purpose | Survives refresh? | Updates during execution? |
|---------|---------|-------------------|--------------------------|
| SSE (`useSSEConsumer`) | Live in-memory step status during execution | ❌ No | ✅ Yes — real-time |
| Firestore `onSnapshot` (`useFirestoreSession`) | Durable audit log | ✅ Yes (same tab) | ✅ Yes — fires after each `write_audit_log` |

Both hooks run in parallel when a session is active. SSE drives the live `steps: PlanStep[]` (in-memory). Firestore drives `auditLog: FirestoreAuditStep[]` (persisted). After task completion, `auditLog` fills in from Firestore `onSnapshot` and the `ThinkingPanel` renders it as the permanent record.

**Scope of FR37 in this story**: The `onSnapshot` hook reconnects automatically within the same browser tab on network interruptions thanks to the Firebase SDK's built-in retry logic. Full cross-tab / cross-session audit log restoration (storing `sessionId` in `localStorage` and hydrating on page load) is deferred to Story 3.6.

### Firebase SDK: No New Dependency

The frontend `package.json` already includes `"firebase": "^10.x"`. The `firebase/firestore` module is part of this package. Verify with:
```bash
cat aria-frontend/package.json | grep '"firebase"'
```
Expected: something like `"firebase": "^10.12.0"` or similar. No `npm install` needed.

### `handlers/audit_writer.py` Cleanup (Task 1)

The current stub has `from dotenv import load_dotenv` and `load_dotenv()` — these are not needed in a handler module (Django/FastAPI app loads env vars at startup via `run.py` / `main.py`). Remove them in Task 1 to keep the module clean.

The existing `update_session_status` wrapper function in `audit_writer.py` is already correct and used by `task_complete_service.py` — do NOT change it.

### Architecture Compliance

- **Firestore path**: `sessions/{session_id}` — established pattern from `session_service.py` (Stories 1.3–1.4)
- **Lazy Firestore client**: Use `_get_db()` pattern from `session_service.py` — do NOT instantiate a new client at module level (breaks test mocking)
- **Non-fatal audit writes**: The `try/except` wrapper in `executor_service.py` (Task 2) ensures Firestore failures never crash execution — this is mandatory per architecture reliability requirements
- **NFR11**: Step data scoped to `session_id` (linked to Firebase Anonymous Auth `uid` at session creation)
- **NFR10**: Screenshot URLs in audit log point to GCS paths scoped to `sessions/{session_id}/steps/` — no exfiltration risk
- **NFR7**: Browser session runs in sandboxed Chromium — audit log writer runs server-side only

### Previous Story Learnings (from Story 3.4)

- `_wait_for_user_input(session_id, step_index, paused_with, step_description)` is already implemented in `executor_service.py` and handles the 300s timeout + `task_failed` emission — use it directly for `requires_user_input` flow
- `input_queue_service.py` is fully tested and working — `get_input_queue`, `put_user_input`, `clear_input_queue`
- `InputRequestBanner` is already in `ThinkingPanel` and wired to `POST /api/task/{session_id}/input` — no new UI work for the user input flow
- The `awaiting_input` SSE event type, `taskStatus: "awaiting_input"`, and `awaitingInputMessage` store field are all live — the `requires_input` reason code is a new value but the same event type, compatible with existing frontend wiring
- `ThinkingPanel.tsx` already reads `awaitingInputMessage` from store and renders `InputRequestBanner` conditionally — verify the `onSubmitted` callback resets `taskStatus` to `"running"` (existing code does this correctly)
- `handlers/audit_writer.py` exists as a stub (`write_audit_log` is a no-op `pass`) since Story 3.1 — Task 1 implements the real body

### References

- [Source: aria-backend/handlers/audit_writer.py] — Stub to implement in Task 1
- [Source: aria-backend/services/executor_service.py] — Add `write_audit_log` call (Task 2) and `requires_user_input` handling (Task 3); update `build_executor_context` call (Task 3)
- [Source: aria-backend/services/session_service.py#_get_db] — Reference pattern for lazy Firestore client
- [Source: aria-backend/agents/executor_agent.py] — Extend `build_executor_context` signature (Task 4)
- [Source: aria-backend/services/task_complete_service.py] — Shows `audit_update_session_status` delegation pattern
- [Source: aria-frontend/src/lib/firebase.ts] — `app` singleton for `getFirestore(app)`
- [Source: aria-frontend/src/lib/store/aria-store.ts] — Add `auditLog: FirestoreAuditStep[]` (Task 5)
- [Source: aria-frontend/src/types/aria.ts] — Add `FirestoreAuditStep` interface (Task 5)
- [Source: aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx] — Mount hook + audit log render (Task 7)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5] — Epic story definition, ACs, FRs

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation proceeded without blocking issues.

### Completion Notes List

- Task 1: Replaced no-op stub in `audit_writer.py` with full implementation using lazy `_get_db()` pattern, `firestore.ArrayUnion`, and ISO 8601 timestamp formatting. Removed dotenv imports.
- Task 2: Added `write_audit_log` call in `executor_service.py` wrapped in `try/except` after `step_complete` emit, before `completed_steps.append()`. Uses the step's `action`, `description`, `confidence`, and `screenshot_url`.
- Task 3: Added `requires_user_input` pre-step check before `step_start` emit. Uses existing `_wait_for_user_input` with `paused_with="requires_input"`. Shallow-copies step dict to inject `user_provided_value` safely.
- Task 4: Extended `build_executor_context` with optional `user_provided_value: str | None = None` param — backward-compatible; appends user value to context string when set.
- Task 5: Added `FirestoreAuditStep` interface to `aria.ts` and `auditLog: FirestoreAuditStep[]` to store interface and initial state.
- Task 6: Created `useFirestoreSession.ts` hook with `onSnapshot` subscription, auditLog population, cleanup, and error logging.
- Task 7: Mounted `useFirestoreSession()` in `ThinkingPanel.tsx`, reads `auditLog` from store, renders audit log section conditionally when `panelStatus === "complete"` and `auditLog.length > 0`.
- Task 8: Created `test_audit_writer.py` (4 tests: all pass). Added 3 new tests to `test_executor_service.py` (tests 13–15: audit write on success, non-fatal audit failure, requires_user_input emits awaiting_input before step_start). All 124 backend tests pass.
- Task 9: Created `useFirestoreSession.test.ts` (6 tests). Added 4 audit log tests to `ThinkingPanel.test.tsx`. All 98 frontend tests pass.

### File List

**Backend:**
- `aria-backend/handlers/audit_writer.py` — implemented (replaced stub)
- `aria-backend/agents/executor_agent.py` — extended `build_executor_context` signature
- `aria-backend/services/executor_service.py` — added `write_audit_log` import, `requires_user_input` handling, audit log call, updated `build_executor_context` call
- `aria-backend/tests/test_audit_writer.py` — created (4 tests)
- `aria-backend/tests/test_executor_service.py` — added tests 13, 14, 15

**Frontend:**
- `aria-frontend/src/types/aria.ts` — added `FirestoreAuditStep` interface
- `aria-frontend/src/lib/store/aria-store.ts` — added `FirestoreAuditStep` import, `auditLog` to slice and initial state
- `aria-frontend/src/lib/hooks/useFirestoreSession.ts` — created
- `aria-frontend/src/lib/hooks/useFirestoreSession.test.ts` — created (6 tests)
- `aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx` — mounted hook, added audit log section
- `aria-frontend/src/components/thinking-panel/ThinkingPanel.test.tsx` — added 4 audit log tests

**Sprint tracking:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — updated `3-5-*` to `review`

## Change Log

- **2026-03-03**: Implemented Story 3.5 — Firestore audit log writer and mid-task input request
  - Replaced `write_audit_log` stub with full Firestore `ArrayUnion` implementation
  - Added non-fatal audit log write call in executor after each `step_complete`
  - Added `requires_user_input` pre-step check in executor loop (emits `awaiting_input` with `reason: "requires_input"`, waits for user, injects value into context)
  - Extended `build_executor_context` with backward-compatible `user_provided_value` param
  - Added `FirestoreAuditStep` type, `auditLog` store field, `useFirestoreSession` hook
  - Rendered audit log summary in `ThinkingPanel` when task is complete
  - 3 new backend tests, 10 new frontend tests; all regression suites green (124 backend, 98 frontend)
