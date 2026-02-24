# Core Architectural Decisions

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
