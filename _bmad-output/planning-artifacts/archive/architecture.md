---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief-gemini-hackathon-2026-02-23.md
  - _bmad-output/planning-artifacts/research/domain-agentic-ai-computer-use-ux-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/market-ui-navigator-agents-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/technical-aria-stack-research-2026-02-23.md
workflowType: 'architecture'
project_name: 'gemini-hackathon'
user_name: 'Bahaa'
date: '2026-02-24'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

ARIA has 13 distinct functional requirement areas derived from 5 user journeys:

1. **Voice task input** — Real-time speech-to-intent via Gemini Live API with native VAD
2. **Text task input** — Alternative input path sharing the same Planner pipeline
3. **Task decomposition** — Planner outputs structured JSON step plan before Executor acts
4. **Step plan display** — Thinking panel shows ordered steps before and during execution
5. **Browser execution** — Executor navigates, clicks, types via Playwright + Chromium (headless)
6. **Live thinking panel** — ADK OpenTelemetry events streamed via SSE to frontend in real time
7. **Voice narration** — Gemini Live TTS narrates Executor actions throughout task
8. **Voice barge-in** — Native VAD interruption: user says "wait/stop", ARIA pauses and re-listens
9. **Mid-task user input** — Planner halts Executor when required data is missing, requests from user
10. **Destructive action guard** — Mandatory voice + visual confirmation before submit/delete/purchase
11. **Confidence scoring** — Planner annotates each step with confidence level; low confidence triggers verify loop
12. **Audit log** — Per-step records (action, screenshot URL, confidence, result) stored in Firestore + GCS
13. **Structured output display** — Chat panel surfaces comparison results and task summaries

**Non-Functional Requirements:**

| NFR | Target | Architectural Driver |
|---|---|---|
| Barge-in response | < 1s from utterance | True streaming audio relay, no buffering |
| Thinking panel sync | < 500ms from ADK event | SSE hot path, no DB round-trip |
| Voice-to-first-action | < 3s end-to-end | Planner fast-path, parallel screenshot |
| Gemini Live round-trip | 1–1.8s | Streaming mode config, WebSocket transport |
| Destructive detection | 100% — zero misses | Deterministic Planner classification |
| Cloud Run cold start | Zero during demo | min-instances 1 in deploy config |
| Chromium stability | Zero crashes in demo run | Container memory ≥ 4GB, --no-sandbox config |

**Scale & Complexity:**

- Primary domain: Full-stack web application + AI backend + real-time multimodal streaming
- Complexity level: **High** — novel AI stack, dual-agent orchestration, real-time voice, GCP multi-service
- Estimated architectural components: 8 major (Frontend, Voice Pipeline, Planner Agent, Executor Agent, ADK Runtime, Audit Log, GCP Services, Docker/Deploy)

### Technical Constraints & Dependencies

- **Deadline:** March 17, 2026 (hackathon submission)
- **Runtime:** Must deploy on Google Cloud Run — Vertex AI Agent Engine excluded (no headless browser support)
- **Models:** Planner = `gemini-3-1-pro`; Executor + Voice = `gemini-3-flash` (fully multimodal — built-in computer use, native audio in/out; single model handles both browser execution and voice interaction)
- **Model update note:** `gemini-2.5-computer-use-preview-10-2025` is superseded — per Google AI docs (Feb 2026): *"Gemini 3 Pro and Flash models support integrated computer use, without the need for a separate model."* `gemini-3-flash` is preferred for the Executor role: faster action-verify loop, lower latency per step, and cost-efficient at high screenshot volume.
- **Framework:** Google ADK v1.25+ — native ComputerUseToolset, built-in OpenTelemetry, one-command Cloud Run deploy
- **Container:** Official `mcr.microsoft.com/playwright` Docker image; 2–4 GB RAM; `--no-sandbox`, `--disable-dev-shm-usage`
- **Context window:** Long tasks require step summarization — only current step + last 3 steps in active Gemini context

### Cross-Cutting Concerns Identified

1. **Real-time streaming** — Three concurrent streams per session: audio (WebSocket bidirectional), thinking panel (SSE unidirectional), audit log (Firestore real-time subscription). Each must be independently resilient.
2. **HITL safety gate** — Destructive action classification and confirmation is a cross-cutting concern touching Planner output schema, Executor execution logic, voice pipeline, and frontend UI simultaneously.
3. **Session state** — Task context, step history, and screenshot references must be consistent across Planner, Executor, voice handler, and audit log writer within a single session.
4. **Error & recovery** — CAPTCHA encounters, JS-heavy page loads, coordinate drift, and context overflow each require defined recovery paths without breaking the user-visible flow.
5. **Prompt injection surface** — Page content enters the Gemini context window; sandboxing boundary between page-sourced content and system prompt must be enforced at the Executor level.
6. **Observability** — ADK's native OpenTelemetry traces are the primary feed for the thinking panel AND for debugging; trace format must be consistent and filterable by session.

---

## Starter Template Evaluation

### Primary Technology Domain

Full-stack split architecture: TypeScript/Next.js frontend + Python/ADK backend deployed as separate services. Two project starters required.

### Starter Options Considered

**Frontend:** `create-next-app` (official Next.js CLI) — the only supported way to bootstrap a Next.js 15 project with App Router, TypeScript, and Tailwind in one command.

**Backend:** Google ADK CLI scaffold (`adk new`) — official ADK project generator that produces a ready-to-run multi-agent Python project with correct `pyproject.toml`, agent directory structure, and `.env` convention.

### Selected Starters

#### Frontend: create-next-app

**Initialization Command:**

```bash
npx create-next-app@latest aria-frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-turbopack
```

**Architectural Decisions Provided by Starter:**

- **Language & Runtime:** TypeScript strict mode, Node.js 20+
- **Framework:** Next.js 15 with App Router (`app/` directory) — server components by default, client components opt-in
- **Styling Solution:** Tailwind CSS v3 — utility-first; shadcn/ui components added post-init via `npx shadcn@latest init`
- **Build Tooling:** Webpack (Turbopack disabled — better ecosystem compatibility for hackathon)
- **Linting/Formatting:** ESLint with Next.js config; Prettier added separately
- **Project Structure:** `src/app/` for routes, `src/components/` for UI, `src/lib/` for utilities
- **Real-time Transport:** Native `EventSource` API (SSE) for thinking panel; native `WebSocket` API for voice audio relay

#### Backend: Google ADK Python Scaffold

**Initialization Command:**

```bash
pip install google-adk
adk new aria-backend
cd aria-backend
```

**Architectural Decisions Provided by Starter:**

- **Language & Runtime:** Python 3.11+ (required for ADK v1.25 async patterns)
- **Framework:** Google ADK v1.25+ — declarative agent config, built-in OpenTelemetry, `adk run` dev server with hot reload
- **Package Management:** `pyproject.toml` + `pip`; `requirements.txt` for Docker layer caching
- **Agent Structure:** `agents/` directory with one Python file per agent; `__init__.py` exports root agent
- **Build Tooling:** Docker via `mcr.microsoft.com/playwright:v1.50.0-jammy` base image
- **Executor model:** `gemini-3-flash` with built-in computer use (via ADK `ComputerUseToolset`) — replaces `gemini-2.5-computer-use-preview-10-2025`
- **Testing:** pytest + ADK's built-in `adk eval` for agent evaluation
- **Deployment:** `adk deploy cloud-run --project $GCP_PROJECT --region us-central1 --min-instances 1`

**Note:** Project initialization using both commands above should be the first two implementation stories — frontend first, then backend scaffold with Playwright image configuration.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Executor model confirmed as `gemini-3-flash` with built-in computer use
- Session ID owned by backend (ADK runner)
- Firestore scoped per anonymous Firebase Auth uid
- All three real-time transports confirmed (WebSocket / SSE / Firestore subscription)

**Important Decisions (Shape Architecture):**
- Zustand for frontend state management
- GCS screenshot path convention: `sessions/{session_id}/steps/{step_index}.png`
- REST + WebSocket + SSE API surface (no GraphQL)
- GitHub Actions CI/CD

**Deferred Decisions (Post-hackathon):**
- Vertex AI Agent Engine migration (blocked by Playwright requirement)
- Vector DB for semantic memory (post-MVP)
- WebRTC for voice (would reduce latency ~200ms but adds LiveKit dependency)

---

### Data Architecture

**Session ID ownership:** Backend (ADK runner) generates and owns `session_id` via `runner.run_async()`. Frontend receives it in the `POST /api/task/start` response and uses it for all subsequent WebSocket, SSE, and Firestore connections. Rationale: prevents race conditions; ADK session is the authoritative identity.

**Firestore document structure:**

```json
{
  "session_id": "sess_abc123",
  "uid": "firebase_anon_uid",
  "task_description": "Fill out the monthly compliance form",
  "status": "running | paused | awaiting_confirmation | completed | failed",
  "created_at": "ISO8601",
  "steps": [
    {
      "step_index": 0,
      "description": "Navigate to supplier portal login page",
      "action": "navigate",
      "confidence": 0.95,
      "is_destructive": false,
      "result": "success",
      "screenshot_url": "gs://aria-screenshots/sessions/sess_abc123/steps/0.png",
      "timestamp": "ISO8601"
    }
  ]
}
```

**GCS screenshot path convention:** `sessions/{session_id}/steps/{step_index}.png`
Rationale: enables full session replay by scanning `sessions/{session_id}/steps/` prefix without any index lookup. Step index is zero-padded to 4 digits (`0000`, `0001`) for lexicographic ordering.

---

### Authentication & Security

**Decision: Firebase Anonymous Auth**

All sessions are scoped to a Firebase Anonymous Auth uid. Firestore security rules write-protect each session document to its uid. CORS on the Cloud Run backend is locked to the Firebase Hosting origin.

```typescript
// Frontend: get anonymous uid before starting task
const { user } = await signInAnonymously(auth);
const idToken = await user.getIdToken();
// Pass idToken in Authorization header to POST /api/task/start
```

Rationale: zero user friction (no sign-up), Firestore session isolation is automatic, and it demonstrates production-ready auth thinking to judges.

**Prompt injection mitigation:** All page content passed to Gemini context is wrapped in a `<page_content>` XML tag. Executor system prompt explicitly instructs the model to treat anything inside `<page_content>` as untrusted data, never as instructions.

---

### API & Communication Patterns

**REST endpoints (Cloud Run backend):**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/task/start` | Start a new task; returns `session_id` + SSE stream URL |
| `POST` | `/api/task/{session_id}/interrupt` | Pause task (text/UI fallback for barge-in) |
| `POST` | `/api/task/{session_id}/confirm` | Confirm destructive action |
| `POST` | `/api/task/{session_id}/input` | Provide mid-task requested data |
| `GET` | `/api/task/{session_id}/status` | Poll task status (fallback if SSE disconnects) |

**WebSocket:** `/ws/audio/{session_id}` — bidirectional, browser sends raw PCM audio chunks, backend relays to Gemini Live API and streams TTS audio back.

**SSE:** `/api/stream/{session_id}` — backend pushes ADK OpenTelemetry events as structured JSON events. Frontend `EventSource` consumes and updates thinking panel.

**SSE event envelope:**

```json
{
  "event_type": "step_start | step_complete | step_error | plan_ready | awaiting_confirmation | awaiting_input | task_complete",
  "session_id": "sess_abc123",
  "step_index": 2,
  "payload": { ... }
}
```

**Audit log reads:** Frontend Firestore SDK subscribes directly via `onSnapshot` — no backend round-trip for audit log display.

---

### Frontend Architecture

**State management: Zustand**

One store, three slices:

```typescript
// store/aria-store.ts
interface ARIAStore {
  // Session slice
  sessionId: string | null;
  taskStatus: 'idle' | 'running' | 'paused' | 'awaiting_confirmation' | 'awaiting_input' | 'completed' | 'failed';

  // Voice slice
  isListening: boolean;
  isSpeaking: boolean;
  audioStream: MediaStream | null;

  // Thinking panel slice
  steps: ThinkingStep[];
  currentStepIndex: number;
  pendingConfirmation: ConfirmationRequest | null;
}
```

Rationale: three concurrent real-time streams (WebSocket, SSE, Firestore) update disjoint state slices — Zustand's flat store prevents re-render cascades across slices.

**Component architecture:** Feature-based, not type-based.

```
src/
  app/           # Next.js App Router routes
  components/
    voice/       # VoiceMic, VoiceWaveform, BargeInButton
    thinking-panel/  # ThinkingPanel, StepItem, ConfidenceBadge
    session/     # TaskInput, AuditLog, ScreenshotViewer
    ui/          # shadcn/ui primitives (Button, Card, etc.)
  lib/
    store/       # Zustand store
    hooks/       # useVoice, useThinkingPanel, useAuditLog
    api/         # fetch wrappers for REST endpoints
    ws/          # WebSocket audio relay client
```

---

### Infrastructure & Deployment

**CI/CD: GitHub Actions**

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth
      - run: |
          adk deploy cloud-run \
            --project $GCP_PROJECT \
            --region us-central1 \
            --min-instances 1 \
            --concurrency 1 \
            --memory 4Gi \
            --cpu 2
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - run: npm run build
      - uses: FirebaseExtended/action-hosting-deploy
```

**Concurrency constraint rationale:** `--concurrency 1` is mandatory. Default Cloud Run concurrency is 80 requests/instance. Two concurrent ARIA sessions on one instance = two headless Chromium processes (~500MB each) + two audio WebSocket relays in a 4GB container = OOM crash. With `--concurrency 1`, Cloud Run auto-scales to one instance per active session, giving each session the full 4GB. `--min-instances 1` ensures the warm instance is always available for the first request.

**Environments:**
- Development: `.env.local` (never committed); `adk run` local dev server
- Production: Cloud Run environment variables set via `--set-env-vars` in deploy command; secrets via Google Secret Manager

**Required environment variables:**

```
GEMINI_API_KEY
GCP_PROJECT
FIREBASE_PROJECT_ID
GCS_BUCKET_NAME
CORS_ORIGIN  # Firebase Hosting URL
```

**Monitoring:** ADK built-in OpenTelemetry traces sufficient for hackathon. Cloud Run logs via `gcloud logging read` for debugging.

### Decision Impact Analysis

**Implementation Sequence (order matters):**
1. Backend scaffold + Playwright Docker image
2. Firebase project setup (Auth + Firestore + Hosting)
3. GCP project setup (Cloud Run + GCS bucket + Secret Manager)
4. Planner agent (`gemini-3-1-pro`) with JSON step plan output
5. Executor agent (`gemini-3-flash` + ComputerUseToolset)
6. ADK SequentialAgent root wiring Planner → Executor
7. SSE endpoint (ADK events → frontend)
8. Voice WebSocket handler (browser audio ↔ Gemini Live API)
9. Firestore audit log writer
10. Frontend: Zustand store + three stream consumers
11. Frontend: ThinkingPanel + VoiceUI components
12. GitHub Actions deploy pipeline

**Cross-Component Dependencies:**
- `session_id` flows from ADK runner → REST response → WebSocket path → SSE path → Firestore path — must be consistent string format (`sess_` prefix + UUID v4)
- `is_destructive` flag in Planner JSON output → Executor checks before acting → SSE `awaiting_confirmation` event → frontend confirmation UI → `POST /confirm` → Executor proceeds
- Firestore `uid` from Firebase Anonymous Auth → passed as header to backend → backend scopes Firestore writes to that uid

---

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

9 areas where AI agents could make incompatible choices without explicit rules.

---

### Naming Patterns

**API field naming:** `snake_case` everywhere in JSON payloads exchanged between backend and frontend.
- Backend (Python) produces snake_case naturally; frontend converts at the API layer boundary only.
- Example: `session_id`, `step_index`, `is_destructive`, `screenshot_url`
- Anti-pattern: mixing `sessionId` in some endpoints and `session_id` in others

**REST endpoint naming:** plural nouns for collections, kebab-case paths.
- Correct: `POST /api/task/start`, `GET /api/task/{session_id}/status`
- Anti-pattern: `POST /api/startTask`, `GET /api/getTaskStatus`

**Route/path parameters:** `{session_id}` style (not `:session_id`).

**SSE event types:** `snake_case` verb_noun format.
- Correct: `step_start`, `step_complete`, `task_complete`, `awaiting_confirmation`
- Anti-pattern: `StepStarted`, `stepStart`, `STEP_START`

**Python code:** `snake_case` for all functions, variables, files, and module names.
- Agent files: `planner_agent.py`, `executor_agent.py`
- Functions: `run_planner()`, `write_audit_step()`

**TypeScript/React code:** `camelCase` for variables and functions; `PascalCase` for components and types.
- Components: `ThinkingPanel`, `VoiceWaveform`, `AuditLog`
- Hooks: `useVoice`, `useThinkingPanel`
- Store slices: `sessionSlice`, `voiceSlice`

**Firestore collection/document naming:** `camelCase` collection names, `snake_case` field names.
- Collection: `sessions` (plural)
- Fields: `session_id`, `created_at`, `task_description`

---

### Structure Patterns

**Python agent structure:**
```
aria-backend/
  agents/
    __init__.py          # exports root_agent
    planner_agent.py
    executor_agent.py
    root_agent.py        # SequentialAgent wiring
  tools/
    playwright_computer.py
  handlers/
    voice_handler.py     # Gemini Live API WebSocket relay
    sse_handler.py       # ADK events → SSE stream
    audit_writer.py      # Firestore + GCS writes
  prompts/
    planner_system.py
    executor_system.py
  main.py                # FastAPI app entrypoint
```

**TypeScript project structure:** Feature-based under `src/components/`, type-based only for `src/lib/`.
- All voice UI components live in `src/components/voice/`
- All thinking panel components live in `src/components/thinking-panel/`
- No component files directly in `src/components/` root

**Test file location:** Co-located with source — `foo.test.ts` next to `foo.ts` for frontend; `tests/test_foo.py` at backend root for Python.

---

### Format Patterns

**API response wrapper — ALL REST responses use this envelope:**
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```
Error case:
```json
{
  "success": false,
  "data": null,
  "error": { "code": "TASK_NOT_FOUND", "message": "Session not found" }
}
```

**HTTP error codes:** `200` success, `400` bad request, `401` unauthorized, `404` not found, `409` conflict (e.g. task already running), `500` server error. Never use `200` for errors.

**Dates/timestamps:** ISO 8601 strings everywhere (`2026-02-24T14:30:00Z`). Never Unix timestamps in API or Firestore.

**Planner JSON step plan — canonical schema (all agents must match exactly):**
```json
{
  "task_summary": "string",
  "steps": [
    {
      "step_index": 0,
      "description": "string",
      "action": "navigate | click | type | scroll | screenshot | wait",
      "target": "string or null",
      "value": "string or null",
      "confidence": 0.0,
      "is_destructive": false,
      "requires_user_input": false,
      "user_input_reason": "string or null"
    }
  ]
}
```

---

### Communication Patterns

**SSE event envelope — canonical (frontend EventSource consumer must match exactly):**
```json
{
  "event_type": "step_start | step_complete | step_error | plan_ready | awaiting_confirmation | awaiting_input | task_complete | task_failed",
  "session_id": "sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "step_index": 0,
  "timestamp": "ISO8601",
  "payload": {}
}
```

**Zustand state updates:** Always use immer-style via Zustand's `set()` — never mutate state directly.
```typescript
// Correct
set((state) => { state.steps.push(newStep); });
// Anti-pattern
state.steps.push(newStep); // direct mutation
```

**WebSocket audio chunks:** Raw PCM, 16kHz, 16-bit, mono. Fixed format — no runtime encoding negotiation.

---

### Process Patterns

**Error handling:**
- Backend: all agent errors caught at the FastAPI route level; emit `task_failed` SSE event; never propagate exceptions as HTML 500 pages
- Frontend: all SSE `task_failed` events update `taskStatus` to `'failed'` and surface `error.message` in UI — no silent failures
- Retry: Executor retries a failed action at most **2 times** before escalating to `step_error` SSE and pausing for user input

**Loading states:** Each stream has its own loading boolean in Zustand — `isSessionStarting`, `isVoiceConnecting`, `isThinkingPanelConnecting`. Never a single global loading flag.

**Destructive action flow — exact sequence all agents must follow:**
1. Planner sets `is_destructive: true` on the step
2. Executor detects flag before executing — never executes without confirmation
3. Backend emits `awaiting_confirmation` SSE event
4. Frontend shows confirmation UI + speaks TTS confirmation
5. User confirms via voice or UI → `POST /api/task/{session_id}/confirm`
6. Executor proceeds only after receiving confirm signal

**Context window management:** Executor context = system prompt + current step plan + last 3 completed step results + current screenshot. Older steps summarized into a single `completed_steps_summary` string.

**Barge-in cancellation primitive:** Each session owns one `asyncio.Event` keyed by `session_id`, stored in a module-level dict in `session_service.py`. Pattern:

```python
# session_service.py
_cancel_flags: dict[str, asyncio.Event] = {}

def get_cancel_flag(session_id: str) -> asyncio.Event:
    if session_id not in _cancel_flags:
        _cancel_flags[session_id] = asyncio.Event()
    return _cancel_flags[session_id]

def signal_barge_in(session_id: str):
    get_cancel_flag(session_id).set()

def reset_cancel_flag(session_id: str):
    get_cancel_flag(session_id).clear()
```

`voice_handler.py` calls `signal_barge_in(session_id)` when VAD detects speech mid-execution. `playwright_computer.py` checks `cancel_flag.is_set()` before AND after every Playwright `await` call and raises `BargeInException` if set. The Executor's step loop catches `BargeInException`, stops execution, and returns control to `voice_handler.py` for replanning. This is the correct Python pattern — `task.cancel()` is NOT used because it injects `CancelledError` unpredictably across unrelated awaits.

**Audio relay queue pattern:** `voice_handler.py` must treat the browser ↔ Gemini Live relay as a pure pass-through pipe using `asyncio.Queue`. No logging, no inspection, no JSON parsing of audio bytes in the relay path:

```python
# voice_handler.py — canonical structure
async def relay_audio(session_id: str, browser_ws: WebSocket):
    inbound_q: asyncio.Queue[bytes] = asyncio.Queue()
    outbound_q: asyncio.Queue[bytes] = asyncio.Queue()

    async def browser_to_queue():
        async for chunk in browser_ws.iter_bytes():
            await inbound_q.put(chunk)  # never inspect or log chunk

    async def queue_to_gemini(gemini_session):
        while True:
            chunk = await inbound_q.get()
            await gemini_session.send(chunk)

    async def gemini_to_browser(gemini_session):
        async for response in gemini_session:
            await outbound_q.put(response.audio)

    async def queue_to_browser():
        while True:
            audio = await outbound_q.get()
            await browser_ws.send_bytes(audio)

    await asyncio.gather(
        browser_to_queue(),
        queue_to_gemini(gemini_session),
        gemini_to_browser(gemini_session),
        queue_to_browser(),
    )
```

Rationale: Python's GIL causes micro-stutters when the event loop is busy with JSON parsing or logging while audio chunks are waiting. The queue decouples receipt from forwarding, keeping the hot path non-blocking. Any barge-in detection logic runs in a separate coroutine that reads from a side-channel, never from the audio queue itself.

---

### Enforcement Guidelines

**All AI Agents MUST:**
- Use `snake_case` for all JSON field names in API payloads and Firestore documents
- Use the canonical SSE event envelope schema exactly — no additional top-level fields
- Use the canonical Planner step plan schema exactly — no field renames
- Wrap all REST responses in the `{ success, data, error }` envelope
- Never execute a step where `is_destructive: true` without a confirmed `POST /confirm`
- Always emit a `task_failed` SSE event on unhandled exceptions — no silent failures
- Use `sess_` prefix + UUID v4 for all session IDs (format: `sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- Never use `task.cancel()` for barge-in — always use the session `asyncio.Event` cancellation primitive
- Never log, inspect, or await anything in the audio relay hot path — pure `asyncio.Queue` pass-through only
- Deploy with `--concurrency 1 --memory 4Gi` — never rely on Cloud Run default concurrency (80) for Playwright workloads

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
gemini-hackathon/
├── README.md
├── .github/
│   └── workflows/
│       └── deploy.yml               # GitHub Actions: deploy backend + frontend
│
├── aria-frontend/                   # Next.js 15 — Firebase Hosting
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── .env.local                   # gitignored
│   ├── .env.example
│   ├── .gitignore
│   ├── public/
│   │   └── aria-logo.svg
│   └── src/
│       ├── app/
│       │   ├── globals.css
│       │   ├── layout.tsx            # Firebase Auth init, root layout
│       │   └── page.tsx              # Main ARIA UI (single-page app)
│       ├── components/
│       │   ├── ui/                   # shadcn/ui primitives (Button, Card, Badge, etc.)
│       │   ├── voice/
│       │   │   ├── VoiceMic.tsx      # Mic button, press-to-talk + VAD toggle
│       │   │   ├── VoiceWaveform.tsx # Live audio amplitude visualizer
│       │   │   └── BargeInButton.tsx # Interrupt / stop button
│       │   ├── thinking-panel/
│       │   │   ├── ThinkingPanel.tsx # Container: step list + current action
│       │   │   ├── StepItem.tsx      # Individual step row with status + confidence
│       │   │   ├── ConfidenceBadge.tsx
│       │   │   └── ConfirmationModal.tsx  # Destructive action guard UI
│       │   └── session/
│       │       ├── TaskInput.tsx     # Text input + submit (fallback to voice)
│       │       ├── AuditLog.tsx      # Firestore real-time audit log viewer
│       │       └── ScreenshotViewer.tsx   # Annotated step screenshot display
│       ├── lib/
│       │   ├── store/
│       │   │   └── aria-store.ts     # Zustand store (session + voice + thinking-panel slices)
│       │   ├── hooks/
│       │   │   ├── useVoice.ts       # WebSocket audio relay, MediaRecorder setup
│       │   │   ├── useThinkingPanel.ts  # EventSource SSE consumer
│       │   │   └── useAuditLog.ts    # Firestore onSnapshot subscription
│       │   ├── api/
│       │   │   └── task.ts           # fetch wrappers: startTask, interrupt, confirm, input
│       │   ├── firebase.ts           # Firebase app init + Anonymous Auth
│       │   └── utils.ts              # shared helpers (formatISO, cn, etc.)
│       └── types/
│           └── aria.ts               # Shared TS types: Step, SSEEvent, TaskStatus, etc.
│
└── aria-backend/                    # Python ADK — Cloud Run
    ├── Dockerfile                   # FROM mcr.microsoft.com/playwright:v1.50.0-jammy
    ├── requirements.txt             # pip freeze for Docker layer caching
    ├── pyproject.toml               # ADK project config
    ├── .env                         # gitignored
    ├── .env.example
    ├── .gitignore
    ├── main.py                      # FastAPI app: REST routes + WebSocket + SSE
    ├── agents/
    │   ├── __init__.py              # exports root_agent
    │   ├── root_agent.py            # SequentialAgent: [planner_agent, executor_agent]
    │   ├── planner_agent.py         # Agent(model='gemini-3-1-pro', ...)
    │   └── executor_agent.py        # Agent(model='gemini-3-flash', tools=[ComputerUseToolset])
    ├── prompts/
    │   ├── planner_system.py        # Planner system prompt (4-section format)
    │   └── executor_system.py       # Executor system prompt + prompt injection sandboxing
    ├── tools/
    │   └── playwright_computer.py   # PlaywrightComputer wrapper + get_accessibility_tree()
    ├── handlers/
    │   ├── voice_handler.py         # WebSocket /ws/audio/{session_id}: browser ↔ Gemini Live
    │   ├── sse_handler.py           # GET /api/stream/{session_id}: ADK OTel events → SSE
    │   └── audit_writer.py          # Firestore step writes + GCS screenshot uploads
    ├── services/
    │   ├── session_service.py       # Session creation, status updates, Firebase uid scoping
    │   └── gcs_service.py           # GCS upload: sessions/{session_id}/steps/{step_index:04d}.png
    └── tests/
        ├── test_planner_agent.py    # adk eval + unit tests for JSON plan output
        ├── test_executor_agent.py   # action execution tests against mock Playwright
        ├── test_voice_handler.py    # WebSocket relay tests
        └── test_audit_writer.py     # Firestore write verification
```

---

### Architectural Boundaries

**API Boundaries:**

| Boundary | Protocol | Direction | Auth |
|---|---|---|---|
| Browser → Backend (task start) | HTTPS REST | Request/Response | Firebase ID Token header |
| Browser → Backend (voice audio) | WebSocket `/ws/audio/{session_id}` | Bidirectional | session_id in path |
| Backend → Browser (thinking panel) | SSE `/api/stream/{session_id}` | Server push | session_id in path |
| Browser → Firestore (audit log) | Firestore SDK real-time | Server push | Firebase Anonymous Auth |
| Backend → Gemini Live API | WebSocket (google-genai SDK) | Bidirectional | GEMINI_API_KEY |
| Backend → Vertex AI | HTTPS (google-genai SDK) | Request/Response | GCP service account |
| Backend → Firestore | Firestore Admin SDK | Read/Write | GCP service account |
| Backend → GCS | GCS Client Library | Write | GCP service account |

**Component Ownership Boundaries:**

- `planner_agent.py` owns: task decomposition, JSON step plan, `requires_user_input` detection — never executes browser actions
- `executor_agent.py` owns: all browser interactions via `ComputerUseToolset`, action verification, `is_destructive` enforcement — never modifies step plan
- `voice_handler.py` owns: the WebSocket audio relay loop exclusively — no task logic
- `audit_writer.py` owns: all Firestore and GCS writes — no other file writes to Firestore
- `aria-store.ts` owns: all client state — no component holds local state for session/voice/steps

**Data Boundaries:**

- Planner → Executor: JSON step plan only (no screenshots, no DOM data)
- Executor → audit_writer: completed step result dict only
- Backend → Frontend (SSE): SSE event envelope only — never raw Gemini API responses
- Frontend → Firestore: read-only (Firestore security rules block client writes)

---

### Requirements to Structure Mapping

| Functional Requirement | Primary File(s) |
|---|---|
| Voice task input | `voice_handler.py`, `VoiceMic.tsx`, `useVoice.ts` |
| Text task input | `TaskInput.tsx`, `lib/api/task.ts` |
| Task decomposition | `planner_agent.py`, `prompts/planner_system.py` |
| Step plan display | `ThinkingPanel.tsx`, `StepItem.tsx`, `useThinkingPanel.ts` |
| Browser execution | `executor_agent.py`, `tools/playwright_computer.py` |
| Live thinking panel | `sse_handler.py`, `useThinkingPanel.ts`, `ThinkingPanel.tsx` |
| Voice narration | `voice_handler.py` (TTS from Gemini Live), `VoiceWaveform.tsx` |
| Voice barge-in | `voice_handler.py` (native VAD), `BargeInButton.tsx` |
| Mid-task user input | `planner_agent.py` (requires_user_input), `ConfirmationModal.tsx`, `task.ts` |
| Destructive action guard | `executor_agent.py` (is_destructive check), `ConfirmationModal.tsx`, `task.ts` |
| Confidence scoring | `planner_agent.py` (confidence per step), `ConfidenceBadge.tsx` |
| Audit log | `audit_writer.py`, `services/gcs_service.py`, `AuditLog.tsx`, `useAuditLog.ts` |
| Structured output display | `ThinkingPanel.tsx`, `ScreenshotViewer.tsx` |

---

### Data Flow

```
User speaks
  → VoiceMic (browser MediaRecorder, 16kHz PCM)
  → WebSocket /ws/audio/{session_id}
  → voice_handler.py relays to Gemini Live API
  → Gemini Live returns intent text
  → voice_handler triggers POST /api/task/start

Task starts
  → session_service creates Firestore doc (status: running)
  → root_agent.run_async() → planner_agent
  → planner_agent returns JSON step plan
  → sse_handler emits plan_ready SSE event
  → ThinkingPanel renders step list

Execution loop (per step)
  → executor_agent receives step
  → PlaywrightComputer executes action
  → screenshot captured → GCS upload
  → audit_writer writes step to Firestore
  → sse_handler emits step_complete SSE event
  → StepItem updates status in ThinkingPanel
  → AuditLog reflects new step (Firestore onSnapshot)

On is_destructive step
  → executor_agent pauses before acting
  → sse_handler emits awaiting_confirmation SSE event
  → ConfirmationModal appears + TTS speaks prompt
  → User confirms → POST /api/task/{session_id}/confirm
  → executor_agent proceeds

On barge-in
  → Gemini Live VAD detects voice mid-execution
  → voice_handler interrupts current ADK runner step
  → Gemini Live re-processes new utterance
  → planner_agent replans from current browser state
```

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All technology choices are compatible. Python 3.11 + ADK v1.25 is the current stable pairing. `gemini-3-flash` with built-in computer use removes the need for a separate computer use model and is compatible with ADK's `ComputerUseToolset`. Next.js 15 App Router + Tailwind + shadcn/ui + Zustand have no version conflicts. Firebase Anonymous Auth integrates cleanly with Firestore security rules.

**Pattern Consistency:**
`snake_case` API fields align naturally with Python backend conventions. Zustand's immutable `set()` pattern is consistent with React's rendering model. The SSE envelope schema is aligned with ADK's OpenTelemetry event structure. All naming conventions are internally consistent across backend and frontend.

**Structure Alignment:**
Every file in the project tree traces directly to an architectural decision. `audit_writer.py` is the sole Firestore writer (enforced by boundary rules). `aria-store.ts` is the sole client state owner. Component feature-grouping matches the thinking panel / voice / session architectural split.

---

### Requirements Coverage Validation ✅

**Functional Requirements (13/13 covered):**

| FR | Covered By | Status |
|---|---|---|
| Voice task input | `voice_handler.py` + Gemini Live VAD | ✅ |
| Text task input | `TaskInput.tsx` + `task.ts` | ✅ |
| Task decomposition | `planner_agent.py` + `planner_system.py` | ✅ |
| Step plan display | `ThinkingPanel.tsx` + SSE `plan_ready` event | ✅ |
| Browser execution | `executor_agent.py` + `playwright_computer.py` | ✅ |
| Live thinking panel | `sse_handler.py` + `useThinkingPanel.ts` | ✅ |
| Voice narration | `voice_handler.py` TTS path | ✅ |
| Voice barge-in | Gemini Live native VAD in `voice_handler.py` | ✅ |
| Mid-task user input | `requires_user_input` flag + `awaiting_input` SSE + `POST /input` | ✅ |
| Destructive action guard | `is_destructive` flag + `awaiting_confirmation` SSE + `POST /confirm` | ✅ |
| Confidence scoring | Planner JSON `confidence` field + `ConfidenceBadge.tsx` | ✅ |
| Audit log | `audit_writer.py` + Firestore + GCS + `AuditLog.tsx` | ✅ |
| Structured output display | `ThinkingPanel.tsx` + `ScreenshotViewer.tsx` | ✅ |

**Non-Functional Requirements (7/7 covered):**

| NFR | Architectural Coverage | Status |
|---|---|---|
| Barge-in < 1s | Native Gemini Live VAD, no buffering, server-side relay | ✅ |
| Thinking panel < 500ms | ADK OTel → SSE direct, no DB round-trip in hot path | ✅ |
| Voice-to-first-action < 3s | Parallel planner + screenshot, `gemini-3-1-pro` fast-path | ✅ |
| Gemini Live 1–1.8s | Streaming mode config enforced in `voice_handler.py` | ✅ |
| Destructive detection 100% | Deterministic flag in Planner JSON, enforced in Executor before every action | ✅ |
| Cloud Run cold start zero | `--min-instances 1` in deploy command | ✅ |
| Chromium stability | Container memory ≥ 4GB, `--no-sandbox`, `--disable-dev-shm-usage` in Dockerfile | ✅ |

---

### Implementation Readiness Validation ✅

**Decision Completeness:** All critical decisions documented with exact model strings, library versions, deploy commands, and environment variable names. Zero ambiguous decisions.

**Structure Completeness:** Every file named with purpose. Component, handler, service, and agent boundaries all explicitly defined. No placeholder directories.

**Pattern Completeness:** 9 conflict point categories addressed. Canonical schemas defined for Planner JSON, SSE envelope, and API response wrapper. Exact destructive action flow documented step-by-step.

---

### Gap Analysis Results

**Critical Gaps:** None.

**Important (address in first implementation sprint):**
- `firestore.rules` not listed in project tree — add to `aria-frontend/firestore.rules` before deployment
- `firebase.json` and `.firebaserc` not listed — add to `aria-frontend/` for `firebase deploy`

**Nice-to-have:**
- `docker-compose.yml` at repo root for local full-stack development
- `CONTRIBUTING.md` with dev setup steps

---

### Architecture Completeness Checklist

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (High — novel AI stack)
- [x] Technical constraints identified (Cloud Run, Playwright, model strings)
- [x] Cross-cutting concerns mapped (6 identified)
- [x] Model stack confirmed and updated to latest (`gemini-3-flash` replaces deprecated computer use model)
- [x] Technology stack fully specified with versions
- [x] All integration patterns defined (REST + WebSocket + SSE + Firestore)
- [x] Performance considerations addressed for every NFR
- [x] Naming conventions: snake_case / camelCase / PascalCase boundaries defined
- [x] Canonical schemas: Planner JSON, SSE envelope, API response wrapper
- [x] Process patterns: destructive action flow, error handling, retry, context truncation
- [x] Enforcement guidelines: 7 mandatory rules for all AI agents
- [x] Complete directory tree with every file named and annotated
- [x] Component ownership boundaries defined
- [x] Data boundaries enforced (read-only Firestore client, single audit writer)
- [x] All 13 FRs mapped to specific files

---

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Executor model updated to `gemini-3-flash` with built-in computer use — more capable, no separate model dependency
- Three real-time streams (WebSocket/SSE/Firestore) are architecturally isolated and independently resilient
- Destructive action guard is deterministic (flag-based) — satisfies 100% detection NFR
- ADK's native OpenTelemetry eliminates all custom instrumentation for the thinking panel
- Firebase Anonymous Auth provides session isolation at zero user friction

**Areas for Future Enhancement (post-hackathon):**
- WebRTC for voice transport (~200ms lower latency vs WebSocket relay)
- Vector DB semantic memory for cross-session preference learning
- Vertex AI Agent Engine migration once Playwright support is added

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use the canonical Planner JSON schema and SSE envelope — no field additions or renames
- Respect component ownership boundaries — `audit_writer.py` is the sole Firestore writer
- Refer to the Implementation Patterns section for all naming and format questions
- The destructive action 6-step flow is mandatory — no shortcuts

**First Implementation Priority (in order):**
1. `npx create-next-app@latest aria-frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack`
2. `pip install google-adk && adk new aria-backend`
3. Firebase project setup + `firestore.rules` + Anonymous Auth
4. GCP project setup + GCS bucket + Secret Manager secrets
5. Planner agent with canonical JSON step plan output

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All technology choices are compatible. Python 3.11 + ADK v1.25 is the current stable pairing. `gemini-3-flash` with built-in computer use removes the need for a separate computer use model and is compatible with ADK's `ComputerUseToolset`. Next.js 15 App Router + Tailwind + shadcn/ui + Zustand have no version conflicts. Firebase Anonymous Auth integrates cleanly with Firestore security rules.

**Pattern Consistency:**
`snake_case` API fields align naturally with Python backend conventions. Zustand's immutable `set()` pattern is consistent with React's rendering model. The SSE envelope schema is aligned with ADK's OpenTelemetry event structure. All naming conventions are internally consistent across backend and frontend.

**Structure Alignment:**
Every file in the project tree traces directly to an architectural decision. `audit_writer.py` is the sole Firestore writer (enforced by boundary rules). `aria-store.ts` is the sole client state owner. Component feature-grouping matches the thinking panel / voice / session architectural split.

---

### Requirements Coverage Validation ✅

**Functional Requirements (13/13 covered):**

| FR | Covered By | Status |
|---|---|---|
| Voice task input | `voice_handler.py` + Gemini Live VAD | ✅ |
| Text task input | `TaskInput.tsx` + `task.ts` | ✅ |
| Task decomposition | `planner_agent.py` + `planner_system.py` | ✅ |
| Step plan display | `ThinkingPanel.tsx` + SSE `plan_ready` event | ✅ |
| Browser execution | `executor_agent.py` + `playwright_computer.py` | ✅ |
| Live thinking panel | `sse_handler.py` + `useThinkingPanel.ts` | ✅ |
| Voice narration | `voice_handler.py` TTS path | ✅ |
| Voice barge-in | Gemini Live native VAD in `voice_handler.py` | ✅ |
| Mid-task user input | `requires_user_input` flag + `awaiting_input` SSE + `POST /input` | ✅ |
| Destructive action guard | `is_destructive` flag + `awaiting_confirmation` SSE + `POST /confirm` | ✅ |
| Confidence scoring | Planner JSON `confidence` field + `ConfidenceBadge.tsx` | ✅ |
| Audit log | `audit_writer.py` + Firestore + GCS + `AuditLog.tsx` | ✅ |
| Structured output display | `ThinkingPanel.tsx` + `ScreenshotViewer.tsx` | ✅ |

**Non-Functional Requirements (7/7 covered):**

| NFR | Architectural Coverage | Status |
|---|---|---|
| Barge-in < 1s | Native Gemini Live VAD, no buffering, server-side relay | ✅ |
| Thinking panel < 500ms | ADK OTel → SSE direct, no DB round-trip in hot path | ✅ |
| Voice-to-first-action < 3s | Parallel planner + screenshot, `gemini-3-1-pro` fast-path | ✅ |
| Gemini Live 1–1.8s | Streaming mode config enforced in `voice_handler.py` | ✅ |
| Destructive detection 100% | Deterministic flag in Planner JSON, enforced in Executor before every action | ✅ |
| Cloud Run cold start zero | `--min-instances 1` in deploy command | ✅ |
| Chromium stability | Container memory ≥ 4GB, `--no-sandbox`, `--disable-dev-shm-usage` in Dockerfile | ✅ |

---

### Implementation Readiness Validation ✅

**Decision Completeness:** All critical decisions documented with exact model strings, library versions, deploy commands, and environment variable names. Zero ambiguous decisions.

**Structure Completeness:** Every file named with purpose. Component, handler, service, and agent boundaries all explicitly defined. No placeholder directories.

**Pattern Completeness:** 9 conflict point categories addressed. Canonical schemas defined for Planner JSON, SSE envelope, and API response wrapper. Exact destructive action flow sequence documented step-by-step.

---

### Gap Analysis Results

**Critical Gaps:** None.

**Important (address in first implementation sprint):**
- `firestore.rules` not listed in project tree — add to `aria-frontend/firestore.rules` before deployment
- `firebase.json` and `.firebaserc` not listed — add to `aria-frontend/` for `firebase deploy`

**Nice-to-have:**
- `docker-compose.yml` at repo root for local full-stack development
- `CONTRIBUTING.md` with dev setup steps

---

### Architecture Completeness Checklist

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (High — novel AI stack)
- [x] Technical constraints identified (Cloud Run, Playwright, model strings)
- [x] Cross-cutting concerns mapped (6 identified)
- [x] Model stack confirmed and updated to latest (`gemini-3-flash` replaces deprecated computer use model)
- [x] Technology stack fully specified with versions
- [x] All integration patterns defined (REST + WebSocket + SSE + Firestore)
- [x] Performance considerations addressed for every NFR
- [x] Naming conventions: snake_case / camelCase / PascalCase boundaries defined
- [x] Canonical schemas: Planner JSON, SSE envelope, API response wrapper
- [x] Process patterns: destructive action flow, error handling, retry, context truncation
- [x] Enforcement guidelines: 7 mandatory rules for all AI agents
- [x] Complete directory tree with every file named and annotated
- [x] Component ownership boundaries defined
- [x] Data boundaries enforced (read-only Firestore client, single audit writer)
- [x] All 13 FRs mapped to specific files

---

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Executor model updated to `gemini-3-flash` with built-in computer use — more capable, no separate model dependency
- Three real-time streams (WebSocket/SSE/Firestore) are architecturally isolated and independently resilient
- Destructive action guard is deterministic (flag-based, not heuristic) — satisfies 100% detection NFR
- ADK's native OpenTelemetry eliminates all custom instrumentation for the thinking panel
- Firebase Anonymous Auth provides session isolation at zero user friction

**Areas for Future Enhancement (post-hackathon):**
- WebRTC for voice transport (~200ms lower latency vs WebSocket relay)
- Vector DB semantic memory for cross-session preference learning
- Vertex AI Agent Engine migration once Playwright support is added

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use the canonical Planner JSON schema and SSE envelope — no field additions or renames
- Respect component ownership boundaries — `audit_writer.py` is the sole Firestore writer
- Refer to the Implementation Patterns section for all naming and format questions
- The destructive action 6-step flow is mandatory — no shortcuts

**First Implementation Priority (in order):**
1. `npx create-next-app@latest aria-frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack`
2. `pip install google-adk && adk new aria-backend`
3. Firebase project setup + `firestore.rules` + Anonymous Auth
4. GCP project setup + GCS bucket + Secret Manager secrets
5. Planner agent with canonical JSON step plan output
