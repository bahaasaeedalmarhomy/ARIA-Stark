# Story 2.4: ThinkingPanel, StepItem, and ConfidenceBadge Components

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see the step plan displayed as a visually scannable list with confidence indicators,
so that I can follow what ARIA plans to do at a glance without reading dense text.

## Acceptance Criteria

1. **Given** the `thinkingPanelSlice` has a non-empty `steps` array, **When** `ThinkingPanel` renders, **Then** it displays one `StepItem` per step in order, inside a `ScrollArea`, with the panel background `bg-surface` (`zinc-900`).

2. **Given** a `StepItem` renders, **When** it displays a step, **Then** it shows: step index number, action description in Geist Mono, a status icon (`pending`: gray dot, `active`: blue pulse, `complete`: emerald checkmark, `error`: rose X), and a `ConfidenceBadge`.

3. **Given** a `ConfidenceBadge` renders with a confidence value, **When** `confidence >= 0.8`, **Then** it displays an emerald pill labeled "High"; when `0.5 <= confidence < 0.8` it displays an amber pill labeled "Med"; when `confidence < 0.5` it displays a rose pill labeled "Low".

4. **Given** a step has `status: "active"`, **When** the `StepItem` renders, **Then** the card background is `bg-surface-raised` (`#27272A`), a blue left border accent is visible, and the status icon pulses at 1Hz.

5. **Given** all step items are rendered, **When** the number of steps exceeds the panel height, **Then** the `ScrollArea` enables vertical scrolling and automatically scrolls to keep the active step in view.

6. **Given** the `ThinkingPanel` is placed in the right aside of `page.tsx`, **When** the page loads, **Then** the aside renders the `ThinkingPanel` instead of the current placeholder paragraph.

## Tasks / Subtasks

- [x] Task 1: Create `ConfidenceBadge` component (AC: 3)
  - [x] Create `src/components/thinking-panel/ConfidenceBadge.tsx`
  - [x] Accept `confidence: number` prop
  - [x] Render emerald pill "High" for `confidence >= 0.8`
  - [x] Render amber pill "Med" for `0.5 <= confidence < 0.8`
  - [x] Render rose pill "Low" for `confidence < 0.5`
  - [x] Use inline Tailwind with the project's CSS token classes (`bg-confidence-high`, `bg-confidence-mid`, `bg-confidence-low`) applied via `className` — NOT hardcoded hex colors
  - [x] Text must contrast at WCAG AA (4.5:1) against the badge background (use `text-zinc-950` on colored pills)

- [x] Task 2: Create `StepItem` component (AC: 2, 4)
  - [x] Create `src/components/thinking-panel/StepItem.tsx`
  - [x] Accept `step: PlanStep` prop
  - [x] Display `step.step_index + 1` (1-based display index) as a small number label
  - [x] Display `step.description` in Geist Mono (`font-mono`) — `text-text-secondary` when pending/complete, `text-text-primary` when active
  - [x] Render `ConfidenceBadge` with `step.confidence`
  - [x] Status icon per `step.status`:
    - `pending`: gray dot — `●` in `text-zinc-500`
    - `active`: animated blue pulse circle — use `animate-pulse` with `text-step-active`
    - `complete`: emerald checkmark — `✓` in `text-confidence-high`
    - `error`: rose ✗ — `✗` in `text-confidence-low`
  - [x] Card container classes:
    - Base: `rounded-md border border-border-aria px-3 py-2 flex items-start gap-2 transition-colors`
    - `pending` / `complete` / `error`: `bg-surface`
    - `active`: `bg-surface-raised border-l-2 border-l-step-active`
  - [x] Do NOT use any `is_destructive` prominence in this story — that's Story 2.5+

- [x] Task 3: Create `ThinkingPanel` component (AC: 1, 5, 6)
  - [x] Create `src/components/thinking-panel/ThinkingPanel.tsx`
  - [x] Mark `"use client"` at the top
  - [x] Read `steps` and `panelStatus` from `useARIAStore`
  - [x] Container: `h-full w-full bg-surface flex flex-col`
  - [x] Panel header: `<div className="px-4 py-3 border-b border-border-aria text-sm font-medium text-text-secondary flex items-center gap-2">`
    - Display "Thinking" label always visible
    - When `panelStatus === "planning"`: show a small `animate-pulse` dot next to label
    - When `panelStatus === "complete"`: label changes to "Done" in `text-confidence-high`
    - When `panelStatus === "failed"`: label changes to "Failed" in `text-confidence-low`
  - [x] Render `<ScrollArea className="flex-1 px-4 py-3">` for the step list
  - [x] Inside ScrollArea: map `steps` to `<StepItem key={step.step_index} step={step} />`; each wrapped in an `<li>` inside a `<ul className="flex flex-col gap-2">`
  - [x] Empty state (`steps.length === 0` AND `panelStatus === "idle"`): show centered `<p className="text-text-disabled text-sm font-mono">Waiting for task…</p>`
  - [x] Planning state (`panelStatus === "planning"` AND `steps.length === 0`): show centered `<p className="animate-pulse text-text-secondary text-sm font-mono">Planning…</p>`
  - [x] Auto-scroll to the active step: use a `useEffect` that watches `steps`, finds the active step's DOM element via `data-step-index` attribute, and calls `scrollIntoView({ behavior: "smooth", block: "nearest" })` on it
  - [x] Export `ThinkingPanel` as default and named export

- [x] Task 4: Wire `ThinkingPanel` into `page.tsx` (AC: 6)
  - [x] Open `src/app/page.tsx`
  - [x] Import `ThinkingPanel` from `@/components/thinking-panel/ThinkingPanel`
  - [x] Replace the `<p className="p-4 text-zinc-500 text-sm font-mono">Thinking panel</p>` placeholder with `<ThinkingPanel />`
  - [x] Ensure the `aside` already has `h-full` (it has `flex flex-col` — `ThinkingPanel`'s `h-full` will fill it)

- [x] Task 5: Write tests for ConfidenceBadge (AC: 3)
  - [x] Create `src/components/thinking-panel/ConfidenceBadge.test.tsx`
  - [x] Use `vitest` + `@testing-library/react` (already configured)
  - [x] Test: `confidence=0.9` → text "High", badge has class referencing `confidence-high` color token
  - [x] Test: `confidence=0.65` → text "Med", badge has class referencing `confidence-mid` color token
  - [x] Test: `confidence=0.3` → text "Low", badge has class referencing `confidence-low` color token
  - [x] Test: `confidence=0.8` → boundary edge → text "High"
  - [x] Test: `confidence=0.5` → boundary edge → text "Med"

- [x] Task 6: Write tests for StepItem (AC: 2, 4)
  - [x] Create `src/components/thinking-panel/StepItem.test.tsx`
  - [x] Test: `status: "pending"` → renders gray status dot, `bg-surface` class on card
  - [x] Test: `status: "active"` → renders `animate-pulse` element, `bg-surface-raised` on card, `border-l-step-active` on card
  - [x] Test: `status: "complete"` → renders checkmark ✓ character
  - [x] Test: `status: "error"` → renders ✗ character
  - [x] Test: step description renders in font-mono
  - [x] Test: `ConfidenceBadge` is rendered (query by confidence value display text)

- [x] Task 7: Write tests for ThinkingPanel (AC: 1, 5)
  - [x] Create `src/components/thinking-panel/ThinkingPanel.test.tsx`
  - [x] Mock `useARIAStore` with `vi.mock("@/lib/store/aria-store", ...)`
  - [x] Test: `steps=[]`, `panelStatus="idle"` → renders "Waiting for task…" empty state
  - [x] Test: `steps=[]`, `panelStatus="planning"` → renders "Planning…" text
  - [x] Test: 3 steps in store → renders 3 `StepItem` elements (query by step description)
  - [x] Test: `panelStatus="complete"` → header shows "Done"
  - [x] Test: `panelStatus="failed"` → header shows "Failed"

- [x] Task 8: Git commit
  - [x] `git add -A && git commit -m "feat(story-2.4): implement ThinkingPanel, StepItem, and ConfidenceBadge components"`

## Dev Notes

### Design Tokens — Use CSS Variable Utility Classes (NOT hardcoded hex)

The project uses Tailwind v4 `@theme inline` to expose `--color-*` CSS variables as auto-generated Tailwind utility classes. Always use these instead of Tailwind color palette classes:

| Purpose | CSS Token Variable | Tailwind Utility Class |
|---|---|---|
| Panel/page background | `--color-surface` (`#18181B`) | `bg-surface` |
| Active step card background | `--color-surface-raised` (`#27272A`) | `bg-surface-raised` |
| Active step left border | `--color-step-active` (`#3B82F6`) | `border-l-step-active` |
| High confidence badge bg | `--color-confidence-high` (`#10B981`) | `bg-confidence-high` |
| Mid confidence badge bg | `--color-confidence-mid` (`#F59E0B`) | `bg-confidence-mid` |
| Low confidence badge bg | `--color-confidence-low` (`#F43F5E`) | `bg-confidence-low` |
| Primary divider/border | `--color-border-aria` (`#3F3F46`) | `border-border-aria` |
| Primary text | `--color-text-primary` (`#FAFAFA`) | `text-text-primary` |
| Secondary text | `--color-text-secondary` (`#A1A1AA`) | `text-text-secondary` |
| Disabled text / empty state | `--color-text-disabled` (`#52525B`) | `text-text-disabled` |
| High confidence text / done | `--color-confidence-high` | `text-confidence-high` |
| Low confidence text / error | `--color-confidence-low` | `text-confidence-low` |

**Do NOT** use `bg-zinc-900`, `bg-zinc-800`, `text-emerald-400`, etc. — use the project tokens above.

[Source: aria-frontend/src/app/globals.css → `@theme inline` block, lines 176–193]

---

### Typography — Geist Fonts

Step descriptions MUST use Geist Mono:
- Tailwind class: `font-mono` (configured in `globals.css` to use `var(--font-geist-mono)`)
- Do NOT use `font-code` or inline `fontFamily` style; `font-mono` resolves to Geist Mono globally.

[Source: aria-frontend/src/app/globals.css → `code, pre, .font-mono` rule]

---

### Existing UI Components Available

The following shadcn/ui components are already installed and should be preferred over creating new ones:

- **`ScrollArea`** → `@/components/ui/scroll-area` — radix-based, already typed. Use `<ScrollArea className="flex-1 ...">` for the step list container.
- **`Badge`** → `@/components/ui/badge` — has predefined `variant` prop. However, for `ConfidenceBadge`, the semantic colors do not map cleanly to any existing `variant`. Use `Badge` as the base only if you can pass `className` to override `bg-*`; otherwise a plain `<span>` with the token classes is more direct and avoids the CVA variant override complexity. Either approach is acceptable — keep it simple.

[Source: aria-frontend/src/components/ui/scroll-area.tsx, aria-frontend/src/components/ui/badge.tsx]

---

### PlanStep Interface (from Story 2.3 — already in types/aria.ts)

No new types needed. Use the existing `PlanStep` from `@/types/aria`:

```typescript
export interface PlanStep {
  step_index: number;        // 0-based from backend; display as step_index + 1
  description: string;       // render in font-mono
  action: "navigate" | "click" | "type" | "scroll" | "screenshot" | "wait";
  target: string | null;
  value: string | null;
  confidence: number;        // 0.0–1.0; drives ConfidenceBadge
  is_destructive: boolean;   // NOT rendered in this story; reserved for Story 2.5+
  requires_user_input: boolean;
  user_input_reason: string | null;
  // Frontend-only:
  status: StepStatus;        // "pending" | "active" | "complete" | "error"
  screenshot_url?: string | null; // NOT rendered in this story; reserved for Story 3.3
}
```

Do NOT add any new fields to `PlanStep` or `aria.ts` in this story.

[Source: aria-frontend/src/types/aria.ts]

---

### Zustand Store — Read-Only in ThinkingPanel

`ThinkingPanel` reads from `useARIAStore` via selectors. It does NOT mutate state. All state mutations remain in `useSSEConsumer` (Story 2.3). Example:

```typescript
// In ThinkingPanel.tsx
const steps = useARIAStore((state) => state.steps);
const panelStatus = useARIAStore((state) => state.panelStatus);
```

Do NOT call `useARIAStore.setState()` from any component in this story.

[Source: aria-frontend/src/lib/store/aria-store.ts → `ThinkingPanelSlice`]

---

### Auto-Scroll to Active Step

Use a `useEffect` + `useRef` pattern. Add `data-step-index={step.step_index}` attribute to each `StepItem`'s root element. In `ThinkingPanel`, scroll to the active step on every `steps` change:

```typescript
// In ThinkingPanel.tsx
const viewportRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  const activeStep = steps.find(s => s.status === "active");
  if (!activeStep) return;
  const el = viewportRef.current?.querySelector(
    `[data-step-index="${activeStep.step_index}"]`
  );
  el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}, [steps]);
```

Attach `ref={viewportRef}` to the `ScrollArea`'s outer `div` wrapper (pass `ref` via `React.forwardRef` if needed, or wrap in a `div` and attach the ref there).

---

### Page Layout — `page.tsx` Current Structure

The `aside` in `page.tsx` currently contains:

```tsx
<aside className="w-[400px] shrink-0 border-l border-zinc-800 flex flex-col bg-surface">
  {/* Placeholder — ThinkingPanel goes here in Story 2.4 */}
  <p className="p-4 text-zinc-500 text-sm font-mono">Thinking panel</p>
</aside>
```

Replace only the `<p>` placeholder with `<ThinkingPanel />`. Do NOT change the `aside` dimensions or border.

[Source: aria-frontend/src/app/page.tsx]

---

### Accessibility Requirements (NFR19, NFR20)

- **NFR19**: The `ThinkingPanel` is a read-only display; no interactive controls in this story. Ensure the `ul`/`li` step list has a proper ARIA role (`role="list"` on `<ul>`, no override needed on `<li>`).
- **NFR20**: Text content must meet WCAG AA contrast (4.5:1). Specifically:
  - `ConfidenceBadge` text: use `text-zinc-950` (near-black) on all colored pill backgrounds for ≥4.5:1 contrast
  - Step description: `text-text-secondary` (`#A1A1AA`) on `bg-surface` (`#18181B`) → contrast ratio is ~5.6:1 ✓
  - Active step description: `text-text-primary` (`#FAFAFA`) on `bg-surface-raised` (`#27272A`) → contrast ratio is ~13.5:1 ✓

---

### File Structure

Per architecture rules, all thinking panel components live in `src/components/thinking-panel/`:

```
aria-frontend/src/components/thinking-panel/
  .gitkeep                          ← already exists, will be replaced by new files
  ConfidenceBadge.tsx               ← CREATE
  ConfidenceBadge.test.tsx          ← CREATE
  StepItem.tsx                      ← CREATE
  StepItem.test.tsx                 ← CREATE
  ThinkingPanel.tsx                 ← CREATE
  ThinkingPanel.test.tsx            ← CREATE
```

**Files to modify:**
- `src/app/page.tsx` — replace `<p>` placeholder with `<ThinkingPanel />`

**Files NOT to touch:**
- `src/types/aria.ts` — no new types needed
- `src/lib/store/aria-store.ts` — no state changes in this story
- `src/lib/hooks/useSSEConsumer.ts` — no changes needed
- Any backend files

---

### Testing Setup — `@testing-library/react` Render Pattern

Tests use `vitest` + `@testing-library/react` (already configured via `vitest.setup.ts` and `vitest.config.ts`). For `ThinkingPanel.test.tsx`, mock the Zustand store:

```typescript
// ThinkingPanel.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThinkingPanel } from "./ThinkingPanel";

// Mock the store
vi.mock("@/lib/store/aria-store", () => ({
  useARIAStore: vi.fn(),
}));

import { useARIAStore } from "@/lib/store/aria-store";

describe("ThinkingPanel", () => {
  beforeEach(() => {
    (useARIAStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (selector: (state: unknown) => unknown) =>
        selector({
          steps: [],
          panelStatus: "idle",
        })
    );
  });

  it("shows empty state when idle with no steps", () => {
    render(<ThinkingPanel />);
    expect(screen.getByText(/waiting for task/i)).toBeTruthy();
  });
});
```

For `ConfidenceBadge` and `StepItem` tests, no store mocking needed — they receive all data via props.

---

### Previous Story Learnings (from Story 2.3 Code Review)

1. **Stream URL** — Story 2.3 fixed EventSource to use `stream_url` from POST response rather than constructing the URL manually. This story has no SSE involvement, but note the pattern if you ever need to reference session state.

2. **Reconnect backoff** — Story 2.3 used constant 1-second delay (not multiplied by attempt). Not relevant here.

3. **Immer setState pattern** — When calling `useARIAStore.setState(() => { ... })` with a mutation function, immer handles immutability automatically. This story does NOT call setState from components — but carry this forward for any future work.

4. **Test co-location** — All test files are co-located next to source files (`*.test.tsx` next to `*.tsx`). Follow this pattern for all three new component test files.

5. **Model name** — The correct names are `gemini-3.1-pro-preview` and `gemini-3-flash-preview` (NOT `gemini-3-1-pro` / `gemini-3-flash` as the docs say). Not relevant to this frontend story, but carry forward for any backend work.

[Source: 2-3-frontend-sse-consumer-and-thinking-panel-state.md → "Code Review Findings — 2026-02-27"]

---

### NFR Compliance Summary

| NFR | Requirement | This Story's Compliance |
|---|---|---|
| NFR19 | All UI controls keyboard-navigable | ✓ Panel is read-only display; `ul`/`li` semantics provided |
| NFR20 | WCAG AA 4.5:1 contrast | ✓ Token colors validated above; badge text `text-zinc-950` ensures contrast |

---

### References

- Story AC source: [epics.md](_bmad-output/planning-artifacts/epics.md) → "Story 2.4: ThinkingPanel, StepItem, and ConfidenceBadge Components"
- Design tokens: [globals.css](aria-frontend/src/app/globals.css) → `@theme inline` block
- Existing `PlanStep` type: [aria.ts](aria-frontend/src/types/aria.ts)
- Zustand store: [aria-store.ts](aria-frontend/src/lib/store/aria-store.ts) → `ThinkingPanelSlice`
- `ScrollArea` component: [scroll-area.tsx](aria-frontend/src/components/ui/scroll-area.tsx)
- `Badge` component: [badge.tsx](aria-frontend/src/components/ui/badge.tsx)
- Page layout: [page.tsx](aria-frontend/src/app/page.tsx)
- Architecture naming conventions: [implementation-patterns-consistency-rules.md](_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Naming Patterns" and "Structure Patterns"
- Previous story dev notes and review: [2-3-frontend-sse-consumer-and-thinking-panel-state.md](_bmad-output/implementation-artifacts/2-3-frontend-sse-consumer-and-thinking-panel-state.md) → "Code Review Findings"
- UX component spec: [epics.md](_bmad-output/planning-artifacts/epics.md) → "Additional Requirements / UX Design" (`StepItem`, `ConfidenceBadge` custom components, signal tokens)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List
- Implemented ConfidenceBadge with token classes and WCAG AA contrast
- Implemented StepItem with status icons, token backgrounds, and mono text
- Implemented ThinkingPanel with header states, ScrollArea, and auto-scroll
- Wired ThinkingPanel into page aside replacing placeholder
- Added unit tests for ConfidenceBadge, StepItem, and ThinkingPanel with vitest + RTL
- Committed changes with the specified story commit message

### Code Review Fixes
- **Auto-scroll**: Replaced fragile `viewportRef` targeting with robust `scrollIntoView` on the active step element. Added test coverage.
- **Status Icons**: Replaced unicode characters with `lucide-react` icons (`Check`, `X`, `Loader2`, `Circle`) for better visual fidelity.
- **Accessibility**: Added `role="list"`, `aria-label`, `aria-live`, and `aria-current` attributes.
- **Semantic Tokens**: Replaced hardcoded `text-zinc-500` with `text-text-disabled`.

### File List
- aria-frontend/src/components/thinking-panel/ConfidenceBadge.tsx
- aria-frontend/src/components/thinking-panel/ConfidenceBadge.test.tsx
- aria-frontend/src/components/thinking-panel/StepItem.tsx
- aria-frontend/src/components/thinking-panel/StepItem.test.tsx
- aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx
- aria-frontend/src/components/thinking-panel/ThinkingPanel.test.tsx
- aria-frontend/src/app/page.tsx

