# Non-Functional Requirements

### Performance

All performance targets are the threshold for demo viability — below these, the user experience breaks down visibly:

| Requirement | Target | Rationale |
|---|---|---|
| Voice-to-first-browser-action latency | < 3 seconds | End-to-end from utterance start to first Executor action |
| Barge-in interruption response | < 1 second | From utterance of "stop/wait" to ARIA halting execution |
| Gemini Live API voice round-trip | 1–1.8 seconds | Streaming mode only; buffered mode (3s+) is unacceptable |
| Thinking panel → Executor sync lag | < 500ms | Panel steps must reflect Executor actions in near-real-time |
| Screenshot render in thinking panel | < 300ms after receipt | Annotated screenshots must feel live, not delayed |
| First Contentful Paint (frontend) | < 2 seconds | Application load time before user can begin |

### Security

ARIA's threat surface is specific: a cloud-hosted agent with a live browser and access to arbitrary web pages.

- The Executor browser session runs in a sandboxed Chromium instance — it must not have access to the host Cloud Run container's filesystem or environment variables
- Gemini API keys and GCP credentials must never be exposed to the frontend or included in client-side code; all model calls originate server-side
- Page content ingested by the Planner must be treated as untrusted input — system prompt boundaries must prevent prompt injection from malicious page text from overriding ARIA's task instructions
- The backend must not exfiltrate page content or screenshots to any destination other than the session's Firestore audit log
- Screenshot and session data in Firestore/GCS must be scoped to the active session only

### Reliability

Demo reliability is the highest-priority non-functional concern — a crash during the demo recording is an unrecoverable failure:

- The ARIA backend on Cloud Run must have `--min-instances 1` configured to eliminate cold start failures during the demo window
- The Playwright/Chromium session must complete a full demo run without crash across 10 consecutive test runs before submission
- ARIA must handle page load timeouts gracefully — if a page does not load within 15 seconds, ARIA reports the failure to the user without crashing the session
- ARIA must handle Gemini API rate limit errors or transient failures with a retry (max 2 retries) before surfacing an error to the user
- No single point of failure in the SSE thinking panel stream — if the stream connection drops, the frontend must attempt reconnection automatically

### Scalability

Hackathon scope only — single concurrent user session per deployment:

- The backend must support one active session reliably; multi-session concurrency is not required for MVP
- Cloud Run auto-scaling handles any burst beyond one session; no manual scaling configuration required beyond `--min-instances 1`

### Accessibility

Functional baseline only — no regulated requirement:

- All UI controls (task input, voice button, confirmation dialogs) must be keyboard-navigable
- Text content in the thinking panel must meet WCAG AA colour contrast ratio (4.5:1)
- Voice narration serves as the audio accessibility layer for the execution experience
