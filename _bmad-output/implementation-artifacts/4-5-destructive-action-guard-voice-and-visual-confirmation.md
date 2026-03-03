# Story 4.5: Destructive Action Guard — Voice and Visual Confirmation

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want ARIA to always pause and ask for my explicit confirmation — both spoken aloud and shown on screen — before it submits a form, makes a purchase, deletes a record, or publishes content,
so that I am never surprised by an irreversible action I didn't intend.

## Acceptance Criteria

1. **Given** the Executor reaches a step where `is_destructive: true`, **When** it evaluates the step before executing, **Then** it does NOT execute the action and instead emits an `awaiting_confirmation` SSE event with `payload: {step_index, action_description, warning: "This action cannot be undone"}`.

2. **Given** an `awaiting_confirmation` SSE event is received, **When** the frontend processes it, **Then** a `ConfirmActionDialog` is displayed over the thinking panel with the action description, a warning banner in rose (`signal-danger`/`text-rose-500`), a "Confirm" button, and a "Cancel" button — all keyboard-accessible (Enter = Confirm, Escape = Cancel, NFR19).

3. **Given** the confirmation dialog is shown, **When** it renders, **Then** ARIA simultaneously speaks aloud via TTS: `"I'm about to [action_description]. This action cannot be undone — shall I proceed?"` — voice and visual confirmation fire within 500ms of each other (FR30). The TTS is delivered by injecting text into the Gemini Live session via the `tts_queue_service`.

4. **Given** the confirmation dialog is displayed, **When** the user says "yes" / "confirm" / "proceed" audibly, **Then** Gemini Live transcribes the utterance → `relay_gemini_to_browser()` detects a confirmation keyword while session status is `"awaiting_confirmation"` → `deliver_confirmation(session_id, True)` is called → dialog dismisses → Executor proceeds with the destructive action (FR31).

5. **Given** the confirmation dialog is displayed, **When** the user says "no" / "cancel" / "stop" or clicks "Cancel", **Then** `deliver_confirmation(session_id, False)` is called (or `POST /api/task/{session_id}/confirm` with `{"confirmed": false}`) → dialog dismisses → a `task_paused` SSE event is emitted → execution halts in a state where the user can provide a new direction (FR32).

6. **Given** the confirmation dialog is displayed, **When** the user clicks "Confirm" in the UI, **Then** `POST /api/task/{session_id}/confirm` is called with `{"confirmed": true}` → dialog dismisses → Executor proceeds with the destructive action (FR31).

7. **Given** the confirmation dialog is displayed, **When** 60 seconds pass with no response, **Then** the action is automatically cancelled (safe default), a `task_paused` SSE event is emitted, and `taskStatus` transitions to `"paused"` — ARIA never proceeds on timeout (FR32 safe default).

8. **Given** the destructive action detection is tested across all demo scenarios, **When** form submissions, purchases, deletions, and publish actions are executed, **Then** 100% are detected and guarded — zero silent destructive actions occur (NFR: 100% detection rate, enforced by `is_destructive: true` on the Planner step).

## Tasks / Subtasks

- [ ] Task 1: Create `aria-backend/services/confirmation_queue_service.py` (AC: 1, 5, 6, 7)
  - [ ] Implement `create_confirmation_queue(session_id: str) -> asyncio.Queue[bool]`
  - [ ] Implement `deliver_confirmation(session_id: str, confirmed: bool) -> None` — non-blocking `put_nowait`
  - [ ] Implement `wait_for_confirmation(session_id: str, timeout: float = 60.0) -> bool | None` — returns `None` on timeout
  - [ ] Implement `release_confirmation_queue(session_id: str) -> None` — pops from `_confirmation_queues` dict
  - [ ] Implement `has_confirmation_queue(session_id: str) -> bool`
  - [ ] Pattern: mirror `input_queue_service.py` exactly (dict of `asyncio.Queue[bool]`)

- [ ] Task 2: Create `aria-backend/services/tts_queue_service.py` (AC: 3)
  - [ ] Implement `create_tts_queue(session_id: str) -> asyncio.Queue[str | None]`
  - [ ] Implement `try_put_tts_text(session_id: str, text: str) -> None` — non-blocking, silently drops if no queue exists
  - [ ] Implement `get_tts_text(session_id: str) -> asyncio.Queue[str | None] | None` — returns the queue or `None`
  - [ ] Implement `release_tts_queue(session_id: str) -> None`
  - [ ] Pattern: same dict-of-queues pattern as `voice_instruction_service.py`

- [ ] Task 3: Add `is_destructive` guard to `aria-backend/services/executor_service.py` (AC: 1, 5, 7)
  - [ ] In the step loop, AFTER `step_start` is emitted but BEFORE the attempt/retry loop, add:
    ```python
    # Destructive action guard (Story 4.5)
    if step.get("is_destructive", False):
        action_description = step_description
        emit_event(session_id, "awaiting_confirmation", {
            "step_index": current_step_index,
            "action_description": action_description,
            "warning": "This action cannot be undone",
        })
        await update_session_status(session_id, "awaiting_confirmation")
        # Inject TTS confirmation prompt into Gemini Live (FR30)
        from services.tts_queue_service import try_put_tts_text
        try_put_tts_text(
            session_id,
            f"I'm about to {action_description}. This action cannot be undone — shall I proceed?"
        )
        # Create queue and wait (max 60s)
        from services.confirmation_queue_service import (
            create_confirmation_queue, wait_for_confirmation, release_confirmation_queue
        )
        create_confirmation_queue(session_id)
        confirmed = await wait_for_confirmation(session_id, timeout=60.0)
        release_confirmation_queue(session_id)
        if confirmed is None or not confirmed:
            # Timeout or explicit cancel — safe default: do NOT execute
            emit_event(session_id, "task_paused", {
                "paused_at_step": current_step_index,
                "reason": "destructive_action_cancelled",
            })
            await update_session_status(session_id, "paused")
            return
        # User confirmed — restore executing status and proceed
        await update_session_status(session_id, "executing")
    ```
  - [ ] Add `release_confirmation_queue` call in the `finally` block (after `clear_input_queue`) for safety
  - [ ] `BargeInException` must still propagate through the destructive guard — if a barge-in arrives while waiting for confirmation, the `BargeInException` pathway must fire. (Note: `asyncio.wait_for` inside `wait_for_confirmation` will be interrupted when the cancel flag sets via a separate cancel mechanism — ensure the existing `_check_cancel()` mechanism is covered OR use a separate task that reads barge-in cancellation. See Dev Notes.)

- [ ] Task 4: Add `POST /{session_id}/confirm` endpoint to `aria-backend/routers/task_router.py` (AC: 5, 6)
  - [ ] Add `ConfirmRequest` Pydantic model: `confirmed: bool`
  - [ ] Add `@router.post("/{session_id}/confirm")` handler:
    - Import `deliver_confirmation` from `services.confirmation_queue_service`
    - Import `has_confirmation_queue` from `services.confirmation_queue_service`
    - If `not has_confirmation_queue(session_id)`, return `_error_response("CONFIRMATION_NOT_EXPECTED", "No pending confirmation for this session", 404)`
    - Call `deliver_confirmation(session_id, body.confirmed)`
    - Return `JSONResponse(200, {"success": True, "data": {"confirmed": body.confirmed}, "error": None})`
  - [ ] No auth check — `session_id` (UUID v4) acts as implicit ownership token (consistent with `/interrupt`, `/barge-in`, `/input`)

- [ ] Task 5: Modify `aria-backend/handlers/voice_handler.py` for TTS injection and voice confirmation detection (AC: 3, 4)
  - [ ] **Add TTS injection task**: Create `inject_tts_to_gemini(tts_queue, gemini_session)` coroutine:
    ```python
    async def inject_tts_to_gemini(
        tts_queue: asyncio.Queue,
        gemini_session,
    ) -> None:
        """Forward text-to-speech requests to Gemini Live as text turns."""
        while True:
            text = await tts_queue.get()
            if text is None:
                break
            await gemini_session.send(input=text, end_of_turn=True)
    ```
  - [ ] In `audio_relay()`, create TTS queue and add `inject_tts_to_gemini` task:
    ```python
    from services.tts_queue_service import create_tts_queue, release_tts_queue
    tts_queue = create_tts_queue(session_id)
    tasks = [
        asyncio.create_task(relay_inbound_to_queue(websocket, inbound_queue)),
        asyncio.create_task(drain_queue_to_gemini(inbound_queue, gemini_session)),
        asyncio.create_task(relay_gemini_to_browser(websocket, gemini_session, session_id)),
        asyncio.create_task(inject_tts_to_gemini(tts_queue, gemini_session)),  # NEW
    ]
    ```
  - [ ] In the `finally` block, signal `inject_tts_to_gemini` to stop: `tts_queue.put_nowait(None)` and call `release_tts_queue(session_id)`
  - [ ] **Extend `relay_gemini_to_browser()`** to detect confirmation keywords in `response.text`:
    ```python
    if response.text:
        from services.voice_instruction_service import try_put_instruction
        try_put_instruction(session_id, response.text)
        # Voice confirmation detection (Story 4.5)
        from services.session_service import get_session_status
        from services.confirmation_queue_service import has_confirmation_queue, deliver_confirmation
        if has_confirmation_queue(session_id):
            text_lower = response.text.strip().lower()
            CONFIRM_WORDS = {"yes", "confirm", "proceed", "go ahead", "do it"}
            DENY_WORDS = {"no", "cancel", "stop", "don't", "abort"}
            if any(text_lower.startswith(w) for w in CONFIRM_WORDS):
                deliver_confirmation(session_id, True)
            elif any(text_lower.startswith(w) for w in DENY_WORDS):
                deliver_confirmation(session_id, False)
    ```

- [ ] Task 6: Update `aria-frontend/src/types/aria.ts` (AC: 2)
  - [ ] Add `"awaiting_confirmation"` to `ThinkingPanelStatus` union (note: `TaskStatus` already has it)
  - [ ] Add `ConfirmationRequest` interface:
    ```typescript
    export interface ConfirmationRequest {
      step_index: number;
      action_description: string;
      warning: string;
    }
    ```

- [ ] Task 7: Update `aria-frontend/src/lib/store/aria-store.ts` (AC: 2)
  - [ ] Import `ConfirmationRequest` from `@/types/aria`
  - [ ] Add `confirmationRequest: ConfirmationRequest | null` field to `ThinkingPanelSlice`
  - [ ] Add `confirmationRequest: null` to `ARIA_INITIAL_STATE`

- [ ] Task 8: Add `awaiting_confirmation` SSE case to `aria-frontend/src/lib/hooks/useSSEConsumer.ts` (AC: 2, 5)
  - [ ] Add case in `handleSSEEvent()` switch (after `task_paused`):
    ```typescript
    case "awaiting_confirmation": {
      const payload = event.payload as {
        step_index: number;
        action_description: string;
        warning: string;
      };
      useARIAStore.setState({
        taskStatus: "awaiting_confirmation",
        panelStatus: "awaiting_confirmation",
        confirmationRequest: {
          step_index: payload.step_index,
          action_description: payload.action_description,
          warning: payload.warning,
        },
      });
      break;
    }
    ```
  - [ ] Note: `task_paused` case already exists — ensures dialog dismisses by setting `confirmationRequest: null` inside the `task_paused` case (add `state.confirmationRequest = null;`). Also add `state.confirmationRequest = null;` to `task_complete`, `task_failed` cases.

- [ ] Task 9: Create `aria-frontend/src/components/thinking-panel/ConfirmActionDialog.tsx` (AC: 2, 6)
  - [ ] Props: `{ request: ConfirmationRequest; sessionId: string; onDismiss: () => void }`
  - [ ] Layout: modal overlay (`fixed inset-0 bg-black/60 flex items-center justify-center z-50`)
  - [ ] Inner card: `bg-zinc-900 border border-rose-500/50 rounded-lg p-6 max-w-md w-full shadow-xl`
  - [ ] Rose warning banner: `<div className="bg-rose-500/10 border border-rose-500/30 rounded px-3 py-2 mb-4 flex items-center gap-2 text-rose-400 text-sm">⚠️ {request.warning}</div>`
  - [ ] Action description: `<p className="text-text-primary text-sm mb-6">{request.action_description}</p>`
  - [ ] Buttons row: `<div className="flex gap-3 justify-end">`
    - Cancel button: `bg-zinc-800 text-text-secondary hover:bg-zinc-700`, calls `handleDecline()`
    - Confirm button: `bg-rose-600 text-white hover:bg-rose-700`, calls `handleConfirm()`
  - [ ] `handleConfirm()`: `POST ${BACKEND_URL}/api/task/${sessionId}/confirm` with body `{confirmed: true}`, then `onDismiss()`
  - [ ] `handleDecline()`: `POST ${BACKEND_URL}/api/task/${sessionId}/confirm` with body `{confirmed: false}`, then `onDismiss()`
  - [ ] Keyboard: `onKeyDown` handler on the modal — `Enter` → `handleConfirm()`, `Escape` → `handleDecline()`; add `role="dialog"`, `aria-modal="true"`, `aria-label="Confirm Action"` for accessibility
  - [ ] `autoFocus` on Cancel button (safer default per UX spec and FR32)
  - [ ] Import `BACKEND_URL` from `@/lib/constants` (already exists from Story 4.4)

- [ ] Task 10: Integrate `ConfirmActionDialog` into `aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx` (AC: 2)
  - [ ] Add `confirmationRequest` and `sessionId` to store reads at component top
  - [ ] Render dialog just before the closing `</div>` of the outer container:
    ```tsx
    {confirmationRequest && sessionId && (
      <ConfirmActionDialog
        request={confirmationRequest}
        sessionId={sessionId}
        onDismiss={() =>
          useARIAStore.setState({
            confirmationRequest: null,
            taskStatus: "paused",
            panelStatus: "paused",
          })
        }
      />
    )}
    ```
  - [ ] Import `ConfirmActionDialog` from `./ConfirmActionDialog`
  - [ ] Add `"awaiting_confirmation"` case to the `headerClass` and `headerLabel` logic (rose text `text-rose-400`, label `"Awaiting Confirmation"`)

- [ ] Task 11: Write backend tests in `aria-backend/tests/test_destructive_action_guard.py` (AC: 1, 5, 6, 7)
  - [ ] Test: `POST /api/task/{session_id}/confirm` with `{"confirmed": true}` returns 200 and delivers confirmation
  - [ ] Test: `POST /api/task/{session_id}/confirm` with `{"confirmed": false}` returns 200 and delivers cancellation
  - [ ] Test: `POST /api/task/{session_id}/confirm` returns 404 when no confirmation queue exists
  - [ ] Test: `wait_for_confirmation()` returns `None` after timeout (60s)
  - [ ] Test: Executor emits `awaiting_confirmation` SSE and does NOT execute step when `is_destructive: True` — use executor test mock pattern from `test_executor_service.py`
  - [ ] Test: Executor emits `task_paused` with `reason: "destructive_action_cancelled"` when `confirmed=False`
  - [ ] Test: Executor proceeds to execute step when `confirmed=True`
  - [ ] Test: `confirmation_queue_service` — `create`, `deliver`, `wait_for` cycle completes correctly

- [ ] Task 12: Write frontend tests (AC: 2, 6)
  - [ ] `aria-frontend/src/components/thinking-panel/ConfirmActionDialog.test.tsx` (CREATE):
    - Renders dialog with action description and rose warning banner
    - "Confirm" button calls POST `/confirm` with `{confirmed: true}` and calls `onDismiss`
    - "Cancel" button calls POST `/confirm` with `{confirmed: false}` and calls `onDismiss`
    - Enter keypress triggers confirm
    - Escape keypress triggers decline
    - Cancel button has autoFocus
  - [ ] `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts` (EXTEND):
    - `awaiting_confirmation` event sets `taskStatus: "awaiting_confirmation"`, `panelStatus: "awaiting_confirmation"`, and populates `confirmationRequest`
    - `task_paused` event clears `confirmationRequest`
    - `task_complete` event clears `confirmationRequest`
    - `task_failed` event clears `confirmationRequest`

## Dev Notes

### 🚨 CRITICAL: Executor Step Loop Position — Destructive Guard Must Fire AFTER `step_start`, BEFORE Attempt Loop

The destructive guard must be inserted in `executor_service.py` AFTER `step_start` is emitted (so the frontend transitions the step to `"active"` — shows the user which step is being guarded) but BEFORE the `while not step_resolved:` attempt loop (so the Playwright runner never executes the destructive action without confirmation):

```python
# EXISTING: Emit step_start BEFORE retry loop (AC: 1, 5)
emit_event(session_id, "step_start", {...})

# NEW: Destructive action guard — MUST be here, after step_start, before attempt loop
if step.get("is_destructive", False):
    # ... emit awaiting_confirmation, wait, handle result ...

# EXISTING: attempt loop
step_resolved = False
while not step_resolved:
    for attempt in range(_MAX_STEP_ATTEMPTS):
        ...
```

The insertion point is around line 186 in `executor_service.py` (after the `emit_event(session_id, "step_start", ...)` call ending around line 184, before `step_resolved = False`).

### 🚨 CRITICAL: Barge-in During `wait_for_confirmation` — Handle Cleanly

`wait_for_confirmation()` uses `asyncio.wait_for(queue.get(), timeout=60.0)`. If a barge-in arrives WHILE the executor is waiting for confirmation:
- The `BargeInException` is NOT naturally raised inside an `asyncio.wait_for` call because `BargeInException` is raised by `PlaywrightComputer._check_cancel()` — which is only called during Playwright actions, not during the `asyncio.wait_for` wait.
- Solution: Add a check after `wait_for_confirmation()` returns — if confirmed is True, also check `cancel_flag.is_set()` and raise `BargeInException` before proceeding.

```python
confirmed = await wait_for_confirmation(session_id, timeout=60.0)
release_confirmation_queue(session_id)
if confirmed is None or not confirmed:
    # Cancelled or timed out
    emit_event(session_id, "task_paused", {...})
    await update_session_status(session_id, "paused")
    return
# Check for barge-in that arrived during confirmation wait
from services.session_service import get_cancel_flag
if get_cancel_flag(session_id).is_set():
    raise BargeInException("Barge-in during destructive confirmation")
await update_session_status(session_id, "executing")
# Proceed to attempt loop...
```

### 🚨 CRITICAL: TTS Injection API — `gemini_session.send()` Text Format

The Gemini Live API (`google-genai` SDK) `session.send()` accepts both `bytes` (audio) and `str` (text). When sending text, pass a plain string:
```python
await gemini_session.send(input=text, end_of_turn=True)
# NOT: await gemini_session.send(input={"text": text}, ...)
```
The `end_of_turn=True` signals to Gemini that this is a complete utterance to respond to. Gemini Live will synthesize TTS audio from the text and return it via audio responses. Use `end_of_turn=True` here (unlike PCM chunks where `end_of_turn=False`).

### 🚨 CRITICAL: TTS Queue Must Exist Before Executor Fires Confirmation

The TTS queue is created in `audio_relay()` when the WebSocket connects. The voice relay may NOT be connected when the executor reaches a destructive step. `try_put_tts_text()` silently drops if no queue exists — this is the correct behavior (TTS is best-effort when voice is connected, visual dialog is the mandatory gate). Never block execution on TTS delivery.

### Voice Confirmation Keyword Detection in `relay_gemini_to_browser`

The keyword matching in `relay_gemini_to_browser` should be conservative and ordered (check confirmation keywords first to avoid ambiguity):
```python
CONFIRM_WORDS = frozenset({"yes", "confirm", "proceed", "go ahead", "do it", "ok", "okay", "sure"})
DENY_WORDS = frozenset({"no", "cancel", "stop", "don't", "abort", "halt", "nope", "negative"})

text_normalized = response.text.strip().lower()
# Use startswith for partial matches ("yes please", "no that's wrong", etc.)
is_confirm = any(text_normalized.startswith(w) for w in CONFIRM_WORDS)
is_deny = any(text_normalized.startswith(w) for w in DENY_WORDS)
if is_confirm and not is_deny:
    deliver_confirmation(session_id, True)
elif is_deny:
    deliver_confirmation(session_id, False)
# If neither or ambiguous: ignore (visual dialog remains open)
```
Important: `deliver_confirmation` is `put_nowait` on a `maxsize=1` queue. Calling it multiple times while the executor is waiting will raise `QueueFull` — use a try/except:```python
try:
    deliver_confirmation(session_id, True)
except asyncio.QueueFull:
    pass  # First confirmation already queued
```
Or use `asyncio.Queue(maxsize=1)` in the service and handle the full case gracefully.

### `ConfirmActionDialog` — Accessibility Requirements (NFR19)

The dialog must be fully keyboard navigable:
- `role="dialog"` and `aria-modal="true"` on the overlay
- `aria-labelledby="confirm-dialog-title"` pointing to dialog title text  
- `aria-describedby="confirm-dialog-desc"` pointing to action description
- Cancel button gets `autoFocus` (safer default — avoids accidental form submission)
- `onKeyDown` on the dialog container:
  - `Enter` key → `handleConfirm()` (confirms, since keyboard users may expect Enter = primary action)
  - `Escape` key → `handleDecline()` (declines, consistent with modal dismiss patterns)
- Focus trap: use `tabIndex` on the dialog container, or rely on browser modal focus semantics

### `onDismiss` Callback — State Cleanup

When the dialog is dismissed (via button or keyboard), the `onDismiss` in `ThinkingPanel` sets:
```typescript
useARIAStore.setState({
  confirmationRequest: null,
  taskStatus: "paused",   // show paused (not awaiting_confirmation)
  panelStatus: "paused",  // consistent with task_paused SSE that follows
})
```
This is a LOCAL optimistic clear. The backend will also emit `task_paused` (for denial) or the executor will continue (for confirmation with no SSE gap). On confirm, the backend resumes executing and the store will naturally transition when `step_start` arrives next.

### `ThinkingPanel` Header — `awaiting_confirmation` State

Extend the `headerClass`/`headerLabel` logic in `ThinkingPanel.tsx`:
```tsx
const headerClass =
  panelStatus === "complete" ? `${headerBase} text-confidence-high`
  : panelStatus === "failed" ? `${headerBase} text-confidence-low`
  : panelStatus === "awaiting_input" ? `${headerBase} text-amber-400`
  : panelStatus === "awaiting_confirmation" ? `${headerBase} text-rose-400`   // NEW
  : headerBase;

const headerLabel =
  panelStatus === "complete" ? "Done"
  : panelStatus === "failed" ? "Failed"
  : panelStatus === "awaiting_input" ? "Awaiting Input"
  : panelStatus === "awaiting_confirmation" ? "Awaiting Confirmation"         // NEW
  : "Thinking";
```

### Backend: `confirmation_queue_service.py` Pattern

Mirror `input_queue_service.py` exactly, with `bool` instead of `str` and `maxsize=1`:

```python
import asyncio

_confirmation_queues: dict[str, asyncio.Queue[bool]] = {}


def create_confirmation_queue(session_id: str) -> asyncio.Queue[bool]:
    q: asyncio.Queue[bool] = asyncio.Queue(maxsize=1)
    _confirmation_queues[session_id] = q
    return q


def deliver_confirmation(session_id: str, confirmed: bool) -> None:
    q = _confirmation_queues.get(session_id)
    if q:
        try:
            q.put_nowait(confirmed)
        except asyncio.QueueFull:
            pass  # Already has a response — ignore duplicate


async def wait_for_confirmation(session_id: str, timeout: float = 60.0) -> bool | None:
    q = _confirmation_queues.get(session_id)
    if not q:
        return None
    try:
        return await asyncio.wait_for(q.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def release_confirmation_queue(session_id: str) -> None:
    _confirmation_queues.pop(session_id, None)


def has_confirmation_queue(session_id: str) -> bool:
    return session_id in _confirmation_queues
```

### Backend: `tts_queue_service.py` Pattern

Mirror `voice_instruction_service.py`:

```python
import asyncio

_tts_queues: dict[str, asyncio.Queue[str | None]] = {}


def create_tts_queue(session_id: str) -> asyncio.Queue[str | None]:
    q: asyncio.Queue[str | None] = asyncio.Queue()
    _tts_queues[session_id] = q
    return q


def try_put_tts_text(session_id: str, text: str) -> None:
    """Non-blocking put. Silently drops if no queue (voice relay not connected)."""
    q = _tts_queues.get(session_id)
    if q:
        try:
            q.put_nowait(text)
        except asyncio.QueueFull:
            pass


def release_tts_queue(session_id: str) -> None:
    _tts_queues.pop(session_id, None)
```

### Frontend: `ConfirmActionDialog` Full Component Sketch

```tsx
"use client";

import { useRef, useEffect, type KeyboardEvent } from "react";
import type { ConfirmationRequest } from "@/types/aria";
import { BACKEND_URL } from "@/lib/constants";

interface Props {
  request: ConfirmationRequest;
  sessionId: string;
  onDismiss: () => void;
}

export function ConfirmActionDialog({ request, sessionId, onDismiss }: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  const postConfirm = async (confirmed: boolean) => {
    await fetch(`${BACKEND_URL}/api/task/${sessionId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed }),
    }).catch(() => undefined); // non-fatal
    onDismiss();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") postConfirm(true);
    if (e.key === "Escape") postConfirm(false);
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-label="Confirm Action"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-zinc-900 border border-rose-500/50 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h2 id="confirm-dialog-title" className="text-text-primary font-semibold text-base mb-3">
          Confirm Irreversible Action
        </h2>
        <div className="bg-rose-500/10 border border-rose-500/30 rounded px-3 py-2 mb-4 flex items-center gap-2 text-rose-400 text-sm">
          ⚠️ {request.warning}
        </div>
        <p id="confirm-dialog-desc" className="text-text-secondary text-sm mb-6">
          {request.action_description}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            ref={cancelRef}
            onClick={() => postConfirm(false)}
            className="px-4 py-2 rounded bg-zinc-800 text-text-secondary hover:bg-zinc-700 text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => postConfirm(true)}
            className="px-4 py-2 rounded bg-rose-600 text-white hover:bg-rose-700 text-sm font-medium transition-colors"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Existing Tests — What Must NOT Break

All tests from Stories 4.1–4.4 remain unchanged:
- `test_interrupt_endpoint.py`: 5 tests — `/interrupt` unchanged
- `test_barge_in_endpoint.py`: 5 tests — `/barge-in` unchanged  
- `test_executor_service.py`: BargeInException behavior unchanged; `is_destructive: False` steps (the default) must pass through with zero change — the guard only fires when `is_destructive: True`
- `test_voice_instruction_service.py`: 8 tests — `voice_instruction_service.py` unchanged
- `test_replan_service.py`: 5 tests — `replan_service.py` unchanged
- Frontend: 178 tests currently passing — new guard doesn't affect any existing step processing for `is_destructive: False` steps

The `is_destructive` field already exists on `PlanStep` in `aria-frontend/src/types/aria.ts` and is produced by the Planner agent — Story 4.5 does NOT change the Planner or the step plan structure; it only adds the execution gate in the executor.

### Current Test Counts

- Backend: 188 passed (as of Story 4.4)
- Frontend: 178 passed (as of Story 4.4)

Neither count includes Story 4.5 tests yet. Expected delta: +8 backend tests, +10 frontend tests.

### Project Structure Notes

**Backend new files:**
- `aria-backend/services/confirmation_queue_service.py` — CREATE: per-session `asyncio.Queue[bool]`  
- `aria-backend/services/tts_queue_service.py` — CREATE: per-session `asyncio.Queue[str | None]` for TTS injection
- `aria-backend/tests/test_destructive_action_guard.py` — CREATE: 8 tests

**Backend modified files:**
- `aria-backend/services/executor_service.py` — ADD: `is_destructive` guard block after `step_start` emit; ADD: `release_confirmation_queue` in `finally` block
- `aria-backend/handlers/voice_handler.py` — ADD: `inject_tts_to_gemini()` coroutine + task; EXTEND: `relay_gemini_to_browser()` keyword detection for confirmation; ADD: TTS queue create/release in `audio_relay()`
- `aria-backend/routers/task_router.py` — ADD: `POST /{session_id}/confirm` endpoint + `ConfirmRequest` Pydantic model

**Frontend new files:**
- `aria-frontend/src/components/thinking-panel/ConfirmActionDialog.tsx` — CREATE: confirmation dialog component with rose styling, keyboard navigation, API call

**Frontend modified files:**
- `aria-frontend/src/types/aria.ts` — ADD `"awaiting_confirmation"` to `ThinkingPanelStatus`; ADD `ConfirmationRequest` interface
- `aria-frontend/src/lib/store/aria-store.ts` — ADD `confirmationRequest: ConfirmationRequest | null` to `ThinkingPanelSlice` and `ARIA_INITIAL_STATE`
- `aria-frontend/src/lib/hooks/useSSEConsumer.ts` — ADD `awaiting_confirmation` case; ADD `confirmationRequest: null` clear in `task_paused`, `task_complete`, `task_failed` cases
- `aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx` — ADD `ConfirmActionDialog` render; ADD `awaiting_confirmation` to header class/label logic

**Frontend new test files:**
- `aria-frontend/src/components/thinking-panel/ConfirmActionDialog.test.tsx` — CREATE: 6 tests

**Frontend modified test files:**
- `aria-frontend/src/lib/hooks/useSSEConsumer.test.ts` — ADD: 4 tests for `awaiting_confirmation` + clear-on-complete/failed/paused

### References

- Epic 4 requirements: FRs 28–32 — [Source: _bmad-output/planning-artifacts/epics.md#Safety, Control & Confirmation]
- Existing `input_queue_service.py` pattern: [aria-backend/services/input_queue_service.py](aria-backend/services/input_queue_service.py)
- Existing `voice_instruction_service.py` pattern: [aria-backend/services/voice_instruction_service.py](aria-backend/services/voice_instruction_service.py)
- Executor step loop: [aria-backend/services/executor_service.py](aria-backend/services/executor_service.py#L152) — step loop with `step_start` emit ~line 175
- voice_handler.py relay pattern: [aria-backend/handlers/voice_handler.py](aria-backend/handlers/voice_handler.py) — `relay_gemini_to_browser()`, `drain_queue_to_gemini()`
- task_router.py endpoint pattern: [aria-backend/routers/task_router.py](aria-backend/routers/task_router.py#L206) — existing `/barge-in` endpoint pattern
- `ThinkingPanel.tsx` integration point: [aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx](aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx#L121) — `InputRequestBanner` render pattern (lines 121–130)
- `StepItem.tsx` status styling pattern: [aria-frontend/src/components/thinking-panel/StepItem.tsx](aria-frontend/src/components/thinking-panel/StepItem.tsx) — for rose error border if needed in confirmation state
- `PlanStep.is_destructive` type: [aria-frontend/src/types/aria.ts](aria-frontend/src/types/aria.ts#L29) — already typed as `is_destructive: boolean`
- `BACKEND_URL` constant: [aria-frontend/src/lib/constants.ts](aria-frontend/src/lib/constants.ts) — from Story 4.4
- Barge-in cancel flag: [aria-backend/services/session_service.py](aria-backend/services/session_service.py) — `get_cancel_flag()`, `signal_barge_in()`
- Story 4.4 replan pattern (asyncio.Queue per-session): [_bmad-output/implementation-artifacts/4-4-voice-barge-in-execution-halt-and-plan-adaptation.md](_bmad-output/implementation-artifacts/4-4-voice-barge-in-execution-halt-and-plan-adaptation.md)
- NFR2 (<1s barge-in), NFR19 (keyboard accessibility): [Source: _bmad-output/planning-artifacts/epics.md#NonFunctional Requirements]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
