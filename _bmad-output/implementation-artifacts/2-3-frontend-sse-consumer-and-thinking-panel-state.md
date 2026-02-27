# Story 2.3: Frontend SSE Consumer and Thinking Panel State

Status: review

## Story

As a developer,
I want the frontend to consume SSE events and update Zustand state,
so that all thinking panel components react to live agent events without prop drilling.

## Acceptance Criteria

1. **Given** a `session_id` is available in Zustand `sessionSlice`, **When** the session transitions to `status: "running"` (i.e., `sessionId` becomes non-null after a successful task start), **Then** an `EventSource` is opened to the `stream_url` returned from `POST /api/task/start` and its `onmessage` handler dispatches events to the Zustand `thinkingPanelSlice`.

2. **Given** a `plan_ready` SSE event is received, **When** the `thinkingPanelSlice` processes it, **Then** `steps` is populated with the full step array, `panelStatus` transitions to `"plan_ready"`, and each step entry has `status: "pending"`.

3. **Given** the SSE connection drops, **When** the `EventSource` `onerror` handler fires, **Then** the frontend attempts reconnection automatically up to 5 times with 1-second backoff before surfacing a connection error in the UI (NFR16).

4. **Given** a `task_failed` SSE event is received, **When** the `thinkingPanelSlice` processes it, **Then** `taskStatus` (in `sessionSlice`) transitions to `"failed"` and `errorMessage` is populated for display — no silent failures.

5. **Given** a new session starts, **When** the Zustand store is reset, **Then** all three slices (session, voice, thinkingPanel) are reset to their initial states before the new session's events begin populating them.

## Tasks / Subtasks

- [x] Task 1: Update `types/aria.ts` with ThinkingPanel and step types (AC: 2, 4)
  - [x] Add `StepStatus` type: `"pending" | "active" | "complete" | "error"`
  - [x] Add `ThinkingPanelStatus` type: `"idle" | "planning" | "plan_ready" | "executing" | "complete" | "failed"`
  - [x] Add `PlanStep` interface matching the canonical backend schema (see Dev Notes)
  - [x] Add `SSEConnectionStatus` type: `"disconnected" | "connecting" | "connected" | "reconnecting" | "error"`
  - [x] Update `StartTaskData` to include `step_plan?: { task_summary: string; steps: PlanStep[] }` (backend already returns this)

- [x] Task 2: Update `lib/store/aria-store.ts` with proper ThinkingPanelSlice types (AC: 2, 4, 5)
  - [x] Replace `steps: SSEEvent[]` with `steps: PlanStep[]` in `ThinkingPanelSlice`
  - [x] Add `panelStatus: ThinkingPanelStatus` to `ThinkingPanelSlice`
  - [x] Add `taskSummary: string` (already exists — verify it's kept)
  - [x] Add `errorMessage: string | null` to `ThinkingPanelSlice` for `task_failed` events
  - [x] Add `connectionStatus: SSEConnectionStatus` to `ThinkingPanelSlice`
  - [x] Update initial state to match new field types
  - [x] Export a `resetAllSlices()` action helper that returns the full initial state object (for use in new-session reset — AC5)

- [x] Task 3: Create `lib/hooks/useSSEConsumer.ts` (AC: 1, 2, 3, 4)
  - [x] Export `useSSEConsumer()` hook — must be a React hook (use `useEffect` + `useRef`)
  - [x] Read `sessionId` and `taskStatus` from `useARIAStore`
  - [x] Open `EventSource` to `${NEXT_PUBLIC_BACKEND_URL}/api/stream/${sessionId}` when `sessionId` is non-null
  - [x] `onmessage` handler: parse `JSON.parse(event.data)` into `SSEEvent`; dispatch to store based on `event_type`
  - [x] Handle `plan_ready` event: call `useARIAStore.setState()` to set `steps`, `taskSummary`, `panelStatus: "plan_ready"`; map server steps to `PlanStep[]` with `status: "pending"` (idempotent — step plan is already hydrated from REST response; this is a safe overwrite)
  - [x] Handle `step_start` event: update the matching step's `status` to `"active"` in the steps array using `immer` draft mutation
  - [x] Handle `step_complete` event: update the matching step's `status` to `"complete"`
  - [x] Handle `step_error` event: update the matching step's `status` to `"error"`; set `errorMessage` on step if payload includes description
  - [x] Handle `task_complete` event: set `sessionSlice.taskStatus` to `"completed"`, `thinkingPanelSlice.panelStatus` to `"complete"`
  - [x] Handle `task_failed` event: set `sessionSlice.taskStatus` to `"failed"`, `thinkingPanelSlice.errorMessage` to `payload.error ?? "Task failed"` (AC4)
  - [x] Reconnect logic: on `onerror`, close the current EventSource, increment `reconnectAttemptsRef.current`, check if ≤5; if yes: schedule `setTimeout(reconnect, 1000 * attempt)` (1s × attempt number); if >5: set `connectionStatus: "error"` and surface error (AC3)
  - [x] On cleanup (effect teardown or `sessionId` becomes null): close EventSource, clear reconnect timeout, reset `reconnectAttemptsRef`
  - [x] Set `connectionStatus: "connecting"` on open attempt, `"connected"` on `EventSource` `onopen`, `"reconnecting"` during backoff

- [x] Task 4: Hydrate ThinkingPanel from REST response in `TaskInput.tsx` (AC: 1, 2, 5)
  - [x] After successful `startTask()` response, reset all slices first: call `useARIAStore.setState(resetAllSlices())` before setting new session state (AC5)
  - [x] If `response.data.step_plan` is present on the response, immediately call `useARIAStore.setState()` to set `steps`, `taskSummary`, `panelStatus: "plan_ready"` — this hydrates the plan from the REST response, avoiding the SSE race condition (see Dev Notes)
  - [x] Set `taskStatus: "running"` rather than introducing a `"planning"` intermediate state (backend runs Planner synchronously; by the time response arrives, planning is complete)
  - [x] Update `StartTaskData` type import in `task.ts` to reflect new optional `step_plan` field

- [x] Task 5: Register `useSSEConsumer` in the app layout (AC: 1)
  - [x] Call `useSSEConsumer()` in `src/app/page.tsx` (or a dedicated `Providers` client component) so the hook runs at app root level
  - [x] Verify the hook is called inside a `"use client"` component

- [x] Task 6: Write tests for `useSSEConsumer` (AC: 1, 2, 3, 4, 5)
  - [x] Create `src/lib/hooks/useSSEConsumer.test.ts` (co-located per architecture convention)
  - [x] Use `vitest` + `@testing-library/react` `renderHook` (already configured in the project)
  - [x] Mock `EventSource` globally in test setup — do NOT rely on real network connections
  - [x] Test: when `sessionId` is null → `EventSource` constructor is NOT called
  - [x] Test: when `sessionId` becomes non-null → `EventSource` opens to correct URL
  - [x] Test: `plan_ready` event → store `steps` populated, `panelStatus === "plan_ready"`, all steps `status: "pending"`
  - [x] Test: `step_start` event with `step_index: 1` → `steps[1].status === "active"`
  - [x] Test: `step_complete` event → matching step `status === "complete"`
  - [x] Test: `task_failed` event → `taskStatus === "failed"`, `errorMessage` set
  - [x] Test: `onerror` fires → EventSource is closed and reconnect is scheduled (confirm `connectionStatus === "reconnecting"`)
  - [x] Test: after 5 reconnect failures → `connectionStatus === "error"` and no further reconnects
  - [x] Test: hook cleanup → EventSource `close()` called when component unmounts

- [x] Task 7: Git commit (all files)
  - [x] `git add -A && git commit -m "feat(story-2.3): implement frontend SSE consumer and thinking panel state"`

## Dev Notes

### ⚠️ CRITICAL: SSE Race Condition — Plan from REST, Not from SSE

The backend runs the Planner **synchronously** inside `POST /api/task/start` and emits the `plan_ready` SSE event BEFORE returning the HTTP response. By the time the frontend receives the response and opens the `EventSource`, the `plan_ready` event has already been emitted and is gone.

**Solution (per Story 2.2 dev notes):** Hydrate the step plan directly from the REST response body. The `POST /api/task/start` response already includes `step_plan` in `response.data`:

```json
{
  "success": true,
  "data": {
    "session_id": "sess_abc123",
    "stream_url": "/api/stream/sess_abc123",
    "step_plan": {
      "task_summary": "Navigate to the supplier portal and fill in the monthly form",
      "steps": [ ... ]
    }
  }
}
```

**In `TaskInput.tsx`:** After a successful response, immediately populate `thinkingPanelSlice.steps` from `response.data.step_plan`. Then open the SSE stream for all subsequent executor events (`step_start`, `step_complete`, etc.).

The `plan_ready` SSE handler should still be implemented as an **idempotent** fallback — if it fires (e.g., for future async Planner flows), it safely overwrites with the same data.

[Source: 2-2-sse-stream-endpoint-for-agent-events.md → "⚠️ Important: SSE and the POST /api/task/start Race Condition"]

---

### PlanStep Interface — Exact Backend Schema

The backend canonical step schema (from Story 2.1) maps to this TypeScript interface. Rename `action` → `action_type` is a **mismatch** — the backend actually uses `action` (not `action_type` as the epics suggest). Use what Story 2.1 actually implemented:

```typescript
// src/types/aria.ts
export type StepStatus = "pending" | "active" | "complete" | "error";

export interface PlanStep {
  step_index: number;
  description: string;
  action: "navigate" | "click" | "type" | "scroll" | "screenshot" | "wait";
  target: string | null;
  value: string | null;
  confidence: number;        // 0.0–1.0 float
  is_destructive: boolean;
  requires_user_input: boolean;
  user_input_reason: string | null;
  // Frontend-only fields (not from backend):
  status: StepStatus;        // default: "pending" when hydrating from REST
  screenshot_url?: string | null;  // populated by step_complete SSE events
}
```

**Critical:** `status` is a **frontend-only** field, not present in the backend response. Always initialize it to `"pending"` when mapping from the REST response or the SSE `plan_ready` event.

[Source: 2-1-planner-agent-with-canonical-step-plan-output.md → "Canonical Step Plan Schema — EXACT"]

---

### Zustand Store Update — ThinkingPanelSlice

The existing `ThinkingPanelSlice` uses `steps: SSEEvent[]` which is wrong for rendering step cards. Replace with proper typed steps:

```typescript
// Current (WRONG):
interface ThinkingPanelSlice {
  steps: SSEEvent[];
  currentStepIndex: number;
  taskSummary: string;
}

// Updated (CORRECT):
interface ThinkingPanelSlice {
  steps: PlanStep[];
  panelStatus: ThinkingPanelStatus;   // replaces implicit status via taskStatus
  taskSummary: string;
  errorMessage: string | null;
  connectionStatus: SSEConnectionStatus;
}
```

Remove `currentStepIndex` — components can derive the active step by finding `steps.find(s => s.status === "active")` to avoid stale-index bugs.

**Immer mutation for step updates:**
```typescript
// Correct pattern using immer middleware already in the store:
useARIAStore.setState((state) => {
  const step = state.steps.find(s => s.step_index === stepIndex);
  if (step) step.status = "active";
});
```

---

### useSSEConsumer Hook — Full Pattern

```typescript
// src/lib/hooks/useSSEConsumer.ts
"use client";

import { useEffect, useRef } from "react";
import { useARIAStore } from "@/lib/store/aria-store";
import type { SSEEvent } from "@/types/aria";

const MAX_RECONNECT_ATTEMPTS = 5;
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

export function useSSEConsumer() {
  const sessionId = useARIAStore((state) => state.sessionId);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const connect = () => {
      useARIAStore.setState({ connectionStatus: "connecting" });
      const es = new EventSource(`${BACKEND_URL}/api/stream/${sessionId}`);
      eventSourceRef.current = es;

      es.onopen = () => {
        reconnectAttemptsRef.current = 0;
        useARIAStore.setState({ connectionStatus: "connected" });
      };

      es.onmessage = (event) => {
        try {
          const sseEvent: SSEEvent = JSON.parse(event.data);
          handleSSEEvent(sseEvent);
        } catch {
          // Non-JSON frame (e.g., keepalive comment) — ignore silently
        }
      };

      es.onerror = () => {
        es.close();
        const attempt = ++reconnectAttemptsRef.current;
        if (attempt > MAX_RECONNECT_ATTEMPTS) {
          useARIAStore.setState({ connectionStatus: "error" });
          return;
        }
        useARIAStore.setState({ connectionStatus: "reconnecting" });
        reconnectTimeoutRef.current = setTimeout(connect, 1000 * attempt);
      };
    };

    connect();

    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      reconnectAttemptsRef.current = 0;
    };
  }, [sessionId]);
}
```

---

### SSE Event Dispatch — Handler Functions

Keep `handleSSEEvent` as a module-level function (not inside the hook) for clean testability. It calls `useARIAStore.setState()` directly — this works because Zustand stores expose `setState` and `getState` without needing React context:

```typescript
function handleSSEEvent(event: SSEEvent) {
  switch (event.event_type) {
    case "plan_ready": {
      const payload = event.payload as { steps: PlanStep[]; task_summary: string };
      useARIAStore.setState({
        steps: payload.steps.map(s => ({ ...s, status: "pending" as StepStatus })),
        taskSummary: payload.task_summary,
        panelStatus: "plan_ready",
      });
      break;
    }
    case "step_start": {
      useARIAStore.setState((state) => {
        const step = state.steps.find(s => s.step_index === event.step_index);
        if (step) step.status = "active";
      });
      break;
    }
    case "step_complete": {
      const payload = event.payload as { screenshot_url?: string };
      useARIAStore.setState((state) => {
        const step = state.steps.find(s => s.step_index === event.step_index);
        if (step) {
          step.status = "complete";
          if (payload.screenshot_url) step.screenshot_url = payload.screenshot_url;
        }
      });
      break;
    }
    case "step_error": {
      useARIAStore.setState((state) => {
        const step = state.steps.find(s => s.step_index === event.step_index);
        if (step) step.status = "error";
      });
      break;
    }
    case "task_complete": {
      useARIAStore.setState({ taskStatus: "completed", panelStatus: "complete" });
      break;
    }
    case "task_failed": {
      const payload = event.payload as { error?: string };
      useARIAStore.setState({
        taskStatus: "failed",
        errorMessage: payload.error ?? "Task failed",
      });
      break;
    }
  }
}
```

**Note on immer + `setState` with function:** The immer middleware in the store wraps the updater in `produce()`. Pass a function that mutates the draft directly for step updates. Pass a plain object for simple field assignments.

---

### ⚠️ CRITICAL: Immer Middleware — setState Mutation Pattern

The store uses `immer` middleware. When calling `useARIAStore.setState()` with a **function**, immer converts it to an immutable update automatically. You DO NOT need to spread arrays manually:

```typescript
// ✅ CORRECT — immer handles immutability
useARIAStore.setState((draft) => {
  const step = draft.steps.find(s => s.step_index === idx);
  if (step) step.status = "active";
});

// ❌ WRONG — manual spread defeats immer's purpose and is bug-prone
useARIAStore.setState((state) => ({
  steps: state.steps.map(s => s.step_index === idx ? { ...s, status: "active" } : s)
}));
```

[Source: 2-1-planner-agent-with-canonical-step-plan-output.md → "Dev Notes / Previous story learnings / genai.Client singleton"] and [aria-store.ts → `immer(() => ({ ... }))`]

---

### Session Reset — All Slices Pattern

When a new task starts, reset ALL three slices before populating with new data. Create a helper:

```typescript
// In aria-store.ts or a separate resetState.ts util
export const ARIA_INITIAL_STATE = {
  // Session slice
  sessionId: null,
  taskStatus: "idle" as TaskStatus,
  taskDescription: "",
  uid: null,
  idToken: null,
  isSessionStarting: false,
  // Voice slice
  voiceStatus: "idle" as const,
  isVoiceConnecting: false,
  // Thinking panel slice
  steps: [],
  panelStatus: "idle" as ThinkingPanelStatus,
  taskSummary: "",
  errorMessage: null,
  connectionStatus: "disconnected" as SSEConnectionStatus,
};
```

In `TaskInput.tsx` — before setting new session data on success:
```typescript
// Reset first to clear any previous session state
useARIAStore.setState({
  ...ARIA_INITIAL_STATE,
  // Preserve auth fields — don't reset uid/idToken
  uid: useARIAStore.getState().uid,
  idToken: useARIAStore.getState().idToken,
});
```

**Important:** Do NOT reset `uid` and `idToken` — these are from Firebase Anonymous Auth and persist across sessions.

---

### SSE Canonical Envelope (Reminder)

Every event from the backend matches this exact shape (confirmed in Story 2.2):

```json
{
  "event_type": "step_start | step_complete | step_error | plan_ready | task_complete | task_failed | awaiting_confirmation | awaiting_input",
  "session_id": "sess_abc123",
  "step_index": 2,
  "timestamp": "2026-02-26T14:30:00.000Z",
  "payload": { ... }
}
```

`step_index` is `null` for events that are not step-scoped (`plan_ready`, `task_complete`, `task_failed`).  
**Do NOT use the SSE `event:` field** — events are not sent with SSE named event types; differentiate **only** by `event_type` in JSON.

[Source: 2-2-sse-stream-endpoint-for-agent-events.md → "SSE Canonical Event Envelope — EXACT"]

---

### EventSource and CORS

The `EventSource` constructor URL must be the full backend URL (including origin), not a relative path — otherwise Next.js proxies it to the frontend origin instead of the backend. Use:

```typescript
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";
const es = new EventSource(`${BACKEND_URL}/api/stream/${sessionId}`);
```

The backend's CORS config already allows the Firebase Hosting origin for SSE (same `CORS_ORIGIN` env var as REST). In local dev, `http://localhost:8080` backend with `http://localhost:3000` frontend — ensure the backend CORS allows `localhost:3000` (this should already work from Story 1.6 CORS setup).

---

### ⚠️ CRITICAL: Model Name Note (From Previous Stories)

Not directly relevant to this story, but carry forward for all future stories: the architecture documents say `gemini-3-1-pro` and `gemini-3-flash` but the **correct names** are `gemini-3.1-pro-preview` and `gemini-3-flash-preview`. Do NOT follow the docs blindly — use the story implementations as source of truth.

[Source: 2-1-planner-agent-with-canonical-step-plan-output.md → "CRITICAL: Correct Model Names and SDK Configuration"]

---

### Testing Setup — EventSource Mock

`EventSource` is not available in jsdom (vitest's default environment). Create a mock class:

```typescript
// In useSSEConsumer.test.ts or vitest.setup.ts:
class MockEventSource {
  static instance: MockEventSource;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instance = this;
  }
}

vi.stubGlobal("EventSource", MockEventSource);
```

Then in tests, `MockEventSource.instance.onmessage?.({ data: JSON.stringify(event) } as MessageEvent)` to simulate events.

---

### Project Structure Notes

Per architecture rules:
- Hook file: `src/lib/hooks/useSSEConsumer.ts` (NOT in `src/components/`)
- Test file: `src/lib/hooks/useSSEConsumer.test.ts` (co-located per frontend convention)
- No new components are created in this story — that's Story 2.4 (`ThinkingPanel`, `StepItem`, `ConfidenceBadge`)
- The `src/components/thinking-panel/` directory exists but stays empty until Story 2.4

**Files to modify:**
- `src/types/aria.ts` — add types
- `src/lib/store/aria-store.ts` — update ThinkingPanelSlice
- `src/components/session/TaskInput.tsx` — hydrate plan, reset slices on new session
- `src/app/page.tsx` or a new `src/components/providers/SSEProvider.tsx` — call `useSSEConsumer()`

**Files to create:**
- `src/lib/hooks/useSSEConsumer.ts`
- `src/lib/hooks/useSSEConsumer.test.ts`

---

### NFR Compliance

- **NFR16:** SSE auto-reconnect on connection drop. This story implements 5-retry with 1-second × attempt backoff. The 1-second multiplier ensures `1s, 2s, 3s, 4s, 5s` gaps — not exponential but progressive, sufficient for network blips.
- **NFR17:** Single session. The module-level event queues in the backend (1 queue per session) mean only one client connection is expected. The hook only opens 1 EventSource at a time.

---

### References

- Story AC source: [epics.md](_bmad-output/planning-artifacts/epics.md) → "Story 2.3: Frontend SSE Consumer and Thinking Panel State"
- SSE race condition: [2-2-sse-stream-endpoint-for-agent-events.md](_bmad-output/implementation-artifacts/2-2-sse-stream-endpoint-for-agent-events.md) → "⚠️ Important: SSE and the POST /api/task/start Race Condition"
- SSE canonical envelope: [implementation-patterns-consistency-rules.md](_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Communication Patterns / SSE event envelope"
- PlanStep schema: [2-1-planner-agent-with-canonical-step-plan-output.md](_bmad-output/implementation-artifacts/2-1-planner-agent-with-canonical-step-plan-output.md) → "Canonical Step Plan Schema — EXACT"
- Zustand store: [aria-store.ts](aria-frontend/src/lib/store/aria-store.ts) → existing slice structure with immer middleware
- Existing types: [aria.ts](aria-frontend/src/types/aria.ts) → `SSEEvent`, `StartTaskData`
- Architecture frontend structure: [implementation-patterns-consistency-rules.md](_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "TypeScript/React code naming" and "TypeScript project structure"
- Component patterns: [TaskInput.tsx](aria-frontend/src/components/session/TaskInput.tsx) → `useARIAStore.setState()` usage pattern
- NFR16 reconnect: [epics.md](_bmad-output/planning-artifacts/epics.md) → "NFR16: SSE auto-reconnect on connection drop"
- NFR17 single session: [epics.md](_bmad-output/planning-artifacts/epics.md) → "NFR17: Backend supports one active session reliably"

## Dev Agent Record

### Agent Model Used

gemini-3.1-pro-preview

### Debug Log References

### Completion Notes List

- Implemented `ThinkingPanelSlice` in Zustand with proper types (`PlanStep`, `ThinkingPanelStatus`, `SSEConnectionStatus`).
- Created `useSSEConsumer` hook for handling SSE events (`plan_ready`, `step_start`, `step_complete`, `step_error`, `task_complete`, `task_failed`) with reconnection logic.
- Updated `TaskInput` to hydrate step plan from REST response.
- Added unit tests for `useSSEConsumer` with mock `EventSource`.
- Verified tests pass.

### File List

- aria-frontend/src/types/aria.ts
- aria-frontend/src/lib/store/aria-store.ts
- aria-frontend/src/lib/hooks/useSSEConsumer.ts
- aria-frontend/src/lib/hooks/useSSEConsumer.test.ts
- aria-frontend/src/components/session/TaskInput.tsx
- aria-frontend/src/app/page.tsx
