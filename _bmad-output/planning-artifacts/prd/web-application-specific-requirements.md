# Web Application Specific Requirements

### Project-Type Overview

ARIA's frontend is a single-page application (Next.js 15 + React) delivering a real-time interactive session interface. The application's primary UI surface is the live execution panel — a streaming view of the agent's reasoning, browser actions, and confidence states. The frontend is not content-driven; it is session-driven. All meaningful interaction happens within a single active task session.

### Technical Architecture Considerations

**Real-Time Communication (Critical Path)**

| Channel | Protocol | Direction | Purpose |
|---|---|---|---|
| Thinking panel stream | SSE (Server-Sent Events) | Backend → Frontend | Agent step updates, confidence scores, annotated screenshots |
| Voice audio | WebSocket | Bidirectional | User audio → Gemini Live API; agent narration → user speaker |
| Audit log updates | Firestore real-time subscription | Backend → Frontend | Live session record as steps complete |

SSE is preferred over WebSocket for the thinking panel (unidirectional, simpler, HTTP/2 compatible). WebSocket is required for voice (bidirectional audio stream).

**Browser Support**

- **Primary:** Chrome 120+, Edge 120+ (Chromium-based)
- **Required APIs:** MediaRecorder (audio capture), WebSocket, EventSource (SSE), Web Audio API
- **Secondary:** Firefox 120+ (best-effort)
- **Not supported:** Safari (MediaRecorder limitations for audio), IE/legacy browsers

**Performance Targets**

Frontend-specific: First Contentful Paint < 2s. All end-to-end latency targets (voice, barge-in, thinking panel sync) are defined in the Non-Functional Requirements — Performance section.

**Responsive Design**

Desktop-first. The thinking panel + browser view + audio controls layout requires horizontal space. Mobile is out of scope for MVP. Minimum supported viewport: 1280px wide.

**SEO Strategy**

Not applicable — ARIA is an authenticated application session interface, not a public content page.

### Implementation Considerations

- **Next.js 15 App Router** — used for routing and server components where applicable; client components for all real-time surfaces
- **Tailwind CSS + shadcn/ui** — component system for rapid development within hackathon timeline
- **Firebase Hosting** — static frontend deployment; connects to Cloud Run backend via HTTPS/WebSocket
- **No offline mode** — ARIA requires live connection to Cloud Run backend and Gemini APIs; offline is a non-starter
- **Audio pipeline:** Browser MediaRecorder → WebSocket → Python backend → Gemini Live API; response audio streamed back to browser Web Audio API
