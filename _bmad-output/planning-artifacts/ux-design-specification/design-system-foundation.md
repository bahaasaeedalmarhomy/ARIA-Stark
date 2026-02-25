# Design System Foundation

### Design System Choice

**Selected approach:** Tailwind CSS + shadcn/ui (themeable system) with ARIA-specific custom components

shadcn/ui is already specified in the architecture. This step confirms and extends it as the full design system foundation, not just a component library.

| Layer | Technology | Purpose |
|---|---|---|
| Utility styling | Tailwind CSS v4 | All layout, spacing, typography, and color application |
| Primitive components | shadcn/ui (Radix UI base) | Button, Card, Badge, Dialog, Toast, Separator, ScrollArea |
| Custom components | Hand-built with Tailwind | VoiceWaveform, StepItem, ConfidenceBadge, ScreenshotViewer, BargeInPulse |
| Theme | CSS custom properties | Dark-first; semantic confidence color tokens |

### Rationale for Selection

- **Speed:** shadcn/ui provides all structural primitives (Button, Card, Dialog, Scroll, Toast) with zero build time — essential for the 21-day sprint
- **Dark-first:** shadcn/ui's CSS variable token system supports dark mode natively; ARIA's dense execution interface benefits from a dark theme to reduce eye strain during extended use
- **Accessibility:** Built on Radix UI — keyboard navigation and ARIA attributes are built in, not retrofitted
- **Visual freedom:** Tailwind's utility approach allows full divergence from Material/Ant aesthetics — ARIA can look distinctive while using proven primitives underneath
- **Hackathon-appropriate:** No custom design system overhead; no Storybook, no token pipeline — just CSS variables and Tailwind config

### Implementation Approach

**Phase 1 — Base tokens (Day 1):**
- Extend `tailwind.config.ts` with ARIA semantic color tokens
- Configure shadcn/ui dark theme via `globals.css` CSS variables
- Set Geist + Geist Mono as font stack

**Phase 2 — Primitive components (Days 1–3):**
- Install shadcn/ui components as needed: `button`, `card`, `badge`, `dialog`, `scroll-area`, `separator`, `toast`
- No customization beyond theme tokens at this stage

**Phase 3 — Custom components (Days 3–10):**
- `VoiceWaveform` — animated amplitude bars, state-driven color (listening / speaking / idle)
- `StepItem` — step index, action description, status icon, confidence badge, expandable screenshot
- `ConfidenceBadge` — color-coded pill (high / mid / low) using semantic tokens
- `BargeInPulse` — ripple animation triggered on VAD detection, composable with VoiceWaveform
- `ScreenshotViewer` — annotated screenshot with bounding box overlays

### Customization Strategy

**Semantic Color Tokens (dark theme):**

| Token | Value | Usage |
|---|---|---|
| `--color-step-active` | `#3B82F6` (Electric Blue) | Currently executing step highlight |
| `--color-confidence-high` | `#10B981` (Emerald) | Confidence ≥ 80% |
| `--color-confidence-mid` | `#F59E0B` (Amber) | Confidence 50–79% |
| `--color-confidence-low` | `#F43F5E` (Rose) | Confidence < 50% |
| `--color-surface` | `#18181B` (Zinc 900) | Main panel backgrounds |
| `--color-surface-raised` | `#27272A` (Zinc 800) | Step item cards, raised surfaces |
| `--color-border` | `#3F3F46` (Zinc 700) | Separators, input borders |

**Typography:**
- UI text: Geist Sans (Next.js default) — clean, modern, highly legible at small sizes
- Step descriptions / action text: Geist Mono — reinforces technical precision without being cold
- Scale: 12px step metadata → 14px primary UI → 16px task input → 20px section headers

---

