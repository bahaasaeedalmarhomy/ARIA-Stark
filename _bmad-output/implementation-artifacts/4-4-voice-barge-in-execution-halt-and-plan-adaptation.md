# Story 4.4: Voice Barge-in — Execution Halt and Plan Adaptation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to be able to say "wait" or "stop" at any point during execution and have ARIA pause within 1 second and ask what I want to do next,
So that I am never trapped watching ARIA do the wrong thing.

## Acceptance Criteria

1. **Given** the Executor is actively running steps and the WebSocket audio relay is active, **When** frontend VAD detects user speech mid-execution (amplitude > `VAD_ONSET_THRESHOLD` while `voiceStatus === "speaking"`), **Then** `POST /api/task/{session_id}/barge-in` is called from `useVoice.ts`, which calls `signal_barge_in(session_id)` in `session_service.py`, setting the `asyncio.Event` cancel flag for that session.

2. **Given** the cancel flag is set by `signal_barge_in()`, **When** the Executor checks `cancel_flag.is_set()` via `PlaywrightComputer._check_cancel()` before or after any Playwright `await` call, **Then** `BargeInException` is raised, execution stops after the currently executing Playwright action completes (not mid-action), and the executor's outer `except BargeInException` handler fires.

3. **Given** `BargeInException` is caught and `is_user_cancel(session_id)` is `False` (voice barge-in, not Cancel Task button), **When** the exception is handled, **Then** a `task_paused` SSE event is emitted with `payload: {paused_at_step: N, reason: "barge_in"}`, Firestore `sessions/{session_id}.status` is updated to `"paused"`, and `reset_cancel_flag(session_id)` is called to clear the flag for the next execution.

4. **Given** a `task_paused` SSE event is received by the frontend, **When** `handleSSEEvent("task_paused")` processes it in `useSSEConsumer.ts`, **Then** `taskStatus` is set to `"paused"`, `panelStatus` is set to `"paused"`, the currently active step's `status` transitions to `"paused"`, and `voiceStatus` transitions to `"paused"` — all in response to a single SSE event.

5. **Given** `voiceStatus === "paused"` after a barge-in, **When** the ThinkingPanel renders the paused step, **Then** the step card shows "⏸ Paused — listening" text in violet (`text-violet-400`) alongside the active step information, and the `BargeInPulse` component (already present from Story 4.3) renders its ripple animation since `voiceStatus === "paused"`.

6. **Given** ARIA is paused and voice is in listening mode, **When** the user speaks a new instruction and Gemini Live transcribes it (captures it from `response.text` in the relay), **Then** the voice handler sends the transcription to a new `POST /api/task/{session_id}/voice-instruction` endpoint and triggers a re-planning cycle: the Planner is invoked with the original task, the new instruction, and the paused step index; a new `plan_ready` SSE event is emitted; and execution resumes from the current browser state (no page reload, no session restart).

7. **Given** the full barge-in flow is timed, **When** the user utterance begins, **Then** the Executor halts within 1 second of utterance start (NFR2: <1s from utterance to execution halt). The VAD fires at ~16ms cadence, the cancel flag sets synchronously, and the `_check_cancel()` guard triggers on the next Playwright `await`.

## Tasks / Subtasks

- [x] Task 1: Add `signal_barge_in()` function to `aria-backend/services/session_service.py` (AC: 1)
  - [x] Add `def signal_barge_in(session_id: str) -> None:` that calls `get_cancel_flag(session_id).set()` without calling `set_user_cancel_flag()` — this is the barge-in path (NOT user-cancel path)
  - [x] Document the distinction: `signal_barge_in()` → executor emits `task_paused`; `interrupt` endpoint → executor emits `task_failed` with `user_cancelled`

- [x] Task 2: Add `POST /api/task/{session_id}/barge-in` endpoint to `aria-backend/routers/task_router.py` (AC: 1)
  - [x] Import `signal_barge_in` from `services.session_service`
  - [x] Handler: call `signal_barge_in(session_id)` only (do NOT call `set_user_cancel_flag()`)
  - [x] Return `200` with `{"success": true, "data": {"barge_in": true}, "error": null}`
  - [x] No auth check — `session_id` (UUID v4) acts as implicit ownership token, consistent with `/interrupt` and `/input` endpoints

- [x] Task 3: Expand VAD barge-in trigger in `aria-frontend/src/lib/hooks/useVoice.ts` to also fire during `"speaking"` state (AC: 1)
  - [x] Change the VAD guard from `voiceStatus === "listening"` to `voiceStatus === "listening" || voiceStatus === "speaking"` in `startAmplitudeLoop()`'s tick function
  - [x] Add barge-in HTTP call: when VAD fires AND `taskStatus === "running"` AND `voiceStatus === "speaking"`, call `POST {BACKEND_URL}/api/task/{sessionId}/barge-in` (fire-and-forget fetch)
  - [x] Immediately set `voiceStatus: "paused"` in Zustand after calling the barge-in endpoint (instant visual feedback via `BargeInPulse` already present from Story 4.3)
  - [x] Read `sessionId` and `taskStatus` from `useARIAStore.getState()` inside the RAF callback (same synchronous-read pattern as `voiceStatus`)
  - [x] Add `bargeInSentRef = useRef(false)` to prevent multiple calls per barge-in event; reset it when `voiceStatus` is no longer `"speaking"` or in `disconnect()` cleanup

- [x] Task 4: Handle `task_paused` SSE event in `aria-frontend/src/lib/hooks/useSSEConsumer.ts` (AC: 4)
  - [x] Add `case "task_paused":` to `handleSSEEvent()` switch statement
  - [x] Set `taskStatus: "paused"`, `panelStatus: "paused"`, `voiceStatus: "paused"`
  - [x] Find the `active` step in `state.steps` and update its `status` to `"paused"`
  - [x] Add `"paused"` to `ThinkingPanelStatus` union in `aria-frontend/src/types/aria.ts`
  - [x] Add `"paused"` to `StepStatus` union in `aria-frontend/src/types/aria.ts`

- [x] Task 5: Update `StepItem` component to render paused visual state (AC: 5)
  - [x] In `aria-frontend/src/components/thinking-panel/StepItem.tsx`, add `"paused"` case to the status icon/card-styling logic
  - [x] Paused step card: `bg-zinc-800` background, violet left border (`border-l-2 border-violet-400`)
  - [x] Paused step status icon: render `⏸` (pause unicode) in `text-violet-400` or use `PauseIcon` from lucide-react
  - [x] Render `<span className="text-violet-400 text-xs font-medium">Paused — listening</span>` below the step description when `step.status === "paused"`

- [x] Task 6: Capture Gemini Live transcription in voice handler and forward to re-plan endpoint (AC: 6)
  - [x] In `aria-backend/handlers/voice_handler.py`, update `relay_gemini_to_browser()` to also capture `response.text` (transcription) when session is in `"paused"` state
  - [x] Add `voice_instruction_queue: dict[str, asyncio.Queue[str]] = {}` to `aria-backend/services/session_service.py` (or a new `voice_instruction_service.py`) with `create_voice_instruction_queue()`, `put_voice_instruction()`, `get_voice_instruction()`, `release_voice_instruction_queue()` helpers
  - [x] When `response.text` is received and session `status == "paused"`, put the transcription onto the queue via `put_voice_instruction(session_id, response.text)`

- [x] Task 7: Add `POST /api/task/{session_id}/voice-instruction` endpoint and re-plan service (AC: 6)
  - [x] Add endpoint in `aria-backend/routers/task_router.py` that accepts `{"instruction": str}` and calls `handle_voice_replan(session_id, instruction, paused_step_index)` as an async background task
  - [x] Implement `handle_voice_replan(session_id: str, instruction: str, paused_step_index: int)` in a new `aria-backend/services/replan_service.py`:
    - Load task description from Firestore (`get_session(session_id).task_description`)
    - Build combined instruction: `f"Original task: {task_desc}\nUser correction at step {paused_step_index}: {instruction}"`
    - Call the Planner agent (same pattern as in `task_router.py` start endpoint) to produce a new step plan
    - Emit a new `plan_ready` SSE event with the revised step plan
    - Update Firestore status to `"executing"`
    - Launch `asyncio.create_task(run_executor(session_id, new_step_plan))` to resume from current browser state

- [x] Task 8: Emit `task_paused` payload with `reason: "barge_in"` in `aria-backend/services/executor_service.py` (AC: 3)
  - [x] In the `except BargeInException` block (the `else` branch, i.e. NOT `is_user_cancel()`), update the emitted `task_paused` payload from `{"paused_at_step": N}` to `{"paused_at_step": N, "reason": "barge_in"}`
  - [x] This is a one-line addition; all other logic stays the same
  - [x] Also capture `paused_step_index` in the session service for use by `handle_voice_replan()`: call `set_paused_step(session_id, current_step_index)` (new helper in session_service.py)

- [x] Task 9: Store and retrieve `paused_step_index` per session in `aria-backend/services/session_service.py` (AC: 6)
  - [x] Add `_paused_step_indices: dict[str, int] = {}` module-level dict
  - [x] Add `set_paused_step(session_id: str, step_index: int) -> None`
  - [x] Add `get_paused_step(session_id: str) -> int:` (returns `0` if not found)
  - [x] Call `set_paused_step(session_id, current_step_index)` from executor_service.py's barge-in handler (after emitting `task_paused`)
  - [x] Clear it in `reset_cancel_flag()` (add `_paused_step_indices.pop(session_id, None)`)

- [x] Task 10: Write backend tests for new barge-in endpoint and signal_barge_in (AC: 1, 2, 3)
  - [x] Add test file `aria-backend/tests/test_barge_in_endpoint.py`
  - [x] Test: `POST /api/task/{session_id}/barge-in` returns 200 and sets cancel flag
  - [x] Test: `POST /api/task/{session_id}/barge-in` does NOT set `is_user_cancel()` flag (regression guard: must not trigger task_failed path)
  - [x] Test: `signal_barge_in()` sets cancel flag; `reset_cancel_flag()` clears it
  - [x] Test: executor emits `task_paused` (not `task_failed`) when `signal_barge_in()` is called — reuse existing test pattern from `test_interrupt_endpoint.py::test_run_executor_barge_in_without_user_cancel_emits_task_paused`
  - [x] Test: `task_paused` payload contains `reason: "barge_in"` field

- [x] Task 11: Write frontend tests for barge-in VAD expansion and `task_paused` SSE handler (AC: 1, 4, 5)
  - [x] Extend `aria-frontend/src/lib/hooks/useVoice.test.ts`: add test — VAD fires during `"speaking"` state (amplitude > threshold) triggers fetch to `/barge-in` endpoint and sets `voiceStatus: "paused"`
  - [x] Extend `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts`: add test — `task_paused` event sets `taskStatus: "paused"`, `panelStatus: "paused"`, `voiceStatus: "paused"`, and active step transitions to `status: "paused"`
  - [x] Extend `aria-frontend/src/components/thinking-panel/StepItem.test.tsx` (or create if absent): add test — step with `status: "paused"` renders violet border, pause icon, and "Paused — listening" text

## Dev Notes

### 🚨 CRITICAL: Distinction Between Barge-in and User-Cancel

The cancel flag mechanism already exists in `session_service.py`. There are **two** cancel paths producing **different outcomes**:

| Path | Who calls | What sets | Executor outcome |
|---|---|---|---|
| **Voice barge-in** | `signal_barge_in(session_id)` | `cancel_flag.set()` only | Emits `task_paused` |
| **User cancel (Cancel Task button)** | `/interrupt` endpoint | `cancel_flag.set()` + `set_user_cancel_flag()` | Emits `task_failed` + `reason: "user_cancelled"` |

Story 4.4 adds `signal_barge_in()` and a new `/barge-in` endpoint. The existing `/interrupt` endpoint must NOT be changed — it is the user-cancel path.

```python
# session_service.py — ADD this function below reset_cancel_flag():
def signal_barge_in(session_id: str) -> None:
    """
    Signal a voice barge-in for a session.
    Sets the cancel flag ONLY — does NOT set is_user_cancel().
    The executor will emit task_paused (not task_failed) in response.
    Called from POST /api/task/{session_id}/barge-in.
    """
    get_cancel_flag(session_id).set()
```

### 🚨 CRITICAL: Do NOT Change the Existing BargeInException Handler

`executor_service.py` lines ~464–498 already correctly distinguish `is_user_cancel()` vs. voice barge-in:
```python
except BargeInException as e:
    if is_user_cancel(session_id):
        # → task_failed / user_cancelled (unchanged)
    else:
        # → task_paused (this is our barge-in path)
        emit_event(session_id, "task_paused", {"paused_at_step": current_step_index})
        await update_session_status(session_id, "paused")
```
**The only change to executor_service.py is**: add `"reason": "barge_in"` to the `task_paused` payload and call `set_paused_step(session_id, current_step_index)`. Do NOT restructure the exception handler.

### VAD Barge-in During Speaking State (useVoice.ts)

Story 4.3 explicitly deferred "barge-in during speaking" to Story 4.4. The current VAD guard:
```typescript
// Story 4.3 (current — only fires during listening):
if (voiceStatus === "listening" && amplitude > VAD_ONSET_THRESHOLD) {

// Story 4.4 (this story — also fires during speaking):
if ((voiceStatus === "listening" || voiceStatus === "speaking") && amplitude > VAD_ONSET_THRESHOLD) {
```

Add a `bargeInSentRef` to prevent multiple HTTP calls per utterance:
```typescript
// Add to hook refs:
const bargeInSentRef = useRef(false);

// In tick() — after setting vadActive: true (the listening path stays unchanged):
const { voiceStatus, vadActive, sessionId, taskStatus } = useARIAStore.getState();

if ((voiceStatus === "listening" || voiceStatus === "speaking") && amplitude > VAD_ONSET_THRESHOLD) {
  if (!vadActive) {
    useARIAStore.setState({ vadActive: true });
  }

  // Barge-in trigger: fire ONCE per utterance when ARIA is speaking during execution
  if (voiceStatus === "speaking" && taskStatus === "running" && !bargeInSentRef.current) {
    bargeInSentRef.current = true;
    useARIAStore.setState({ voiceStatus: "paused" }); // immediate visual feedback
    // Fire-and-forget (no await — this is inside RAF/non-React context)
    fetch(`${BACKEND_URL}/api/task/${sessionId}/barge-in`, { method: "POST" }).catch(
      () => undefined // network errors are non-fatal here
    );
  }

  // Reset silence debounce (same as Story 4.3):
  if (vadTimerRef.current) clearTimeout(vadTimerRef.current);
  vadTimerRef.current = setTimeout(() => {
    useARIAStore.setState({ vadActive: false });
    bargeInSentRef.current = false; // reset for next utterance
    vadTimerRef.current = null;
  }, VAD_SILENCE_DEBOUNCE_MS);
}
```

Add `bargeInSentRef.current = false` to `disconnect()` cleanup.

**Import `BACKEND_URL` constant**: It's already defined in `useSSEConsumer.ts`. To avoid duplication, move it to `aria-frontend/src/lib/constants.ts` (create if absent: `export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";`) and import from both files.

### Frontend SSE Handler for task_paused

Add to `useSSEConsumer.ts` `handleSSEEvent()` switch:
```typescript
case "task_paused": {
  const payload = event.payload as { paused_at_step?: number; reason?: string };
  useARIAStore.setState((state) => {
    // Mark currently active step as paused
    const activeStep = state.steps.find((s) => s.status === "active");
    if (activeStep) activeStep.status = "paused";

    // Transition app-level state
    state.taskStatus = "paused";
    state.panelStatus = "paused";
    state.voiceStatus = "paused"; // triggers BargeInPulse + violet waveform (Story 4.3)
  });
  break;
}
```

Note: `voiceStatus` lives in `VoiceSlice` and is separate from `panelStatus`/`taskStatus` in `ThinkingPanelSlice`. `useARIAStore.setState()` with immer merges all slices correctly since `ARIAStore = SessionSlice & VoiceSlice & ThinkingPanelSlice`.

### TypeScript Type Updates Required

In `aria-frontend/src/types/aria.ts`:
```typescript
// BEFORE:
export type ThinkingPanelStatus =
  | "idle" | "planning" | "plan_ready" | "executing"
  | "awaiting_input" | "complete" | "failed";

// AFTER (add "paused"):
export type ThinkingPanelStatus =
  | "idle" | "planning" | "plan_ready" | "executing"
  | "awaiting_input" | "paused" | "complete" | "failed";

// BEFORE:
export type StepStatus = "pending" | "active" | "complete" | "error";

// AFTER (add "paused"):
export type StepStatus = "pending" | "active" | "paused" | "complete" | "error";

// BEFORE:
export type TaskStatus = "idle" | "running" | "paused" | ... (paused already exists ✓)
```

`TaskStatus` already includes `"paused"` — no change needed.

### Voice Handler — Transcription Capture (relay_gemini_to_browser)

The current handler in `voice_handler.py` ignores `response.text`:
```python
# Story 4.1 (current — ignores text):
async for response in gemini_session.receive():
    if response.data:
        await ws.send_bytes(response.data)
    # response.text (transcription) intentionally ignored — handled in Story 4.2+
```

Update for Story 4.4:
```python
async def relay_gemini_to_browser(
    ws: WebSocket,
    gemini_session,
    session_id: str,  # NEW: pass session_id to check pause state
) -> None:
    """Receive audio bytes from Gemini Live and forward them immediately to the browser."""
    async for response in gemini_session.receive():
        if response.data:
            await ws.send_bytes(response.data)
        # Capture transcription ONLY when session is paused (barge-in mode)
        if response.text:
            from services.session_service import get_session_status  # lazy import
            # Check if session is in paused state before acting on transcription
            # (avoid acting on normal narration transcripts)
            # Use voice_instruction_queue to deliver to re-plan endpoint
            from services.voice_instruction_service import try_put_instruction
            try_put_instruction(session_id, response.text)
```

Add `session_id` parameter to the `relay_gemini_to_browser` task launch in `audio_relay()`:
```python
asyncio.create_task(relay_gemini_to_browser(websocket, gemini_session, session_id)),
```

### Voice Instruction Service (new file)

Create `aria-backend/services/voice_instruction_service.py`:
```python
import asyncio

_queues: dict[str, asyncio.Queue[str]] = {}

def create_voice_instruction_queue(session_id: str) -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    _queues[session_id] = q
    return q

def try_put_instruction(session_id: str, text: str) -> None:
    """Non-blocking put. Silently drops if no queue exists or queue is full."""
    q = _queues.get(session_id)
    if q:
        try:
            q.put_nowait(text)
        except asyncio.QueueFull:
            pass  # Already has an instruction queued; skip duplicate

async def get_instruction(session_id: str, timeout: float = 30.0) -> str | None:
    """Await an instruction from the user. Returns None on timeout."""
    q = _queues.get(session_id)
    if not q:
        return None
    try:
        return await asyncio.wait_for(q.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None

def release_voice_instruction_queue(session_id: str) -> None:
    _queues.pop(session_id, None)
```

### Re-plan Service

Create `aria-backend/services/replan_service.py`:

```python
import asyncio
import logging
from services.session_service import get_session, update_session_status, set_paused_step
from services.sse_service import emit_event
from services.voice_instruction_service import (
    create_voice_instruction_queue, get_instruction, release_voice_instruction_queue
)
from services.executor_service import run_executor

logger = logging.getLogger(__name__)

async def wait_for_voice_instruction_and_replan(
    session_id: str,
    paused_at_step: int,
) -> None:
    """
    Wait for user voice instruction, invoke Planner with correction,
    emit new plan_ready, and resume executor.

    Called as an asyncio.create_task() after task_paused is emitted.
    """
    create_voice_instruction_queue(session_id)
    try:
        instruction = await get_instruction(session_id, timeout=60.0)
        if not instruction:
            logger.warning("No voice instruction received for session %s within 60s", session_id)
            emit_event(session_id, "task_failed", {"reason": "barge_in_timeout"})
            await update_session_status(session_id, "failed")
            return

        session = await get_session(session_id)
        task_desc = session.get("task_description", "")
        combined = (
            f"Original task: {task_desc}\n"
            f"User interrupted at step {paused_at_step} with correction: {instruction}"
        )

        # Invoke Planner (same as task_router.py start flow — import and call run_planner)
        from services.planner_service import run_planner  # deferred import
        new_step_plan = await run_planner(combined)

        emit_event(
            session_id,
            "plan_ready",
            {
                "steps": new_step_plan.get("steps", []),
                "task_summary": new_step_plan.get("task_summary", ""),
                "is_replan": True,  # hints frontend this replaces an existing plan
            },
        )
        await update_session_status(session_id, "executing")
        await run_executor(session_id, new_step_plan)

    finally:
        release_voice_instruction_queue(session_id)
```

### Task Router — voice-instruction Endpoint and Re-plan Integration

Add to `aria-backend/routers/task_router.py`:
```python
@router.post("/{session_id}/barge-in")
async def barge_in_task(session_id: str):
    """
    POST /api/task/{session_id}/barge-in
    Signal a voice barge-in — sets cancel flag without user_cancel marker.
    Executor will emit task_paused (not task_failed).
    Then schedules wait_for_voice_instruction_and_replan as a background task.
    """
    signal_barge_in(session_id)
    # Schedule re-plan after barge-in (non-blocking)
    paused_step = get_paused_step(session_id)  # may be 0 if not yet set
    asyncio.create_task(wait_for_voice_instruction_and_replan(session_id, paused_step))
    return JSONResponse(
        status_code=200,
        content={"success": True, "data": {"barge_in": True}, "error": None},
    )
```

Wait — there's a subtle race condition here: the executor hasn't fired yet when the `/barge-in` endpoint returns, so `get_paused_step()` won't have the correct step yet. Better to trigger `wait_for_voice_instruction_and_replan` from within the executor itself after it emits `task_paused`. Update `executor_service.py` barge-in handler:
```python
except BargeInException as e:
    if not is_user_cancel(session_id):
        emit_event(session_id, "task_paused", {"paused_at_step": current_step_index, "reason": "barge_in"})
        await update_session_status(session_id, "paused")
        set_paused_step(session_id, current_step_index)
        # Schedule re-plan listening loop (launched AFTER task_paused is emitted)
        asyncio.create_task(
            wait_for_voice_instruction_and_replan(session_id, current_step_index)
        )
```

The `/barge-in` endpoint then only needs to call `signal_barge_in(session_id)` (no task scheduling).

### plan_ready Re-plan Handling on Frontend

When `is_replan: true` is present in `plan_ready` payload, the frontend should reset:
- `steps` replaced with new plan steps (all `"pending"`)
- `panelStatus: "plan_ready"` (retriggers stagger animation from Story 2.5)
- `taskStatus: "running"`
- `voiceStatus: "listening"` (ARIA is back to ambient listening, not paused)

Update `case "plan_ready":` in `useSSEConsumer.ts`:
```typescript
case "plan_ready": {
  const payload = event.payload as {
    steps: PlanStep[];
    task_summary: string;
    is_replan?: boolean;
  };
  useARIAStore.setState((state) => {
    state.steps = payload.steps.map((s) => ({
      ...s,
      status: "pending" as StepStatus,
    }));
    state.taskSummary = payload.task_summary;
    state.panelStatus = "plan_ready";
    if (payload.is_replan) {
      state.taskStatus = "running";
      state.voiceStatus = "listening"; // clear paused state
    }
  });
  break;
}
```

### StepItem Visual State for paused

In `aria-frontend/src/components/thinking-panel/StepItem.tsx` (already exists from Story 2.4), add the `"paused"` case alongside existing status cases:

```tsx
// Status icon (existing pattern extended):
const statusIcon = {
  pending: <span className="w-2 h-2 rounded-full bg-zinc-500" />,
  active: <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />,
  paused: <span className="text-violet-400 text-sm">⏸</span>,  // ADD
  complete: <CheckCircle className="w-4 h-4 text-emerald-500" />,
  error: <XCircle className="w-4 h-4 text-rose-500" />,
}[step.status];

// Card border accent (extend existing):
const borderClass = {
  active: "border-l-2 border-blue-500",
  paused: "border-l-2 border-violet-400",  // ADD
  error: "border-l-2 border-rose-500",
}[step.status] ?? "";
```

And add the inline "Paused — listening" label:
```tsx
{step.status === "paused" && (
  <span className="text-violet-400 text-xs font-medium mt-1 block">
    Paused — listening
  </span>
)}
```

### NFR2: <1 Second Halt Budget

The 1-second halt budget (NFR2) is met by the existing architecture:
- Frontend VAD fires at ~16ms cadence (RAF loop, Story 4.3)
- `fetch()` to `/barge-in` is non-blocking (~50–100ms round trip to Cloud Run)
- Backend sets `asyncio.Event` synchronously O(1)
- Executor polls `_check_cancel()` before and after every Playwright `await`
- Playwright actions (click, type, navigate) complete in <300ms on a loaded page
- Total: 16ms (VAD) + 100ms (HTTP) + <300ms (Playwright action boundary) = ~416ms — within 1 second budget

### Existing Tests — What Must NOT Break

All tests from Stories 4.1/4.2/4.3 that are currently passing:
- `test_interrupt_endpoint.py`: 5 tests — the `/interrupt` endpoint and user-cancel path are UNCHANGED
- `test_executor_service.py`: test that `BargeInException` (non-user-cancel) emits `task_paused` — still holds; adding `reason: "barge_in"` to payload is backward-compatible (additive field)
- `test_executor_agent.py`: 7 tests — `_check_cancel()` and `BargeInException` behavior unchanged
- `aria-frontend` voice tests: 168 tests currently passing. Extending VAD guard to include `"speaking"` must not break existing tests for `"listening"` behavior

Current test count per iteration: 168 frontend, ~60 backend. Any regression must be fixed before task is complete.

### Project Structure Notes

**Backend new files:**
- `aria-backend/services/replan_service.py` — CREATE: `wait_for_voice_instruction_and_replan()`
- `aria-backend/services/voice_instruction_service.py` — CREATE: per-session instruction queue
- `aria-backend/tests/test_barge_in_endpoint.py` — CREATE: 5+ tests

**Backend modified files:**
- `aria-backend/services/session_service.py` — ADD: `signal_barge_in()`, `set_paused_step()`, `get_paused_step()`, `_paused_step_indices` dict
- `aria-backend/services/executor_service.py` — MODIFY: add `reason: "barge_in"` to `task_paused` payload, call `set_paused_step()`, launch `wait_for_voice_instruction_and_replan` task
- `aria-backend/handlers/voice_handler.py` — MODIFY: `relay_gemini_to_browser()` captures `response.text` when paused and calls `try_put_instruction()`; add `session_id` param
- `aria-backend/routers/task_router.py` — ADD: `POST /{session_id}/barge-in` endpoint

**Frontend new files:** none

**Frontend modified files:**
- `aria-frontend/src/types/aria.ts` — ADD `"paused"` to `ThinkingPanelStatus` and `StepStatus`
- `aria-frontend/src/lib/hooks/useVoice.ts` — MODIFY: expand VAD guard to `"speaking"`, add barge-in fetch, add `bargeInSentRef`
- `aria-frontend/src/lib/hooks/useSSEConsumer.ts` — ADD: `task_paused` case; update `plan_ready` case for `is_replan`
- `aria-frontend/src/components/thinking-panel/StepItem.tsx` — MODIFY: add `"paused"` status rendering
- `aria-frontend/src/lib/constants.ts` — CREATE: `BACKEND_URL` constant (move from `useSSEConsumer.ts`)

**Frontend modified tests:**
- `aria-frontend/src/lib/hooks/useVoice.test.ts` — ADD: 2+ tests for speaking-state VAD barge-in
- `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts` — ADD: 2+ tests for `task_paused` handler
- `aria-frontend/src/components/thinking-panel/StepItem.test.tsx` — ADD: 2+ tests for paused state

### References

- Barge-in cancel flag: [aria-backend/services/session_service.py](aria-backend/services/session_service.py) — `get_cancel_flag()`, `reset_cancel_flag()`, `set_user_cancel_flag()`
- BargeInException: [aria-backend/tools/playwright_computer.py](aria-backend/tools/playwright_computer.py#L23) — `_check_cancel()` pattern
- Executor barge-in handler: [aria-backend/services/executor_service.py](aria-backend/services/executor_service.py) — `except BargeInException` block (~line 464)
- Voice relay handler: [aria-backend/handlers/voice_handler.py](aria-backend/handlers/voice_handler.py) — `relay_gemini_to_browser()` and `audio_relay()`
- useVoice VAD logic: [aria-frontend/src/lib/hooks/useVoice.ts](aria-frontend/src/lib/hooks/useVoice.ts#L87) — `startAmplitudeLoop()` tick function
- SSE consumer: [aria-frontend/src/lib/hooks/useSSEConsumer.ts](aria-frontend/src/lib/hooks/useSSEConsumer.ts) — `handleSSEEvent()` switch
- Zustand store: [aria-frontend/src/lib/store/aria-store.ts](aria-frontend/src/lib/store/aria-store.ts) — `VoiceSlice`, `ThinkingPanelSlice`
- BargeInPulse (already functional from Story 4.3): `voiceStatus === "paused"` already triggers it — no changes needed
- Story 4.3 dev notes: [_bmad-output/implementation-artifacts/4-3-voicewaveform-bargeinpulse-components-and-vad-visual-states.md](_bmad-output/implementation-artifacts/4-3-voicewaveform-bargeinpulse-components-and-vad-visual-states.md) — VAD threshold, antipatterns, Zustand write patterns
- Interrupt endpoint pattern: [aria-backend/routers/task_router.py](aria-backend/routers/task_router.py#L195) — `POST /{session_id}/interrupt`
- Previous barge-in regression test: [aria-backend/tests/test_interrupt_endpoint.py](aria-backend/tests/test_interrupt_endpoint.py) — `test_run_executor_barge_in_without_user_cancel_emits_task_paused`
- NFR2 barge-in timing: [Source: _bmad-output/planning-artifacts/epics.md#NonFunctional Requirements]
- FR24–FR26: [Source: _bmad-output/planning-artifacts/epics.md#Voice Interaction & Barge-in]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

No blockers encountered. All implementation followed the Dev Notes specification exactly.

### Completion Notes List

- ✅ Task 1: Added `signal_barge_in()` to `session_service.py` — sets cancel flag only, no `is_user_cancel()` marker
- ✅ Task 2: Added `POST /api/task/{session_id}/barge-in` endpoint to `task_router.py` — returns 200 with `{barge_in: true}`
- ✅ Task 3: Expanded VAD guard in `useVoice.ts` to fire on `"speaking"` state; added `bargeInSentRef` dedup ref; fire-and-forget barge-in fetch; moves `BACKEND_URL` to `constants.ts`
- ✅ Task 4: Added `case "task_paused":` to `useSSEConsumer.ts`; updated `plan_ready` case for `is_replan`; added `"paused"` to `ThinkingPanelStatus` and `StepStatus` types
- ✅ Task 5: Updated `StepItem.tsx` with violet border, ⏸ icon, and "Paused — listening" label for paused state
- ✅ Task 6: Updated `relay_gemini_to_browser()` in `voice_handler.py` to accept `session_id` and call `try_put_instruction()` when `response.text` is received; created `voice_instruction_service.py`
- ✅ Task 7: Created `replan_service.py` with `wait_for_voice_instruction_and_replan()`; re-plan launched as asyncio task from executor's barge-in handler (not barge-in endpoint, avoiding race condition noted in Dev Notes)
- ✅ Task 8: Updated executor `task_paused` payload to include `"reason": "barge_in"`; added `set_paused_step()` call; launches `wait_for_voice_instruction_and_replan` task
- ✅ Task 9: Added `_paused_step_indices`, `set_paused_step()`, `get_paused_step()` to `session_service.py`; cleared in `reset_cancel_flag()`
- ✅ Task 10: Created `test_barge_in_endpoint.py` with 5 tests — all passing
- ✅ Task 11: Added 10 new frontend tests (VAD speaking, barge-in fetch, task_paused SSE, plan_ready is_replan, StepItem paused state) — all 178 frontend tests passing

**Race condition note (from Dev Notes):** The `wait_for_voice_instruction_and_replan` task is launched from within `executor_service.py`'s barge-in handler (after `task_paused` is emitted), NOT from the `/barge-in` endpoint. This avoids the race where `get_paused_step()` wouldn't yet have the correct step index when the HTTP response returns.

**Test counts:** Backend: 175 passed (5 new), Frontend: 178 passed (10 new from Story 4.4).

### File List

**Backend new files:**
- `aria-backend/services/voice_instruction_service.py`
- `aria-backend/services/replan_service.py`
- `aria-backend/tests/test_barge_in_endpoint.py`

**Backend modified files:**
- `aria-backend/services/session_service.py`
- `aria-backend/services/executor_service.py`
- `aria-backend/handlers/voice_handler.py`
- `aria-backend/routers/task_router.py`

**Frontend new files:**
- `aria-frontend/src/lib/constants.ts`

**Frontend modified files:**
- `aria-frontend/src/types/aria.ts`
- `aria-frontend/src/lib/hooks/useVoice.ts`
- `aria-frontend/src/lib/hooks/useSSEConsumer.ts`
- `aria-frontend/src/components/thinking-panel/StepItem.tsx`

**Frontend modified tests:**
- `aria-frontend/src/lib/hooks/useVoice.test.ts`
- `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts`
- `aria-frontend/src/components/thinking-panel/StepItem.test.tsx`
