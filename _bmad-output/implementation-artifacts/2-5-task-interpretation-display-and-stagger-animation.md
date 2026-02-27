# Story 2.5: Task Interpretation Display and Stagger Animation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see ARIA confirm what it understood my task to be, and watch the step plan appear with a smooth animation,
So that I feel reassured before execution begins and can verify ARIA understood me correctly.

## Acceptance Criteria

1. **Given** a `plan_ready` SSE event is received, **When** the `ThinkingPanel` transitions from "Planning..." to displaying steps, **Then** each `StepItem` appears with a 60ms stagger delay (step 1 at 0ms, step 2 at 60ms, step 3 at 120ms, etc.) using a fade-in + slide-up CSS animation (`opacity: 0 → 1`, `translateY(8px) → translateY(0)`).

2. **Given** the `task_summary` field from the Planner step plan is available in Zustand state, **When** the thinking panel renders with a non-empty `taskSummary`, **Then** a "Task understood:" label followed by `taskSummary` text appears above the step list in `text-text-secondary` color, visible as long as the panel is not in `"idle"` state.

3. **Given** `panelStatus` is `"planning"` (Planner running but no steps yet), **When** the thinking panel renders, **Then** a "Planning..." state with a subtle pulse animation on the panel header dot is shown — no empty or broken state. *(This behavior is already implemented in Story 2.4 and must not regress.)*

4. **Given** all steps in the plan are `status: "complete"`, **When** the final step completes, **Then** the thinking panel header updates to "Done" in emerald color and the pulse animation stops. *(This behavior is already implemented in Story 2.4 and must not regress.)*

## Tasks / Subtasks

- [x] Task 1: Add `step-enter` CSS animation to `globals.css` (AC: 1)
  - [x] Add `@keyframes step-enter` inside the first `@theme inline` block in `globals.css`
  - [x] Keyframe: `from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); }`
  - [x] Add `--animate-step-enter: step-enter 0.3s ease-out both;` inside the ARIA `@theme inline` block to auto-generate the `animate-step-enter` Tailwind utility class
  - [x] Verify: `animate-step-enter` is available as a Tailwind class (no manual `@utility` needed — Tailwind v4 auto-generates from `--animate-*` variables)

- [x] Task 2: Display `taskSummary` in `ThinkingPanel.tsx` (AC: 2)
  - [x] Open `src/components/thinking-panel/ThinkingPanel.tsx`
  - [x] Read `taskSummary` from `useARIAStore`: `const taskSummary = useARIAStore((state) => state.taskSummary);`
  - [x] Add `taskSummary` section inside the `ScrollArea`, **above** the step list `<ul>`, rendered only when `taskSummary` is non-empty (`taskSummary && (...)`)
  - [x] Markup: `<div className="mb-3 pb-3 border-b border-border-aria"><p className="text-xs text-text-secondary"><span className="font-medium text-text-primary">Task understood:</span>{" "}{taskSummary}</p></div>`
  - [x] Do NOT change the header states, auto-scroll logic, or empty/planning states — they already work correctly

- [x] Task 3: Apply stagger animation to step items in `ThinkingPanel.tsx` (AC: 1)
  - [x] In the `steps.map()` inside `ThinkingPanel.tsx`, add `animate-step-enter` class and inline `animationDelay` to the `<li>` wrapper for each step
  - [x] Use `step.step_index` for the delay: `style={{ animationDelay: \`${step.step_index * 60}ms\` }}`
  - [x] Apply class: `<li key={step.step_index} className="animate-step-enter" style={{ animationDelay: \`${step.step_index * 60}ms\` }}>`
  - [x] The `animate-step-enter` class will trigger the CSS keyframe animation on mount; the `animation-fill-mode: both` (from `both` in the shorthand) ensures steps start invisible until their delay elapses
  - [x] Do NOT touch `StepItem.tsx` — all animation is applied on the `<li>` wrapper in `ThinkingPanel`

- [x] Task 4: Update tests for `ThinkingPanel` (AC: 1, 2)
  - [x] Open `src/components/thinking-panel/ThinkingPanel.test.tsx`
  - [x] Add test: `taskSummary="test summary"` with `panelStatus="plan_ready"` and non-empty steps → text "Task understood:" and "test summary" are present in the document
  - [x] Add test: `taskSummary=""` (empty) → "Task understood:" text is NOT present
  - [x] Add test: stagger animation — render 3 steps, query each `<li>` element, verify each has `className` containing `animate-step-enter` and `style.animationDelay` equal to `0ms`, `60ms`, `120ms` respectively
  - [x] Ensure existing tests still pass (planning pulse, Done state, empty state, step rendering)

- [x] Task 5: Git commit
  - [x] `git add -A && git commit -m "feat(story-2.5): task interpretation display and stagger animation"`

## Dev Notes

### What Is Already Done — Do NOT Re-implement

The following behavior is **fully implemented in Story 2.4** and must NOT be changed:

- `panelStatus === "planning"` → shows "Planning…" with `animate-pulse ●` next to "Thinking" label in the header (AC3 — already working)
- `panelStatus === "complete"` → shows "Done" in `text-confidence-high` (AC4 — already working)
- `panelStatus === "failed"` → shows "Failed" in `text-confidence-low` (already working)
- Auto-scroll to active step via `useEffect` + `viewportRef` (already working)
- `ScrollArea` wrapping the step list (already working)
- `StepItem` rendering per step (already working)

**The `taskSummary` field already exists in Zustand store** (`ThinkingPanelSlice`) and is **already populated by `useSSEConsumer.ts`** when a `plan_ready` SSE event is received. Story 2.5 only adds the UI to *display* it — no store or hook changes needed.

### Design Tokens — CSS Variable Utility Classes (MANDATORY)

Always use token classes — NOT hardcoded hex or Tailwind palette classes:

| Purpose | CSS Token Variable | Tailwind Utility Class |
|---|---|---|
| Panel background | `--color-surface` (`#18181B`) | `bg-surface` |
| Primary divider/border | `--color-border-aria` (`#3F3F46`) | `border-border-aria` |
| Primary text | `--color-text-primary` (`#FAFAFA`) | `text-text-primary` |
| Secondary text | `--color-text-secondary` (`#A1A1AA`) | `text-text-secondary` |
| Disabled/empty state text | `--color-text-disabled` (`#52525B`) | `text-text-disabled` |

[Source: aria-frontend/src/app/globals.css → `@theme inline` ARIA block, lines ~176–195]

### Adding Animation to Tailwind v4 (CRITICAL — Tailwind v4 specific)

In Tailwind v4, the framework auto-generates utility classes from `@theme inline` CSS variables. To add a custom animation utility `animate-step-enter`:

**Step 1**: Define the keyframe inside the first `@theme inline` block (alongside existing shadcn keyframes):
```css
@theme inline {
  @keyframes accordion-down { ... }  /* existing */
  @keyframes accordion-up { ... }    /* existing */
  @keyframes step-enter {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0);   }
  }
}
```

**Step 2**: Define the `--animate-*` variable inside the ARIA `@theme inline` block (alongside color tokens):
```css
@theme inline {
  /* ... existing color tokens ... */
  --animate-step-enter: step-enter 0.3s ease-out both;
}
```

Tailwind v4 generates `animate-step-enter` from `--animate-step-enter` automatically. **Do NOT use `@utility animate-step-enter { animation: ... }`** — that approach requires explicit `@utility` and bypasses the token system.

[Source: Tailwind v4 docs — CSS-first configuration; globals.css → existing `@keyframes` pattern]

### Zustand Store — `taskSummary` Already Available

```typescript
// Already in ThinkingPanelSlice (aria-store.ts)
taskSummary: string;  // populated by useSSEConsumer on plan_ready event
```

**Read in ThinkingPanel:**
```typescript
const taskSummary = useARIAStore((state) => state.taskSummary);
```

**Already populated in `useSSEConsumer.ts` (lines ~72–80):**
```typescript
case "plan_ready": {
  const payload = event.payload as { steps: PlanStep[]; task_summary: string; };
  useARIAStore.setState({
    steps: payload.steps.map((s) => ({ ...s, status: "pending" as StepStatus })),
    taskSummary: payload.task_summary,   // ← already stored here
    panelStatus: "plan_ready",
  });
  break;
}
```

**Do NOT modify `aria-store.ts` or `useSSEConsumer.ts`** — all required state management is already complete.

[Source: aria-frontend/src/lib/store/aria-store.ts → ThinkingPanelSlice; aria-frontend/src/lib/hooks/useSSEConsumer.ts → handleSSEEvent plan_ready case]

### Stagger Animation — Exact Implementation Pattern

In `ThinkingPanel.tsx`, the current step list is:
```tsx
<ul className="flex flex-col gap-2" role="list" aria-label="Step plan">
  {steps.map((step) => (
    <li key={step.step_index}>
      <StepItem step={step} />
    </li>
  ))}
</ul>
```

Change only the `<li>` element to add the animation class and delay:
```tsx
<ul className="flex flex-col gap-2" role="list" aria-label="Step plan">
  {steps.map((step) => (
    <li
      key={step.step_index}
      className="animate-step-enter"
      style={{ animationDelay: `${step.step_index * 60}ms` }}
    >
      <StepItem step={step} />
    </li>
  ))}
</ul>
```

Key notes:
- `step.step_index` is 0-based → step 1 gets `0ms`, step 2 gets `60ms`, step 3 gets `120ms` ✓ (matches AC1)
- `animation-fill-mode: both` (from the `both` keyword in `--animate-step-enter`) ensures items are invisible (`opacity: 0; transform: translateY(8px)`) before their delay elapses, then remain fully visible after the animation completes
- Animation replays whenever a new set of steps is mounted (e.g., when a new task's `plan_ready` event arrives and the store resets + steps re-mount)
- Do NOT apply `animate-step-enter` to the `StepItem` root div — it is applied on the `<li>` wrapper only, keeping `StepItem` stateless about animations

### Task Summary Display — Exact Implementation Pattern

Add the following inside `ScrollArea`, immediately before the `{steps.length === 0 ? ... : ...}` conditional in `ThinkingPanel.tsx`:
```tsx
{taskSummary && (
  <div className="mb-3 pb-3 border-b border-border-aria">
    <p className="text-xs text-text-secondary leading-relaxed">
      <span className="font-medium text-text-primary">Task understood:</span>{" "}
      {taskSummary}
    </p>
  </div>
)}
```

Notes:
- Render when `taskSummary` is non-empty (truthy check is sufficient — empty string is falsy)
- The border-bottom separator visually separates the summary from the step list
- `text-xs` keeps the summary compact above the steps
- Do NOT add `panelStatus !== "idle"` guard — if `taskSummary` is populated, it's authoritative; if the store was reset (idle), `taskSummary` will be `""` (falsy) so it won't render

### Current ThinkingPanel.tsx Structure (Reference Only)

```tsx
// Current return block (Story 2.4 final state):
return (
  <div className="h-full w-full bg-surface flex flex-col">
    <div className={headerClass} role="status" aria-live="polite">
      <span>{headerLabel}</span>
      {panelStatus === "planning" && (
        <span className="animate-pulse text-text-secondary">●</span>
      )}
    </div>

    <div ref={viewportRef} className="flex-1">
      <ScrollArea className="flex-1 px-4 py-3">
        {steps.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            {panelStatus === "planning" ? (
              <p className="animate-pulse text-text-secondary text-sm font-mono">Planning…</p>
            ) : panelStatus === "idle" ? (
              <p className="text-text-disabled text-sm font-mono">Waiting for task…</p>
            ) : null}
          </div>
        ) : (
          <ul className="flex flex-col gap-2" role="list" aria-label="Step plan">
            {steps.map((step) => (
              <li key={step.step_index}>
                <StepItem step={step} />
              </li>
            ))}
          </ul>
        )}
      </ScrollArea>
    </div>
  </div>
);
```

The task summary block goes **inside** `<ScrollArea>`, **before** the `{steps.length === 0 ? ... : ...}` conditional. The stagger is added to the `<li>` elements inside the `steps.map()`.

[Source: aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx]

### File Structure

**Files to modify:**
```
aria-frontend/src/app/globals.css
  → Add @keyframes step-enter inside first @theme inline block
  → Add --animate-step-enter variable inside ARIA @theme inline block

aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx
  → Add taskSummary read from useARIAStore
  → Add taskSummary display block inside ScrollArea
  → Add animate-step-enter class + animationDelay style to <li> step wrappers

aria-frontend/src/components/thinking-panel/ThinkingPanel.test.tsx
  → Add tests for taskSummary display and stagger animation
```

**Files NOT to touch:**
- `src/components/thinking-panel/StepItem.tsx` — no changes needed
- `src/components/thinking-panel/ConfidenceBadge.tsx` — no changes needed
- `src/types/aria.ts` — no new types needed
- `src/lib/store/aria-store.ts` — `taskSummary` already in store
- `src/lib/hooks/useSSEConsumer.ts` — already populates `taskSummary`
- `src/app/page.tsx` — no layout changes needed
- Any backend files

### Testing — Stagger Animation Test Pattern

Since JSDOM (used by vitest) does not compute CSS animations, test the stagger by checking that the `<li>` elements have the correct `className` and `style` attribute:

```typescript
// ThinkingPanel.test.tsx
it("applies animate-step-enter class and correct delay to each step li", () => {
  const steps: PlanStep[] = [
    { step_index: 0, description: "Step A", status: "pending", confidence: 0.9, action: "navigate", target: null, value: null, is_destructive: false, requires_user_input: false, user_input_reason: null },
    { step_index: 1, description: "Step B", status: "pending", confidence: 0.7, action: "click", target: null, value: null, is_destructive: false, requires_user_input: false, user_input_reason: null },
    { step_index: 2, description: "Step C", status: "pending", confidence: 0.3, action: "type", target: null, value: null, is_destructive: false, requires_user_input: false, user_input_reason: null },
  ];
  (useARIAStore as ReturnType<typeof vi.fn>).mockImplementation(
    (selector: (state: unknown) => unknown) =>
      selector({ steps, panelStatus: "plan_ready", taskSummary: "" })
  );
  const { container } = render(<ThinkingPanel />);
  const listItems = container.querySelectorAll("li");
  expect(listItems[0].className).toContain("animate-step-enter");
  expect((listItems[0] as HTMLElement).style.animationDelay).toBe("0ms");
  expect((listItems[1] as HTMLElement).style.animationDelay).toBe("60ms");
  expect((listItems[2] as HTMLElement).style.animationDelay).toBe("120ms");
});

it("shows task summary when taskSummary is non-empty", () => {
  (useARIAStore as ReturnType<typeof vi.fn>).mockImplementation(
    (selector: (state: unknown) => unknown) =>
      selector({ steps: [], panelStatus: "plan_ready", taskSummary: "Book a flight to Paris" })
  );
  render(<ThinkingPanel />);
  expect(screen.getByText(/Task understood:/i)).toBeTruthy();
  expect(screen.getByText(/Book a flight to Paris/)).toBeTruthy();
});

it("does not show task summary when taskSummary is empty", () => {
  (useARIAStore as ReturnType<typeof vi.fn>).mockImplementation(
    (selector: (state: unknown) => unknown) =>
      selector({ steps: [], panelStatus: "idle", taskSummary: "" })
  );
  render(<ThinkingPanel />);
  expect(screen.queryByText(/Task understood:/i)).toBeNull();
});
```

[Source: Test pattern from 2-4-thinkingpanel-stepitem-and-confidencebadge-components.md → "Testing Setup — @testing-library/react Render Pattern"]

### Previous Story Learnings (from Story 2.4 Code Review)

1. **Icon library** — Story 2.4 switched from unicode characters to `lucide-react` icons (`Check`, `X`, `Loader2`, `Circle`). This story does not add new icons; continue using lucide-react for any future icon needs.

2. **Semantic tokens enforced** — Story 2.4 code review replaced `text-zinc-500` with `text-text-disabled`. This story must follow the same rule — use ONLY token utility classes, never Tailwind palette classes (`text-zinc-*`, `bg-zinc-*`, `text-emerald-*`, etc.).

3. **Test co-location** — All tests are co-located as `*.test.tsx` next to `*.tsx`. `ThinkingPanel.test.tsx` already exists and must be extended (not replaced).

4. **Auto-scroll uses `viewportRef`** — `viewportRef` is attached to the `<div ref={viewportRef}>` wrapping the `ScrollArea`. This must not be changed. The stagger animation `<li>` approach does not conflict with the `querySelector('[data-step-index=...]')` auto-scroll logic.

5. **Model names** — Backend models are `gemini-3.1-pro-preview` and `gemini-3-flash-preview` (NOT `gemini-3-1-pro` / `gemini-3-flash`). Not relevant to this frontend story, but carry forward for any backend work.

6. **Windows ProactorEventLoop compatibility** — The most recent commit (`1ec3dda`) added Windows compatibility for Playwright. Not relevant to this frontend story.

[Source: aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx; _bmad-output/implementation-artifacts/2-4-thinkingpanel-stepitem-and-confidencebadge-components.md → Dev Notes and Code Review Fixes]

### Recent Git History (Context)

```
1ec3dda (HEAD) feat(windows): add Windows compatibility for Playwright with ProactorEventLoop
f63f883 chore(sprint): update story 2.4 status to done
6e2e691 chore(story-2.4): fix code review issues - auto-scroll, icons, a11y, tokens
d88a322 feat(story-2.4): implement ThinkingPanel, StepItem, and ConfidenceBadge components
5384981 feat(sse): store and use stream URL for SSE connection
3e3f106 feat(story-2.3): implement frontend SSE consumer and thinking panel state
```

### NFR Compliance Summary

| NFR | Requirement | This Story's Compliance |
|---|---|---|
| NFR19 | All UI controls keyboard-navigable | ✓ `taskSummary` is a read-only `<p>` element; no interactive controls added |
| NFR20 | WCAG AA 4.5:1 contrast | ✓ `text-text-secondary` (`#A1A1AA`) on `bg-surface` (`#18181B`) → ~5.6:1 ✓; `text-text-primary` (`#FAFAFA`) on `bg-surface` → ~13.5:1 ✓ |

### References

- Story AC source: [epics.md](_bmad-output/planning-artifacts/epics.md) → "Story 2.5: Task Interpretation Display and Stagger Animation"
- Design tokens: [globals.css](aria-frontend/src/app/globals.css) → `@theme inline` ARIA block
- Existing Zustand store with `taskSummary`: [aria-store.ts](aria-frontend/src/lib/store/aria-store.ts) → `ThinkingPanelSlice`
- SSE consumer populating `taskSummary`: [useSSEConsumer.ts](aria-frontend/src/lib/hooks/useSSEConsumer.ts) → `plan_ready` case
- ThinkingPanel current implementation: [ThinkingPanel.tsx](aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx)
- Previous story (2.4) dev notes and review: [2-4-thinkingpanel-stepitem-and-confidencebadge-components.md](_bmad-output/implementation-artifacts/2-4-thinkingpanel-stepitem-and-confidencebadge-components.md) → "Code Review Fixes"
- Tailwind v4 animation system: globals.css `@theme inline` → existing `@keyframes` for accordion patterns

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List
- Implemented `step-enter` animation in `globals.css` using Tailwind v4 `@theme inline` and `--animate-*` variables.
- Added `taskSummary` display in `ThinkingPanel.tsx` with appropriate styling and conditional rendering.
- Applied stagger animation to `<li>` elements in `ThinkingPanel.tsx` using inline styles for dynamic delay.
- Updated `ThinkingPanel.test.tsx` with new tests for `taskSummary` and stagger animation logic.
- Verified all tests pass.
- Review fixes (AI): Prevented scroll thrash by only scrolling when active step index changes.
- Review fixes (AI): Added reduced-motion support disabling `animate-step-enter` when user prefers reduced motion.
- Review fixes (AI): Standardized ThinkingPanel to named export and updated import in `app/page.tsx`.
- Review fixes (AI): Removed redundant `role="listitem"` from `StepItem` root to rely on native `<li>` semantics.
- Review fixes (AI): Associated task summary with step list via `aria-describedby="task-summary"` on `<ul>`.

### File List
- aria-frontend/src/app/globals.css
- aria-frontend/src/components/thinking-panel/ThinkingPanel.tsx
- aria-frontend/src/components/thinking-panel/ThinkingPanel.test.tsx
- aria-frontend/src/components/thinking-panel/StepItem.tsx  <!-- AI review fix: semantics -->
- aria-frontend/src/app/page.tsx  <!-- AI review fix: named export import -->
