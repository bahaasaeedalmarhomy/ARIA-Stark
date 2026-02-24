# Project Context Analysis

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
