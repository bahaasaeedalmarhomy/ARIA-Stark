# Project Structure & Boundaries

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
