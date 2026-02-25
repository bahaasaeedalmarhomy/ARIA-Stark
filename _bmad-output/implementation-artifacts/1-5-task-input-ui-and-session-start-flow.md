# Story 1.5: Task Input UI and Session Start Flow

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to type a task into the ARIA interface and see it submitted with visual confirmation,
so that I can initiate a session and know the system received my request.

## Acceptance Criteria

1. **Given** the ARIA home page loads, **When** the UI renders, **Then** a task input textarea is visible, keyboard-focusable, with placeholder text `"Describe a task for ARIA..."`, and a `"Start Task"` button is visible and enabled.

2. **Given** the user types a task and clicks `"Start Task"`, **When** the form is submitted, **Then** `POST /api/task/start` is called with the task description, the button shows a loading state (spinner + disabled), and the Zustand `sessionSlice` is updated with the returned `session_id`.

3. **Given** a successful API response, **When** `session_id` is received, **Then** the UI transitions out of the input state and the task description is displayed in a `"task confirmed"` banner with the text ARIA interpreted.

4. **Given** the API call fails, **When** the error response is received, **Then** the error message is displayed below the input field, the button returns to enabled state, and no session transition occurs.

5. **Given** a task is in progress (`status` is not `"idle"`), **When** a new `"Start Task"` is clicked, **Then** the existing session is preserved and a confirmation prompt asks `"Cancel current task and start a new one?"`.

## Tasks / Subtasks

- [x] Task 1: Create `TaskInput` component (AC: 1, 2, 3, 4, 5)
  - [x] Create `aria-frontend/src/components/session/TaskInput.tsx`
  - [x] Mark `"use client"` (uses Zustand hooks and event handlers)
  - [x] Render `<textarea>` with id `"task-input"`, placeholder `"Describe a task for ARIA..."`, rows=3, accessible label
  - [x] Render shadcn `<Button>` with id `"start-task-btn"` — text `"Start Task"`, disabled + loading spinner while `isSessionStarting`
  - [x] Read `idToken`, `sessionId`, `taskStatus`, `isSessionStarting` from `useARIAStore`
  - [x] On form submit: guard empty input (do not call API if `taskDescription.trim() === ""`), call `startTask(taskDescription, idToken)` from `@/lib/api/task`
  - [x] On success: set `sessionId`, `taskDescription`, `taskStatus: "running"`, `isSessionStarting: false` in Zustand
  - [x] On error: set `isSessionStarting: false`, display `response.error.message` in error div below input (id `"task-error"`)
  - [x] On `"Start Task"` click when `taskStatus !== "idle"`: show inline confirmation `"Cancel current task and start a new one?"` with Confirm/Cancel buttons (shadcn `Dialog` or inline conditional render)
- [x] Task 2: Create `TaskConfirmedBanner` component (AC: 3)
  - [x] Create `aria-frontend/src/components/session/TaskConfirmedBanner.tsx`
  - [x] Mark `"use client"`
  - [x] Read `taskDescription` from `useARIAStore`: render banner only when `sessionId !== null`
  - [x] Display: `"Task received:"` label + `taskDescription` text in `text-emerald-400` / `--color-confidence-high` color
  - [x] Include id `"task-confirmed-banner"` for test targeting

- [x] Task 3: Update `page.tsx` to render session components (AC: 1)
  - [x] Import `TaskInput` and `TaskConfirmedBanner` into `aria-frontend/src/app/page.tsx`
  - [x] Add `"use client"` directive — page needs Zustand to conditionally show components
  - [x] Render `TaskInput` within the browser panel section (bottom area)
  - [x] Render `TaskConfirmedBanner` above `TaskInput` (visible only after session starts)
  - [x] Ensure layout still renders at 1280px+ minimum — no layout breakage

- [x] Task 4: Update Zustand `sessionSlice` to add `isSessionStarting` (AC: 2)
  - [x] In `aria-frontend/src/lib/store/aria-store.ts`, add `isSessionStarting: boolean` to `SessionSlice` interface
  - [x] Initialize `isSessionStarting: false` in store body
  - [x] Keep all existing fields — do NOT remove `uid`, `idToken`, `sessionId`, `taskStatus`, `taskDescription`

- [x] Task 5: Write frontend unit tests (AC: 1–5)
  - [x] Create `aria-frontend/src/components/session/TaskInput.test.tsx`
  - [x] Test 1: renders textarea with correct placeholder and Start Task button
  - [x] Test 2: shows loading state while API is in-flight (button disabled, spinner visible)
  - [x] Test 3: on success → `sessionId` set in store, banner visible
  - [x] Test 4: on error → error message rendered below input, button re-enabled
  - [x] Test 5: when `taskStatus !== "idle"` → confirmation prompt appears instead of immediate submission
  - [x] Mock `startTask` from `@/lib/api/task` using `jest.mock` or `vi.mock`
  - [x] Mock Zustand store state via `useARIAStore.setState({})`

- [x] Task 6: Validate build (AC: all)
  - [x] Run `npm run build` in `aria-frontend/` — must complete with 0 TypeScript errors
  - [x] Manually test in browser: type a task → submit → see loading → see banner (requires running backend with valid Firebase token)

## Dev Notes

### Critical Architecture Requirements — DO NOT DEVIATE

1. **`page.tsx` must become a Client Component for this story** — because `TaskInput` reads Zustand state and uses event handlers, and shadcn conditionals at the page level require `"use client"`. Add `"use client"` at the top of `page.tsx`. Note: this does NOT break static export (`output: "export"` in `next.config.ts`) — client components export fine.

2. **`idToken` guards the Submit button subtly** — `startTask()` requires a valid `idToken` from Zustand (set by `FirebaseAuthProvider` from Story 1.4). If `idToken === null` (firebase not yet initialized), the `"Start Task"` button should be disabled. Do NOT show an error — firebase auth is silent and fast; the button will enable within milliseconds of page load in normal conditions.

3. **`isSessionStarting` is a **session slice** loading flag, not a component local state** — per architecture patterns, loading booleans live in Zustand (`isSessionStarting`), not in `useState`. This allows any component to observe and react to loading state without prop drilling.

4. **`taskStatus` transition on success must be `"running"`** — not `"pending"` or `"connected"`. The `TaskStatus` enum in `aria.ts` is `"idle" | "running" | "paused" | "awaiting_confirmation" | "awaiting_input" | "completed" | "failed"`. Use `"running"` to indicate the session is active. The Firestore `status` field transitions from `"pending"` → `"running"` when the ADK runner starts (Story 2.x), but the Zustand `taskStatus` on the frontend tracks UI state, and `"running"` is the correct front-end status after `session_id` is received.

5. **TaskInput component location** — `src/components/session/TaskInput.tsx`, NOT `src/components/` root and NOT `src/components/ui/`. The architecture spec explicitly places session-related components in `src/components/session/` (see project-structure-boundaries.md → Complete Project Directory Structure).

6. **`startTask()` already exists in `aria-frontend/src/lib/api/task.ts`** — Story 1.4 created this wrapper. Do NOT rewrite it. Just import and call it. The function signature is:
   ```typescript
   export async function startTask(
     taskDescription: string,
     idToken: string
   ): Promise<StartTaskResponse>
   ```
   `StartTaskResponse`, `StartTaskData` are already defined in `src/types/aria.ts`.

7. **shadcn components available** (installed in Story 1.2):
   - `Button` — from `@/components/ui/button`
   - `Dialog`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription` — from `@/components/ui/dialog`
   - Use `Button` variant `"destructive"` for the cancel/confirm danger action
   - DO NOT install new shadcn components in this story unless the component already exists in `aria-frontend/src/components/ui/`

8. **Tailwind v4 + ARIA CSS tokens** — use CSS variable references for ARIA semantic tokens, not raw color values:
   ```tsx
   // ✅ Correct
   className="text-emerald-400"       // or use var(--color-confidence-high)
   className="bg-[var(--color-surface-raised)]"
   // ❌ Wrong
   className="text-[#10B981]"         // raw hex
   style={{ color: "#10B981" }}       // inline style with raw color
   ```

9. **Textarea vs Input** — Use `<textarea>` (not shadcn `Input`) for the task input, as per AC1 which specifies a `textarea`. Rows=3 is a good starting height. Style it consistently with the dark theme: `bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500`.

10. **No ADK backend work in this story** — this is purely a frontend story. The backend API was fully implemented in Story 1.4. The only backend interaction is via the existing `POST /api/task/start` endpoint through the `startTask()` wrapper.

### Component Implementation Pattern

```tsx
// aria-frontend/src/components/session/TaskInput.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { startTask } from "@/lib/api/task";
import { useARIAStore } from "@/lib/store/aria-store";

export function TaskInput() {
  const [taskDescription, setTaskDescription] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const { idToken, sessionId, taskStatus, isSessionStarting } = useARIAStore();

  const handleSubmit = async () => {
    if (!taskDescription.trim()) return;

    // AC5: task already in progress — show confirmation
    if (taskStatus !== "idle") {
      setShowConfirm(true);
      return;
    }

    await submitTask();
  };

  const submitTask = async () => {
    setShowConfirm(false);
    setErrorMessage(null);
    useARIAStore.setState({ isSessionStarting: true });

    const response = await startTask(taskDescription, idToken!);

    if (response.success && response.data) {
      useARIAStore.setState({
        sessionId: response.data.session_id,
        taskDescription,
        taskStatus: "running",
        isSessionStarting: false,
      });
    } else {
      setErrorMessage(response.error?.message ?? "An unexpected error occurred");
      useARIAStore.setState({ isSessionStarting: false });
    }
  };

  return (
    <div className="flex flex-col gap-2 p-4">
      <textarea
        id="task-input"
        aria-label="Task description"
        rows={3}
        placeholder="Describe a task for ARIA..."
        className="w-full bg-zinc-800 border border-zinc-700 rounded-md p-3 text-zinc-100 
                   placeholder:text-zinc-500 resize-none focus:outline-none 
                   focus:ring-2 focus:ring-[var(--color-step-active)] text-sm"
        value={taskDescription}
        onChange={(e) => setTaskDescription(e.target.value)}
        disabled={isSessionStarting}
      />

      {errorMessage && (
        <p id="task-error" className="text-rose-400 text-xs">{errorMessage}</p>
      )}

      {showConfirm && (
        <div className="flex items-center gap-2 text-sm text-zinc-300">
          <span>Cancel current task and start a new one?</span>
          <Button size="sm" variant="destructive" onClick={submitTask}>Confirm</Button>
          <Button size="sm" variant="outline" onClick={() => setShowConfirm(false)}>Cancel</Button>
        </div>
      )}

      <Button
        id="start-task-btn"
        onClick={handleSubmit}
        disabled={!idToken || isSessionStarting}
      >
        {isSessionStarting ? (
          <span className="flex items-center gap-2">
            <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Starting...
          </span>
        ) : "Start Task"}
      </Button>
    </div>
  );
}
```

### Zustand Store Update Pattern

```typescript
// aria-store.ts — add to SessionSlice interface
interface SessionSlice {
  sessionId: string | null;
  taskStatus: TaskStatus;
  taskDescription: string;
  uid: string | null;
  idToken: string | null;
  isSessionStarting: boolean;   // ADD THIS — tracks POST /api/task/start in-flight
}

// In immer store body:
isSessionStarting: false,
```

### TaskConfirmedBanner Implementation

```tsx
// aria-frontend/src/components/session/TaskConfirmedBanner.tsx
"use client";
import { useARIAStore } from "@/lib/store/aria-store";

export function TaskConfirmedBanner() {
  const { sessionId, taskDescription } = useARIAStore();

  if (!sessionId) return null;

  return (
    <div
      id="task-confirmed-banner"
      className="mx-4 p-3 rounded-md bg-zinc-800 border border-emerald-800"
    >
      <p className="text-xs text-zinc-400">Task received:</p>
      <p className="text-sm text-emerald-400 font-mono mt-1">{taskDescription}</p>
    </div>
  );
}
```

### Updated `page.tsx` with Session Components

```tsx
// aria-frontend/src/app/page.tsx
"use client";   // ← ADD THIS

import { TaskInput } from "@/components/session/TaskInput";
import { TaskConfirmedBanner } from "@/components/session/TaskConfirmedBanner";

export default function Home() {
  return (
    <main className="flex h-screen w-full min-w-0 bg-zinc-950 overflow-hidden">
      {/* Left: Browser Panel + Task Input */}
      <section className="flex-1 flex flex-col bg-zinc-950">
        {/* Top: placeholder for BrowserPanel (Story 3.x) */}
        <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
          <p className="font-mono">Browser panel</p>
        </div>

        {/* Bottom: Task Input + Confirmed Banner */}
        <div className="border-t border-zinc-800 flex flex-col gap-2 pb-2">
          <TaskConfirmedBanner />
          <TaskInput />
        </div>
      </section>

      {/* Right: Thinking Panel — fixed 400px */}
      <aside className="w-[400px] shrink-0 border-l border-zinc-800 flex flex-col bg-surface">
        <p className="p-4 text-zinc-500 text-sm font-mono">Thinking panel</p>
      </aside>
    </main>
  );
}
```

### Testing Approach

**Frontend unit tests — `aria-frontend/src/components/session/TaskInput.test.tsx`:**

Use `@testing-library/react` + `vitest` or `jest`. Mock dependencies:
```typescript
// Mock startTask API
vi.mock("@/lib/api/task", () => ({
  startTask: vi.fn(),
}));

// Set Zustand state for idToken
beforeEach(() => {
  useARIAStore.setState({
    idToken: "mock-firebase-token",
    taskStatus: "idle",
    sessionId: null,
    isSessionStarting: false,
  });
});
```

Test cases:
1. **Renders correctly** — textarea has `placeholder="Describe a task for ARIA..."`, button has text "Start Task"
2. **Empty input guard** — clicking "Start Task" with empty textarea doesn't call `startTask()`
3. **Loading state** — while API is in-flight, button shows "Starting..." and is disabled
4. **Success flow** — after `startTask()` resolves with `{ success: true, data: { session_id: "sess_abc", stream_url: "..." } }`, store's `sessionId` is set to `"sess_abc"` and `taskStatus` is `"running"`
5. **Error flow** — after `startTask()` resolves with `{ success: false, error: { code: "UNAUTHORIZED", message: "Invalid token" } }`, error div `#task-error` contains "Invalid token", button returns to enabled
6. **In-progress guard** — when `taskStatus === "running"`, clicking "Start Task" shows confirmation prompt before calling API

**No backend tests in this story** — story 1.4 already covered the backend. This story is frontend-only.

### Project Structure Notes

Files added or modified in this story:

| File | Action | Notes |
|---|---|---|
| `aria-frontend/src/components/session/TaskInput.tsx` | **Create** | Main task input form component |
| `aria-frontend/src/components/session/TaskConfirmedBanner.tsx` | **Create** | Post-submission banner showing confirmed task |
| `aria-frontend/src/components/session/TaskInput.test.tsx` | **Create** | Unit tests for TaskInput |
| `aria-frontend/src/lib/store/aria-store.ts` | **Modify** | Add `isSessionStarting: boolean` to `SessionSlice` |
| `aria-frontend/src/app/page.tsx` | **Modify** | Add `"use client"`, import and render session components |

Files that already exist and are used but NOT modified:
- `aria-frontend/src/lib/api/task.ts` — `startTask()` already implemented in Story 1.4
- `aria-frontend/src/types/aria.ts` — `StartTaskResponse`, `StartTaskData`, `TaskStatus` already defined
- `aria-frontend/src/lib/store/aria-store.ts` — all existing fields preserved (`uid`, `idToken`, etc.)

**Architecture boundary reminder:** `src/components/session/` is the correct folder for session-related UI components (per project-structure-boundaries.md). Do NOT put `TaskInput.tsx` in `src/components/` root or `src/components/ui/`.

### Previous Story Intelligence (Story 1.4)

Key learnings from Story 1.4 implementation that affect this story:

1. **`layout.tsx` must remain a Server Component** — the Firebase auth side-effects live in a separate `FirebaseAuthProvider` client component that renders `null`. This pattern is already in place. Do NOT add `"use client"` to `layout.tsx`. Add it only to `page.tsx`.

2. **`useARIAStore` pattern for setting state outside React hooks** — when setting state after an async API call, use `useARIAStore.setState({...})` directly (not inside a hook). This works fine with Zustand + immer.

3. **`idToken` is populated via `onAuthStateChanged`** — the token is available within a few milliseconds after page load. The button disabled-when-`idToken===null` guard handles the rare edge case where the user clicks extremely fast before Firebase auto-auth completes.

4. **Build validation approach** — after implementation, run `npm run build`. The Next.js static export (`output: "export"`) is strict about using client-only APIs (like `useState`, hooks) only in client components. The `"use client"` directive on component files and `page.tsx` is critical to avoid build errors.

5. **`conftest.py` pattern** — not applicable to this story (frontend only), but noted: the Firebase Admin SDK `_apps` dict is patched at module level in `conftest.py` for backend tests.

### Git Intelligence (Last 5 Commits)

- `feat(infra)`: Story 1.3 GCP & Firebase Infrastructure Provisioning (1-3 done)
- `feat(story-1.2)`: frontend scaffold with dark theme and design tokens
- `review(story-1.1)`: adversarial code review complete
- `feat(story-1.1)`: backend scaffold with Playwright Docker image
- Note: Story 1.4 changes were implemented post-last-commit — files for 1.4 exist on disk but no commit

### Architecture Compliance Checklist

- [ ] `TaskInput` and `TaskConfirmedBanner` are in `src/components/session/` (not `src/components/` root)
- [ ] Both components have `"use client"` directive at top
- [ ] `isSessionStarting` is in Zustand `sessionSlice`, not component `useState`
- [ ] `taskStatus` set to `"running"` (not `"pending"`) on session start success
- [ ] `startTask()` imported from `@/lib/api/task` — not reimplemented
- [ ] shadcn `Button` used for submit button (not raw `<button>`)
- [ ] No raw hex color values in className — use Tailwind classes or CSS variable references
- [ ] Button is disabled when `idToken === null` (Firebase not yet initialized)
- [ ] Empty textarea guard before API call
- [ ] Error displayed in element with id `"task-error"` (testability)
- [ ] Confirmed banner has id `"task-confirmed-banner"` (testability)
- [ ] `npm run build` passes with 0 errors

### References

- Story 1.5 AC source: [epics.md](../../_bmad-output/planning-artifacts/epics.md) → Story 1.5
- Component location: [project-structure-boundaries.md](../../_bmad-output/planning-artifacts/architecture/project-structure-boundaries.md) → `src/components/session/`
- Loading boolean pattern: [implementation-patterns-consistency-rules.md](../../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → `isSessionStarting`
- TaskInputBar UX spec: [component-strategy.md](../../_bmad-output/planning-artifacts/ux-design-specification/component-strategy.md) → Section 5 "TaskInputBar"
- `startTask()` wrapper: [task.ts](../../aria-frontend/src/lib/api/task.ts) — already implemented in Story 1.4
- Zustand store: [aria-store.ts](../../aria-frontend/src/lib/store/aria-store.ts) — `SessionSlice`, `idToken`, `taskStatus`
- Types: [aria.ts](../../aria-frontend/src/types/aria.ts) — `StartTaskResponse`, `TaskStatus`

## Dev Agent Record

### Agent Model Used

GPT-5.2 (Trae IDE)

### Debug Log References

- Added Vitest + jsdom test harness and ensured TypeScript recognizes test globals
- Verified Radix Dialog prompt renders correctly under jsdom

### Completion Notes List

- ✅ Task 1: Implemented TaskInput with idToken guard, loading spinner, and confirmation prompt
- ✅ Task 2: Implemented TaskConfirmedBanner showing confirmed task after session start
- ✅ Task 3: Updated Home page to render banner + input in the left panel bottom area
- ✅ Task 4: Added and initialized `isSessionStarting` in Zustand store
- ✅ Task 5: Added unit tests covering AC1–AC5 (mocked `startTask`, store updates, dialog confirmation)
- ✅ Task 6: Frontend lint/test/build/typecheck verified green

### File List

- `aria-frontend/src/components/session/TaskInput.tsx` — **New**
- `aria-frontend/src/components/session/TaskConfirmedBanner.tsx` — **New**
- `aria-frontend/src/components/session/TaskInput.test.tsx` — **New**
- `aria-frontend/src/app/page.tsx` — **Modified**
- `aria-frontend/src/lib/store/aria-store.ts` — **Modified**
- `aria-frontend/package.json` — **Modified**
- `aria-frontend/vitest.config.ts` — **New**
- `aria-frontend/vitest.setup.ts` — **New**
- `aria-frontend/src/vitest.d.ts` — **New**

## Change Log

- 2026-02-25: Implemented Story 1.5 — task input UI, session start flow wiring to `startTask()`, confirmation banner, and frontend unit tests
