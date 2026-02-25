---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
workflowType: 'create-epics-and-stories'
date: 2026-02-24
author: Bahaa
project_name: gemini-hackathon
---

# gemini-hackathon - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for ARIA (Adaptive Reasoning & Interaction Agent), decomposing requirements from the PRD, Architecture, and UX Design Specification into implementable stories.

---

## Requirements Inventory

### Functional Requirements

**Task Input & Session Initiation**
- FR1: User can assign a task to ARIA using natural language voice input
- FR2: User can assign a task to ARIA using natural language text input
- FR3: User can provide supplementary context (e.g., paste document content, provide field values) as part of a task assignment
- FR4: User can start a new task session at any time
- FR5: User can cancel an in-progress task session
- FR6: ARIA displays the interpreted task back to the user before execution begins
- FR7: ARIA presents an ordered, human-readable step plan to the user before the Executor begins acting

**Agent Execution (Browser Navigation)**
- FR8: ARIA can navigate to a URL in a controlled browser session
- FR9: ARIA can click interactive elements (buttons, links, checkboxes, dropdowns) on a web page
- FR10: ARIA can type text into input fields and text areas on a web page
- FR11: ARIA can scroll a web page vertically and horizontally
- FR12: ARIA can submit forms on a web page
- FR13: ARIA can read and extract visible text content from a web page
- FR14: ARIA can identify and interact with UI elements using visual understanding (Gemini Computer Use screenshot interpretation)
- FR15: ARIA can detect when a page has finished loading before proceeding to the next action
- FR16: ARIA can recover from a failed action by re-evaluating the page state and retrying (max 2 retries)

**Live Transparency & Thinking Panel**
- FR17: User can view a real-time feed of ARIA's current step, what it is looking at, and what action it plans to take next
- FR18: User can view an annotated screenshot of the current browser state within the thinking panel
- FR19: User can view ARIA's confidence level for the current action within the thinking panel
- FR20: The thinking panel updates to reflect each new Executor action as it occurs
- FR21: ARIA narrates its actions aloud in natural language as it executes each step
- FR22: User can view the full ordered step plan and track which step is currently active

**Voice Interaction & Barge-in**
- FR23: User can speak to ARIA at any time during task execution without pressing a button (always-on VAD)
- FR24: User can interrupt ARIA mid-execution with a voice command and ARIA stops the current action within 1 second
- FR25: ARIA resumes listening for a new instruction after a barge-in interruption
- FR26: ARIA adapts its execution plan in response to a mid-task voice correction from the user
- FR27: ARIA responds to the user in natural spoken voice during and after task execution

**Safety, Control & Confirmation**
- FR28: ARIA detects when an action is irreversible (form submission, purchase, record deletion, content publishing) before executing it
- FR29: ARIA pauses execution and presents a confirmation request before executing any detected irreversible action
- FR30: ARIA presents the confirmation request in both voice (spoken) and visual (UI) form simultaneously
- FR31: ARIA proceeds with the irreversible action only upon explicit user approval
- FR32: ARIA cancels the irreversible action and remains paused if user declines or does not respond
- FR33: ARIA pauses execution and requests missing information from the user when required data is unavailable

**Audit Log & Session Record**
- FR34: ARIA records every action taken during a task session, including step description, action type, and timestamp
- FR35: ARIA captures a screenshot of the browser state at each significant step and associates it with the corresponding audit log entry
- FR36: User can view the audit log for a completed session, including all steps and screenshots, after execution finishes
- FR37: The audit log is persisted to durable storage and survives browser refresh or session end

**System & Deployment**
- FR38: The ARIA backend runs as a deployed service on Google Cloud Run accessible via HTTPS
- FR39: The ARIA frontend is accessible via a public URL without requiring local installation
- FR40: ARIA operates within a sandboxed browser environment isolated from the user's local machine
- FR41: ARIA handles page load failures and network errors during execution without crashing the session
- FR42: ARIA handles CAPTCHA encounters by pausing and notifying the user that manual intervention is required

---

### NonFunctional Requirements

**Performance**
- NFR1: Voice-to-first-browser-action latency < 3 seconds end-to-end
- NFR2: Barge-in interruption response < 1 second from utterance to execution halt
- NFR3: Gemini Live API voice round-trip 1–1.8 seconds (streaming mode; buffered unacceptable)
- NFR4: Thinking panel → Executor sync lag < 500ms per step
- NFR5: Screenshot render in thinking panel < 300ms after receipt
- NFR6: First Contentful Paint (frontend) < 2 seconds

**Security**
- NFR7: Executor browser session runs in sandboxed Chromium; no access to host container filesystem or env vars
- NFR8: Gemini API keys and GCP credentials must never be exposed to the frontend; all model calls are server-side
- NFR9: Page content passed to Planner must be wrapped in `<page_content>` XML tag; system prompt must prevent prompt injection
- NFR10: Backend must not exfiltrate page content or screenshots beyond the session's Firestore audit log
- NFR11: Screenshot and session data in Firestore/GCS must be scoped to the active session only (Firebase Anonymous Auth uid)

**Reliability**
- NFR12: Cloud Run deployed with `--min-instances 1` to eliminate cold starts during demo
- NFR13: Playwright/Chromium completes a full demo run without crash across 10 consecutive test runs
- NFR14: Page load timeout handling: report failure to user within 15 seconds without crashing
- NFR15: Gemini API errors retry max 2 times before surfacing error to user
- NFR16: SSE auto-reconnect on connection drop (no manual refresh required)

**Scalability**
- NFR17: Backend supports one active session reliably; multi-session concurrency not required for MVP
- NFR18: Cloud Run `--concurrency 1` to prevent OOM crash from concurrent Chromium instances

**Accessibility**
- NFR19: All UI controls (task input, voice button, confirmation dialogs) must be keyboard-navigable
- NFR20: Text content in thinking panel must meet WCAG AA colour contrast ratio (4.5:1)

---

### Additional Requirements

**Architecture — Infrastructure & Stack**
- Starter: `create-next-app` (Next.js 16, TypeScript, App Router, Tailwind v4, ESLint, Turbopack stable default) for frontend; `adk new aria-backend` Python scaffold for backend — these are Epic 1 Story 1 and Story 2
- Backend runtime: Python 3.11+, Google ADK v1.25+, FastAPI entrypoint (`main.py`)
- Container: `mcr.microsoft.com/playwright:v1.50.0-jammy` base image, 4GB RAM, `--no-sandbox --disable-dev-shm-usage`
- Planner model: `gemini-3-1-pro`; Executor model: `gemini-3-flash` (built-in computer use via ADK `ComputerUseToolset`)
- Voice model: `gemini-3-flash` (fully multimodal — handles both Executor actions and voice interaction; same model for both roles)
- GCS screenshot path convention: `sessions/{session_id}/steps/{step_index:04d}.png`
- Session ID format: `sess_` prefix + UUID v4; owned by backend ADK runner

**Architecture — API & Communication**
- REST endpoints: `POST /api/task/start`, `POST /api/task/{session_id}/interrupt`, `POST /api/task/{session_id}/confirm`, `POST /api/task/{session_id}/input`, `GET /api/task/{session_id}/status`
- WebSocket: `/ws/audio/{session_id}` — bidirectional, raw PCM 16kHz 16-bit mono
- SSE: `/api/stream/{session_id}` — unidirectional, ADK OpenTelemetry events as JSON
- Firestore real-time subscription for audit log display (no backend round-trip)
- All REST JSON payloads: `snake_case` field names; canonical response envelope (`success`, `data`, `error`)
- SSE event types: `step_start`, `step_complete`, `step_error`, `plan_ready`, `awaiting_confirmation`, `awaiting_input`, `task_complete`, `task_failed`

**Architecture — Auth & Security**
- Firebase Anonymous Auth: uid scopes Firestore session documents; `idToken` passed in Authorization header to `POST /api/task/start`
- CORS on Cloud Run locked to Firebase Hosting origin

**Architecture — Data & State**
- Firestore collection: `sessions` (plural); document fields: `snake_case`
- Zustand frontend state: three slices — session, voice, thinkingPanel
- Executor context window: system prompt + current step plan + last 3 completed steps + current screenshot (older steps summarized)
- Barge-in cancel flag: `asyncio.Event` per session stored in module-level dict in `session_service.py`
- Audio relay: `asyncio.Queue` pass-through in `voice_handler.py` — no audio inspection in hot path

**Architecture — CI/CD**
- GitHub Actions deploy pipeline: `deploy-backend` (Cloud Run) + `deploy-frontend` (Firebase Hosting)
- Environment variables: `GEMINI_API_KEY`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `GCS_BUCKET_NAME`, `CORS_ORIGIN`; secrets via Google Secret Manager

**UX Design**
- Dark-first theme: `zinc-950` page background, `zinc-900` panels, `zinc-800` step cards
- Semantic signal tokens: `#3B82F6` blue (active step), `#10B981` emerald (success/high confidence), `#F59E0B` amber (warning/mid confidence), `#F43F5E` rose (danger/low confidence/destructive guard), `#A78BFA` violet (paused/barge-in)
- Typography: Geist Sans (UI) + Geist Mono (step descriptions/action text)
- Custom components required: `VoiceWaveform` (state-driven amplitude bars), `StepItem` (index, description, status icon, confidence badge, expandable screenshot), `ConfidenceBadge` (color-coded pill), `BargeInPulse` (ripple animation on VAD), `ScreenshotViewer` (annotated with bounding boxes)
- Always-visible voice waveform in layout sidebar — not in a modal or overlay
- Barge-in visual acknowledgment within 200ms of VAD detection (before backend processes utterance)
- "Always listening" label visible in voice indicator to set VAD expectation
- Step plan items appear with stagger animation as Planner returns them
- Minimum supported viewport: 1280px wide (desktop-first)

---

### FR Coverage Map

| FR | Epic |
|---|---|
| FR1: Voice task input | Epic 4 |
| FR2: Text task input | Epic 1 |
| FR3: Supplementary context input | Epic 2 |
| FR4: Start new session | Epic 1 |
| FR5: Cancel in-progress session | Epic 3 |
| FR6: Display interpreted task | Epic 2 |
| FR7: Ordered step plan display | Epic 2 |
| FR8: Navigate to URL | Epic 3 |
| FR9: Click interactive elements | Epic 3 |
| FR10: Type into input fields | Epic 3 |
| FR11: Scroll page | Epic 3 |
| FR12: Submit forms | Epic 3 |
| FR13: Read/extract page text | Epic 3 |
| FR14: Visual UI identification (Computer Use) | Epic 3 |
| FR15: Page load detection | Epic 3 |
| FR16: Retry on failed action | Epic 3 |
| FR17: Real-time step feed | Epic 2 |
| FR18: Annotated screenshot in panel | Epic 3 |
| FR19: Confidence level display | Epic 2 |
| FR20: Thinking panel syncs per action | Epic 3 |
| FR21: Voice narration (text→Epic 3; audio→Epic 4) | Epic 3/4 |
| FR22: Full step plan + active step tracking | Epic 2 |
| FR23: Always-on VAD | Epic 4 |
| FR24: Voice barge-in mid-execution | Epic 4 |
| FR25: Re-listen after barge-in | Epic 4 |
| FR26: Plan adaptation after correction | Epic 4 |
| FR27: TTS voice response | Epic 4 |
| FR28: Destructive action detection | Epic 4 |
| FR29: Pause + confirmation before irreversible action | Epic 4 |
| FR30: Voice + visual confirmation simultaneously | Epic 4 |
| FR31: Proceed only on explicit approval | Epic 4 |
| FR32: Cancel and pause on decline | Epic 4 |
| FR33: Mid-task missing data request | Epic 3 |
| FR34: Per-step action record | Epic 3 |
| FR35: Per-step screenshot capture | Epic 3 |
| FR36: Audit log viewer | Epic 3 |
| FR37: Durable audit log persistence | Epic 3 |
| FR38: Cloud Run deployment | Epic 1 |
| FR39: Public URL (Firebase Hosting) | Epic 1 |
| FR40: Sandboxed browser | Epic 1/3 |
| FR41: Page load failure handling | Epic 3 |
| FR42: CAPTCHA pause + notify | Epic 3 |

---

## Epic List

### Epic 1: Project Foundation & Deployed Skeleton
Users can access a live deployed ARIA application at a real public URL, submit a text task, and receive confirmation it was received — all running on Cloud Run + Firebase Hosting with CI/CD green.
**FRs covered:** FR2, FR4, FR38, FR39, FR40 (scaffolded)

### Epic 2: Planner Agent + Live Thinking Panel
Users can type a task and watch ARIA decompose it into an ordered, live-updating step plan in the thinking panel — with confidence scores and stagger animation as steps stream in.
**FRs covered:** FR3, FR6, FR7, FR17, FR19, FR22

### Epic 3: Executor + Browser Automation + Audit Log
Users can assign a task via text and watch ARIA fully execute it in a live browser session — navigating, clicking, typing, filling forms — while the thinking panel updates in real time and the audit log fills with annotated screenshots.
**FRs covered:** FR5, FR8–FR16, FR18, FR20, FR21 (text narration), FR33, FR34–FR37, FR41, FR42

### Epic 4: Voice, Barge-in & Destructive Action Guard
Users can speak a task, hear ARIA narrate its actions, interrupt mid-execution with a word and have ARIA pause within 1 second, and receive voice + visual safety confirmations before any irreversible action.
**FRs covered:** FR1, FR21 (audio), FR23–FR32

---

## Epic 1: Project Foundation & Deployed Skeleton

Users can access a live deployed ARIA application at a real public URL, submit a text task, and receive confirmation it was received — all running on Cloud Run + Firebase Hosting with CI/CD green. No AI yet — but real infrastructure that deploys and functions.

### Story 1.1: Backend Scaffold with Playwright Docker Image

As a developer,
I want a Python ADK backend project scaffolded with the correct Playwright Docker image and project structure,
So that the backend can be built, containerized, and deployed to Cloud Run from day one.

**Acceptance Criteria:**

**Given** an empty `aria-backend/` directory,
**When** the ADK scaffold is initialized with `adk new aria-backend` and the Dockerfile is configured,
**Then** the project contains `agents/`, `main.py` (FastAPI entrypoint), `pyproject.toml`, `requirements.txt`, and a `Dockerfile` using `mcr.microsoft.com/playwright:v1.50.0-jammy` as the base image.

**Given** the Dockerfile is built,
**When** `docker build` runs,
**Then** the build completes successfully with Python 3.11+, ADK v1.25+, and Playwright Chromium installed.

**Given** the container is started locally,
**When** a `GET /healthz` request is made,
**Then** the response is `200 OK` with `{"status": "ok"}`.

**Given** the container configuration,
**When** Playwright launches Chromium,
**Then** it uses `--no-sandbox` and `--disable-dev-shm-usage` flags and does not crash.

---

### Story 1.2: Frontend Scaffold with Dark Theme and Design Tokens

As a developer,
I want a Next.js 16 frontend project scaffolded with TypeScript, Tailwind, shadcn/ui, and ARIA's dark design tokens configured,
So that all future UI work builds on the correct foundation without retrofitting styles.

**Acceptance Criteria:**

**Given** an empty `aria-frontend/` directory,
**When** `npx create-next-app@latest` runs with TypeScript, App Router, Tailwind, ESLint, and Turbopack (stable default in Next.js 16),
**Then** the project starts successfully with `npm run dev` and displays the default Next.js page at `localhost:3000`.

**Given** the project is initialized,
**When** shadcn/ui is initialized with `npx shadcn@latest init` using the dark theme,
**Then** `components/ui/` exists and `globals.css` contains the shadcn CSS variable definitions.

**Given** the Tailwind config is extended,
**When** the ARIA semantic color tokens are added (`--color-step-active: #3B82F6`, `--color-confidence-high: #10B981`, `--color-confidence-mid: #F59E0B`, `--color-confidence-low: #F43F5E`, `--color-surface: #18181B`, `--color-surface-raised: #27272A`, `--color-border: #3F3F46`, signal-pause `#A78BFA`),
**Then** these tokens are usable as Tailwind utility classes (e.g., `bg-[var(--color-surface)]`).

**Given** Geist fonts are configured in `layout.tsx`,
**When** any page renders,
**Then** body text uses Geist Sans and monospace text uses Geist Mono.

**Given** the app shell layout,
**When** the root page loads,
**Then** the background is `zinc-950`, the minimum viewport warning appears below 1280px, and no default Next.js branding is visible.

---

### Story 1.3: GCP and Firebase Infrastructure Provisioning

As a developer,
I want all required GCP and Firebase services provisioned and environment variables documented,
So that the backend can connect to Cloud Run, Firestore, GCS, and Firebase Hosting without manual setup per developer.

**Acceptance Criteria:**

**Given** a GCP project is selected,
**When** the provisioning steps are followed,
**Then** a Cloud Run service placeholder exists in `us-central1`, a GCS bucket named per `GCS_BUCKET_NAME` env var exists, and Google Secret Manager contains `GEMINI_API_KEY`.

**Given** Firebase is configured for the project,
**When** setup is complete,
**Then** a Firestore database exists in Native mode, Firebase Hosting is initialized for `aria-frontend`, and Firebase Anonymous Auth is enabled.

**Given** a `.env.local` file in `aria-frontend/` and a `.env` file in `aria-backend/`,
**When** both apps start locally,
**Then** they read `GEMINI_API_KEY`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `GCS_BUCKET_NAME`, and `CORS_ORIGIN` from their respective env files without error.

**Given** the Firestore security rules,
**When** rules are deployed,
**Then** session documents in the `sessions` collection are read/write only by the authenticated uid that owns the document (Firebase Anonymous Auth).

---

### Story 1.4: Firebase Anonymous Auth and Session Start API

As a user,
I want the application to silently authenticate me and create a session when I arrive,
So that my task data is isolated to my session without requiring me to sign up or log in.

**Acceptance Criteria:**

**Given** a user opens the ARIA frontend,
**When** the page loads,
**Then** Firebase `signInAnonymously()` is called automatically, a uid is obtained, and a JWT `idToken` is stored in the Zustand session slice.

**Given** a valid `idToken` is available,
**When** `POST /api/task/start` is called with `{"task_description": "test task"}` and `Authorization: Bearer {idToken}`,
**Then** the backend verifies the Firebase ID token, creates a Firestore document in `sessions/{session_id}` scoped to the uid, and returns `{"success": true, "data": {"session_id": "sess_{uuid4}", "stream_url": "/api/stream/{session_id}"}}`.

**Given** `POST /api/task/start` is called without a valid token,
**When** the request is received,
**Then** the response is `401 Unauthorized` with `{"success": false, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}}`.

**Given** a session is created,
**When** the Firestore document is inspected,
**Then** it contains `session_id`, `uid`, `created_at` (ISO 8601), `task_description`, and `status: "pending"`.

---

### Story 1.5: Task Input UI and Session Start Flow

As a user,
I want to type a task into the ARIA interface and see it submitted with visual confirmation,
So that I can initiate a session and know the system received my request.

**Acceptance Criteria:**

**Given** the ARIA home page loads,
**When** the UI renders,
**Then** a task input textarea is visible, keyboard-focusable, with placeholder text "Describe a task for ARIA...", and a "Start Task" button is visible and enabled.

**Given** the user types a task and clicks "Start Task",
**When** the form is submitted,
**Then** `POST /api/task/start` is called with the task description, the button shows a loading state, and the Zustand `sessionSlice` is updated with the returned `session_id`.

**Given** a successful API response,
**When** `session_id` is received,
**Then** the UI transitions out of the input state and the task description is displayed in a "task confirmed" banner with the text ARIA interpreted.

**Given** the API call fails,
**When** the error response is received,
**Then** the error message is displayed below the input field, the button returns to enabled state, and no session transition occurs.

**Given** a task is in progress (`status` is not `pending`),
**When** a new "Start Task" is clicked,
**Then** the existing session is preserved and a confirmation prompt asks "Cancel current task and start a new one?"

---

### Story 1.6: CI/CD Pipeline with Cloud Run and Firebase Hosting Deployment

As a developer,
I want GitHub Actions to automatically deploy the backend to Cloud Run and the frontend to Firebase Hosting on every push to `main`,
So that every merge produces a live, verifiable cloud deployment without manual steps.

**Acceptance Criteria:**

**Given** a push is made to the `main` branch,
**When** the GitHub Actions workflow triggers,
**Then** the `deploy-backend` job builds the Docker image, pushes it to Google Artifact Registry, and deploys it to Cloud Run with `--min-instances 1`, `--concurrency 1`, `--memory 4Gi`, and all required env vars from Secret Manager.

**Given** the backend deploys successfully,
**When** `GET https://{cloud_run_url}/healthz` is called,
**Then** the response is `200 OK`, confirming the deployment is live and warm.

**Given** a push is made to `main`,
**When** the `deploy-frontend` job runs,
**Then** `npm run build` succeeds, the output is deployed to Firebase Hosting, and the public URL returns the ARIA UI with HTTP 200.

**Given** the Cloud Run service is deployed,
**When** CORS headers are inspected from a request originating from the Firebase Hosting URL,
**Then** `Access-Control-Allow-Origin` matches exactly the Firebase Hosting URL (no wildcard).

**Given** any deployment job fails,
**When** the GitHub Actions run completes,
**Then** the run is marked as failed, no partial deployment is live, and the previous successful deployment remains active.

---

## Epic 2: Planner Agent + Live Thinking Panel

Users can type a task and watch ARIA decompose it into an ordered, live-updating step plan in the thinking panel — with confidence scores and stagger animation as steps stream in. The Planner reasons before anything happens in the browser.

### Story 2.1: Planner Agent with Canonical Step Plan Output

As a user,
I want ARIA to analyze my task and produce a structured, human-readable step plan before doing anything,
So that I can see what ARIA intends to do and trust it before execution begins.

**Acceptance Criteria:**

**Given** a task description is received by the backend,
**When** the Planner agent (`gemini-3-1-pro`) is invoked,
**Then** it returns a JSON object matching the canonical schema: `task_summary` (string), `steps` (array of `{step_index, action_type, description, target_element, expected_outcome, confidence, is_destructive}`), with all required fields present.

**Given** the Planner produces a step plan,
**When** `confidence` values are assigned,
**Then** each step's confidence is a float between 0.0 and 1.0, and any step with `confidence < 0.5` has a non-empty `description` explaining the uncertainty.

**Given** a task that includes a form submission or purchase,
**When** the Planner evaluates each step,
**Then** any step that submits a form, deletes a record, makes a purchase, or publishes content has `is_destructive: true`.

**Given** the Planner is invoked with a supplementary context payload (FR3),
**When** the context string is provided alongside the task description,
**Then** the Planner incorporates the context into its step plan (e.g., uses field values from the context).

**Given** the page content is passed to the Planner,
**When** it is included in the model context,
**Then** it is wrapped in a `<page_content>` XML tag and the system prompt explicitly instructs the model to treat it as untrusted data.

---

### Story 2.2: SSE Stream Endpoint for Agent Events

As the frontend,
I want to subscribe to a Server-Sent Events stream for a session and receive structured agent events in real time,
So that the thinking panel can update immediately as the Planner and Executor produce output.

**Acceptance Criteria:**

**Given** a valid `session_id` exists,
**When** `GET /api/stream/{session_id}` is requested with `Accept: text/event-stream`,
**Then** the response has `Content-Type: text/event-stream`, `Cache-Control: no-cache`, and the connection stays open.

**Given** the Planner completes a step plan,
**When** the plan is ready,
**Then** a `plan_ready` SSE event is emitted with `payload: {steps: [...]}` containing the full canonical step plan within 500ms of Planner completion.

**Given** an SSE event is emitted,
**When** the frontend `EventSource` receives it,
**Then** the event data is a valid JSON object matching the canonical envelope: `{event_type, session_id, timestamp, payload}`.

**Given** an SSE connection drops (client disconnects),
**When** the frontend reconnects with the same `session_id`,
**Then** the backend accepts the new connection and resumes streaming from the current task state.

**Given** `GET /api/stream/{session_id}` is called with an unknown `session_id`,
**When** the request is processed,
**Then** the response is `404 Not Found` with the canonical error envelope.

---

### Story 2.3: Frontend SSE Consumer and Thinking Panel State

As a developer,
I want the frontend to consume SSE events and update Zustand state,
So that all thinking panel components react to live agent events without prop drilling.

**Acceptance Criteria:**

**Given** a `session_id` is available in Zustand `sessionSlice`,
**When** the session transitions to `status: "planning"`,
**Then** an `EventSource` is opened to `/api/stream/{session_id}` and its `onmessage` handler dispatches events to the Zustand `thinkingPanelSlice`.

**Given** a `plan_ready` SSE event is received,
**When** the `thinkingPanelSlice` processes it,
**Then** `steps` is populated with the full step array, `status` transitions to `"plan_ready"`, and each step has `status: "pending"`.

**Given** the SSE connection drops,
**When** the `EventSource` `onerror` handler fires,
**Then** the frontend attempts reconnection automatically up to 5 times with 1-second backoff before surfacing a connection error in the UI (NFR16).

**Given** a `task_failed` SSE event is received,
**When** the `thinkingPanelSlice` processes it,
**Then** `taskStatus` transitions to `"failed"` and `error.message` is populated for display — no silent failures.

**Given** a new session starts,
**When** the Zustand store is reset,
**Then** all three slices (session, voice, thinkingPanel) are reset to their initial states before the new session's events begin populating them.

---

### Story 2.4: ThinkingPanel, StepItem, and ConfidenceBadge Components

As a user,
I want to see the step plan displayed as a visually scannable list with confidence indicators,
So that I can follow what ARIA plans to do at a glance without reading dense text.

**Acceptance Criteria:**

**Given** the `thinkingPanelSlice` has a non-empty `steps` array,
**When** `ThinkingPanel` renders,
**Then** it displays one `StepItem` per step in order, inside a `ScrollArea`, with the panel background `bg-surface` (`zinc-900`).

**Given** a `StepItem` renders,
**When** it displays a step,
**Then** it shows: step index number, action description in Geist Mono, a status icon (pending: gray dot, active: blue pulse, complete: emerald checkmark, error: rose X), and a `ConfidenceBadge`.

**Given** a `ConfidenceBadge` renders with a confidence value,
**When** `confidence >= 0.8`,
**Then** it displays an emerald pill labeled "High"; when `0.5 <= confidence < 0.8` it displays an amber pill labeled "Med"; when `confidence < 0.5` it displays a rose pill labeled "Low".

**Given** a step has `status: "active"`,
**When** the `StepItem` renders,
**Then** the card background is `bg-raised` (`zinc-800`), a blue left border accent is visible, and the status icon pulses at 1Hz.

**Given** all step items are rendered,
**When** the number of steps exceeds the panel height,
**Then** the `ScrollArea` enables vertical scrolling and automatically scrolls to keep the active step in view.

---

### Story 2.5: Task Interpretation Display and Stagger Animation

As a user,
I want to see ARIA confirm what it understood my task to be, and watch the step plan appear with a smooth animation,
So that I feel reassured before execution begins and can verify ARIA understood me correctly.

**Acceptance Criteria:**

**Given** a `plan_ready` SSE event is received,
**When** the `ThinkingPanel` transitions from "Planning..." to displaying steps,
**Then** each `StepItem` appears with a 60ms stagger delay (step 1 at 0ms, step 2 at 60ms, step 3 at 120ms, etc.) using a fade-in + slide-up CSS animation.

**Given** the `task_summary` field from the Planner step plan is available,
**When** the thinking panel renders,
**Then** a "Task understood:" label followed by `task_summary` text appears above the step list in `text-secondary` color before any steps begin executing.

**Given** `status` is `"planning"` (Planner running but no steps yet),
**When** the thinking panel renders,
**Then** a "Planning..." state with a subtle pulse animation on the panel header is shown — no empty or broken state.

**Given** all steps in the plan are `status: "complete"`,
**When** the final step completes,
**Then** the thinking panel header updates to "Done" in emerald color and the pulse animation stops.

---

## Epic 3: Executor + Browser Automation + Audit Log

Users can assign a task via text and watch ARIA fully execute it in a live browser session — navigating, clicking, typing, filling forms — while the thinking panel updates in real time and the audit log fills with annotated screenshots. This is the complete text-driven ARIA loop.

### Story 3.1: Executor Agent with ADK SequentialAgent Wiring

As a developer,
I want the Executor agent wired into ADK as a SequentialAgent after the Planner, using gemini-3-flash with ComputerUseToolset,
So that the Planner's step plan flows directly into the Executor's action loop without manual orchestration.

**Acceptance Criteria:**

**Given** a Planner step plan is produced,
**When** the ADK `SequentialAgent` runs,
**Then** the Executor agent receives the full step plan as its input context and begins executing from step 1.

**Given** the Executor agent is initialized,
**When** it is configured,
**Then** it uses `gemini-3-flash` as its model, `ComputerUseToolset` is attached, and its system prompt instructs it to execute one step at a time and check the cancel flag before and after every `await` call.

**Given** the Executor context window,
**When** it is assembled for each step,
**Then** it contains: system prompt + full step plan + last 3 completed step results + current screenshot. Steps older than the last 3 are summarized into a `completed_steps_summary` string.

**Given** the ADK SequentialAgent runs to completion,
**When** all steps are complete,
**Then** a `task_complete` SSE event is emitted with `payload: {steps_completed: N, session_id}` and Firestore `sessions/{session_id}.status` is updated to `"complete"`.

---

### Story 3.2: Playwright Browser Actions

As a user,
I want ARIA to navigate, click, type, scroll, and read web pages in a real browser,
So that it can perform any web task on my behalf.

**Acceptance Criteria:**

**Given** the Executor receives a step with `action_type: "navigate"`,
**When** it executes the step,
**Then** Playwright navigates to the specified URL and waits for `networkidle` (max 15s timeout) before marking the step complete (FR8, FR15).

**Given** the Executor receives a step with `action_type: "click"`,
**When** it executes the step,
**Then** Playwright locates the target element using the bounding box from the Computer Use screenshot interpretation and performs a click; if the element is not found, the step enters retry logic (FR9, FR14).

**Given** the Executor receives a step with `action_type: "type"`,
**When** it executes the step,
**Then** Playwright types the specified text into the targeted input field character by character with a 30ms delay to avoid triggering bot detection (FR10).

**Given** the Executor receives a step with `action_type: "scroll"`,
**When** it executes the step,
**Then** Playwright scrolls the page by the specified pixel delta in the specified direction (FR11).

**Given** the Executor receives a step with `action_type: "read"`,
**When** it executes the step,
**Then** Playwright extracts visible text content from the specified selector or full page and returns it as the step result (FR13).

**Given** any Playwright action throws an error,
**When** the error is caught,
**Then** the Executor re-takes a screenshot, re-evaluates the page state, and retries the action. After 2 retries, it emits a `step_error` SSE event with the error description and pauses for user input (FR16).

---

### Story 3.3: Screenshot Capture, GCS Upload, and Step SSE Events

As a user,
I want each Executor action to emit a real-time event to my thinking panel and capture a screenshot stored in GCS,
So that I can follow along live and have a complete visual record of every action taken.

**Acceptance Criteria:**

**Given** the Executor begins a step,
**When** the step starts,
**Then** a `step_start` SSE event is emitted within 500ms with `payload: {step_index, action_type, description, confidence}` (NFR4).

**Given** a step completes,
**When** the step result is available,
**Then** a full-page screenshot is taken, uploaded to GCS at `sessions/{session_id}/steps/{step_index:04d}.png`, and a `step_complete` SSE event is emitted with `payload: {step_index, screenshot_url, result_summary, confidence}`.

**Given** a screenshot is uploaded to GCS,
**When** the `screenshot_url` is received by the frontend,
**Then** it renders in the active `StepItem` as a thumbnail in `ScreenshotViewer` within 300ms of receipt (NFR5).

**Given** a `step_error` SSE event is received,
**When** the thinking panel processes it,
**Then** the affected `StepItem` shows a rose error icon, the error description is displayed, and execution is paused awaiting user input.

**Given** a `step_start` SSE event updates the active step,
**When** the thinking panel renders,
**Then** the previously active step transitions to `status: "complete"` (or `"error"`) and the new step transitions to `status: "active"` with the blue pulse animation.

---

### Story 3.4: Error Handling, Page Load Timeouts, and CAPTCHA Pause

As a user,
I want ARIA to handle browser errors gracefully — page timeouts, navigation failures, and CAPTCHAs — without crashing my session,
So that I can intervene and continue rather than having to restart from scratch.

**Acceptance Criteria:**

**Given** a page navigation times out after 15 seconds,
**When** the timeout fires,
**Then** the Executor emits a `step_error` SSE event with description "Page did not load within 15 seconds", updates Firestore with the error, and pauses execution without crashing the session (FR41, NFR14).

**Given** a Gemini API rate limit or transient error occurs,
**When** the error is caught,
**Then** the backend retries the API call up to 2 times with 1-second backoff. If all retries fail, a `task_failed` SSE event is emitted with the error details (NFR15).

**Given** the Computer Use model detects a CAPTCHA element on the page,
**When** ARIA identifies it cannot proceed,
**Then** execution pauses, an `awaiting_input` SSE event is emitted with `payload: {reason: "captcha_detected", message: "CAPTCHA encountered — manual intervention required"}`, and the thinking panel displays the message (FR42).

**Given** a `step_error` or `awaiting_input` state is active,
**When** the user sends a `POST /api/task/{session_id}/input` with instructions,
**Then** the Executor receives the input, re-evaluates the page state, and resumes execution from the current step.

---

### Story 3.5: Firestore Audit Log Writer and Mid-Task Input Request

As a user,
I want every action ARIA takes to be recorded in a durable audit log, and to be prompted when ARIA needs information I haven't provided,
So that I have a complete record of what happened and ARIA can handle tasks that require my input mid-execution.

**Acceptance Criteria:**

**Given** a step completes,
**When** `step_complete` is processed,
**Then** the Firestore document `sessions/{session_id}` is updated: a new entry is appended to the `steps` array with `step_index`, `action_type`, `description`, `result`, `screenshot_url`, `confidence`, `timestamp` (ISO 8601), and `status: "complete"` (FR34, FR35).

**Given** the Executor encounters a step requiring data it cannot infer (e.g., a file path, a password, a specific value),
**When** the missing data is identified,
**Then** the Executor emits an `awaiting_input` SSE event with `payload: {step_index, message: "I need [X] to continue — can you provide it?"}` and pauses execution (FR33).

**Given** an `awaiting_input` event is received by the frontend,
**When** it is processed,
**Then** the UI displays an inline input request in the thinking panel with the message text and a text input field for the user's response.

**Given** the user submits input via `POST /api/task/{session_id}/input`,
**When** the backend receives it,
**Then** the Executor resumes execution incorporating the provided value, and the `awaiting_input` step is resolved in the thinking panel.

**Given** a browser refresh occurs mid-session,
**When** the page reloads,
**Then** the Firestore `onSnapshot` subscription reconnects to `sessions/{session_id}` and the audit log renders all previously completed steps from Firestore — no data is lost (FR37).

---

### Story 3.6: Audit Log Viewer UI and Task Cancel

As a user,
I want to view a complete audit log of all actions after my task completes, and to be able to cancel an in-progress task,
So that I have a professional record I can reference or share, and I am never trapped in a running session.

**Acceptance Criteria:**

**Given** a task is `status: "complete"` or `"failed"`,
**When** the audit log section renders,
**Then** all steps are displayed in chronological order, each showing: step number, action type badge, description, timestamp, confidence badge, and a thumbnail of the associated screenshot (FR36).

**Given** a screenshot thumbnail in the audit log is clicked,
**When** it is interacted with,
**Then** the `ScreenshotViewer` component opens in a modal showing the full-resolution screenshot with any bounding box annotations overlaid.

**Given** the Firestore `onSnapshot` subscription is active during execution,
**When** new steps are written to Firestore,
**Then** the audit log UI updates in real time without page reload — new entries appear at the bottom within 1 second of the action completing.

**Given** a task is in progress,
**When** the user clicks the "Cancel Task" button or selects cancel from the task controls,
**Then** `POST /api/task/{session_id}/interrupt` is called, the backend sets the asyncio cancel flag, the Executor stops after the current action, a `task_failed` SSE event with `reason: "user_cancelled"` is emitted, and the session `status` is updated to `"cancelled"` in Firestore (FR5).

**Given** a "Cancel Task" action completes,
**When** the UI receives the `task_failed` event,
**Then** the task input area resets to allow a new task to be started, and the partial audit log remains visible.

---

## Epic 4: Voice, Barge-in & Destructive Action Guard

Users can speak a task, hear ARIA narrate its actions aloud, interrupt mid-execution with a single word and have ARIA pause within 1 second, and receive simultaneous voice + visual safety confirmations before any irreversible action. This is the complete ARIA experience and the hackathon demo.

### Story 4.1: WebSocket Audio Relay Backend

As a developer,
I want a WebSocket endpoint that relays raw PCM audio between the browser and gemini-3-flash in real time,
So that the voice pipeline has a low-latency bidirectional audio channel with no buffering in the hot path.

**Acceptance Criteria:**

**Given** a `session_id` exists,
**When** a WebSocket client connects to `/ws/audio/{session_id}`,
**Then** the connection is accepted, an `asyncio.Queue` is created for inbound audio chunks, and the relay coroutines start.

**Given** the WebSocket relay is running,
**When** the browser sends raw PCM audio chunks (16kHz, 16-bit, mono),
**Then** the chunks are placed onto the inbound queue and forwarded to `gemini-3-flash` without JSON parsing, logging, or inspection in the relay path — pure pass-through (architecture audio relay queue pattern).

**Given** `gemini-3-flash` produces audio output (TTS narration),
**When** audio bytes are received from the model,
**Then** they are immediately forwarded to the connected WebSocket client without buffering.

**Given** the Gemini Live API round-trip,
**When** measured end-to-end in streaming mode,
**Then** the latency is 1–1.8 seconds from audio sent to first audio byte received back (NFR3).

**Given** the WebSocket connection drops unexpectedly,
**When** the disconnect is detected,
**Then** the relay coroutines are cancelled cleanly, the asyncio resources for that session are released, and the session state in Zustand is updated to `voiceStatus: "disconnected"`.

---

### Story 4.2: Browser Audio Capture and Web Audio Playback

As a user,
I want my microphone audio to stream to ARIA in real time and hear ARIA's voice responses through my speakers,
So that the voice interaction feels natural and continuous without any push-to-talk.

**Acceptance Criteria:**

**Given** a session is active and the user has not yet connected audio,
**When** the voice panel renders,
**Then** a "Connect Microphone" button is visible and an "Always listening" label is present below the `VoiceWaveform` component.

**Given** the user grants microphone permission and the session is active,
**When** the voice connection is established,
**Then** `MediaRecorder` captures audio at 16kHz, 16-bit, mono, and chunks are streamed over the WebSocket to `/ws/audio/{session_id}` in real time with no buffering delay.

**Given** audio bytes are received from the WebSocket (ARIA's TTS narration),
**When** bytes arrive,
**Then** they are passed to the Web Audio API for playback, beginning within 200ms of the first byte received (NFR3 contribution).

**Given** the user's browser does not support `MediaRecorder` or `WebSocket`,
**When** the voice panel renders,
**Then** a fallback message is displayed: "Voice input requires Chrome 120+ or Edge 120+" and only the text input is available.

**Given** the microphone stream is active,
**When** the user speaks,
**Then** the `VoiceWaveform` amplitude bars animate in response to the audio signal within 50ms of speech onset.

---

### Story 4.3: VoiceWaveform, BargeInPulse Components, and VAD Visual States

As a user,
I want clear, always-visible visual feedback about ARIA's voice state at all times,
So that I always know whether ARIA is listening, speaking, executing, or paused — and can interrupt confidently.

**Acceptance Criteria:**

**Given** the session is active,
**When** the `VoiceWaveform` component renders,
**Then** it is permanently visible in the left sidebar of the layout (not in a modal or overlay) with an "Always listening" label.

**Given** ARIA is in `voiceStatus: "listening"` state,
**When** the `VoiceWaveform` renders,
**Then** the amplitude bars are blue (`signal-active: #3B82F6`) and animate at low amplitude to indicate ambient listening.

**Given** ARIA is in `voiceStatus: "speaking"` state (TTS playing),
**When** the `VoiceWaveform` renders,
**Then** the bars animate at higher amplitude in emerald (`signal-success: #10B981`) to visually differentiate ARIA speaking from listening.

**Given** ARIA is in `voiceStatus: "paused"` state (barge-in active),
**When** the `VoiceWaveform` renders,
**Then** the bars are violet (`signal-pause: #A78BFA`) and the `BargeInPulse` ripple animation plays — distinct from all other states.

**Given** VAD detects speech onset from the user,
**When** the detection fires,
**Then** the `BargeInPulse` animation triggers within 200ms — before any backend processing completes — confirming to the user they were heard (NFR: 200ms visual acknowledgment per UX spec).

**Given** the `voiceStatus` transitions between any states,
**When** the transition occurs,
**Then** the waveform color and animation update within one animation frame (16ms) with no flash or broken intermediate state.

---

### Story 4.4: Voice Barge-in — Execution Halt and Plan Adaptation

As a user,
I want to be able to say "wait" or "stop" at any point during execution and have ARIA pause within 1 second and ask what I want to do next,
So that I am never trapped watching ARIA do the wrong thing.

**Acceptance Criteria:**

**Given** the Executor is actively running steps and the WebSocket audio relay is active,
**When** VAD detects user speech mid-execution,
**Then** `signal_barge_in(session_id)` is called in `session_service.py`, setting the `asyncio.Event` cancel flag for that session.

**Given** the cancel flag is set,
**When** the Executor checks `cancel_flag.is_set()` before or after any Playwright `await` call,
**Then** it raises `BargeInException`, stops execution immediately after the current Playwright action completes (not mid-action), and emits a `step_error` SSE event with `reason: "barge_in"`.

**Given** `BargeInException` is caught by the step loop,
**When** the exception is handled,
**Then** a `task_paused` SSE event is emitted with `payload: {paused_at_step: N}`, the cancel flag is reset via `reset_cancel_flag(session_id)`, and the Gemini Live audio session re-enters listening mode.

**Given** a `task_paused` SSE event is received by the frontend,
**When** the thinking panel processes it,
**Then** the active step shows "⏸ Paused — listening" in violet, and the `VoiceWaveform` transitions to `voiceStatus: "paused"`.

**Given** ARIA re-listens and the user provides a new instruction,
**When** the instruction is received via the audio WebSocket,
**Then** `gemini-3-flash` produces a revised step plan incorporating the new instruction and the current browser state, a new `plan_ready` SSE event is emitted, and execution resumes from the current browser state — no page reload, no session restart (FR26).

**Given** the full barge-in flow is timed,
**When** the user utterance begins,
**Then** Executor halts within 1 second of the utterance start (NFR2).

---

### Story 4.5: Destructive Action Guard — Voice and Visual Confirmation

As a user,
I want ARIA to always pause and ask for my explicit confirmation — both spoken aloud and shown on screen — before it submits a form, makes a purchase, deletes a record, or publishes content,
So that I am never surprised by an irreversible action I didn't intend.

**Acceptance Criteria:**

**Given** the Executor reaches a step where `is_destructive: true`,
**When** it evaluates the step before executing,
**Then** it does NOT execute the action and instead emits an `awaiting_confirmation` SSE event with `payload: {step_index, action_description, warning: "This action cannot be undone"}`.

**Given** an `awaiting_confirmation` SSE event is received,
**When** the frontend processes it,
**Then** a confirmation dialog is displayed over the thinking panel with the action description, a warning banner in rose (`signal-danger`), a "Confirm" button, and a "Cancel" button — all keyboard-accessible (NFR19).

**Given** the confirmation dialog is shown,
**When** it renders,
**Then** ARIA simultaneously speaks aloud via TTS: "I'm about to [action description]. This action cannot be undone — shall I proceed?" — voice and visual confirmation fire within 500ms of each other (FR30).

**Given** the confirmation dialog is displayed,
**When** the user says "yes" / "confirm" / "proceed" audibly,
**Then** VAD captures the affirmation, `POST /api/task/{session_id}/confirm` is called with `{"confirmed": true}`, the dialog dismisses, and the Executor proceeds with the action (FR31).

**Given** the confirmation dialog is displayed,
**When** the user says "no" / "cancel" / "stop" or clicks "Cancel",
**Then** `POST /api/task/{session_id}/confirm` is called with `{"confirmed": false}`, the dialog dismisses, a `task_paused` SSE event is emitted, and execution halts in a state where the user can provide a new direction (FR32).

**Given** the confirmation dialog is displayed,
**When** 60 seconds pass with no response,
**Then** the action is automatically cancelled (safe default) and a `task_paused` SSE event is emitted — ARIA never proceeds on timeout (FR32 safe default).

**Given** the destructive action detection is tested across all demo scenarios,
**When** form submissions, purchases, deletions, and publish actions are executed,
**Then** 100% are detected and guarded — zero silent destructive actions occur (NFR: 100% detection rate).

