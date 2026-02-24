# Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Demo-validation MVP — the smallest working system that delivers the complete interaction experience end-to-end, sufficient to prove the core thesis to hackathon judges and validate that the Gemini multimodal stack can deliver the interaction loop as designed.

**Constraint:** 21-day build window (Feb 23 – Mar 17, 2026), 2-person engineering team (Bahaa + Ahmed), intermediate GCP experience. Every scoping decision is made through the lens of demo reliability over feature breadth.

**Core philosophy:** One flawless demo flow beats ten half-working features. The MVP must demonstrate the voice-interruption moment reliably and repeatedly — everything else is secondary.

**Resource Requirements:** 2 engineers full-stack; Python (ADK backend), Next.js (frontend), GCP (Cloud Run, Firestore, GCS, Firebase Hosting). No additional team members, no external contractors.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:** All 6 personas are served by the same underlying capability — task assignment, live execution with thinking panel, voice barge-in, destructive action guard, audit log. The demo will showcase the universal journey pattern, not individual persona flows.

**Must-Have Capabilities:**

| Capability | Rationale |
|---|---|
| Voice task input via Gemini Live API | Core multimodal differentiator — required for 40% Innovation scoring |
| Text task input (fallback) | Demo resilience — voice-only is fragile in live recording conditions |
| Planner Agent (Gemini 3.1 Pro) | Visible reasoning layer — produces the step plan shown in thinking panel |
| Executor Agent (Gemini Computer Use + Playwright) | Browser action layer — the system must actually do things |
| Live thinking panel (SSE stream) | Primary UX differentiator — must update in real time, look compelling |
| Voice narration (Gemini Live API TTS) | Makes execution feel alive; silent execution misses the experience |
| Voice barge-in / mid-execution interruption | The single most important demo moment — must be sub-1s response |
| Destructive action guard (voice + visual) | Safety story; confirms trust-first design |
| Audit log — basic (Firestore + GCS) | GCP usage proof; enables session replay for submission |
| Cloud Run deployment (production) | Mandatory per hackathon rules; must be verifiable, not local |

### Post-MVP Features

**Phase 2 (Post-Hackathon, if ARIA continues):**
- Audit log export / auto-documentation formatting
- Proactive co-pilot mode (session memory + behavioral modeling)
- "Teach me" mode (record-and-replay automation)
- Playwright test script generation as execution side-effect
- Multi-tab / multi-window navigation handling
- Custom autonomy dial (user-configurable confidence threshold)

**Phase 3 (Future Vision):**
- Full desktop control beyond the browser
- Cross-session memory — ARIA learns user preferences and recurring tasks
- SOP ingestion — upload a procedure doc; ARIA executes it on any matching page
- API / headless mode for team workflow automation
- Mobile UI control

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Likelihood | Mitigation |
|---|---|---|
| Gemini Live API buffering adds >1s to barge-in | Medium | Use streaming mode exclusively; test and confirm latency before any other work |
| Playwright/Chromium instability in Cloud Run container | Medium | Use official `mcr.microsoft.com/playwright` Docker image; `--no-sandbox` + `--disable-dev-shm-usage` flags; 2–4GB RAM |
| ADK observability → SSE thinking panel sync lag | Low | Native OpenTelemetry events are synchronous with agent actions; no custom instrumentation needed |
| Cloud Run cold start disrupts demo | Medium | `--min-instances 1` set before demo recording; 10 warm-up test runs before submission |
| Computer Use model misidentifies dynamic UI elements | High | Hybrid approach: vision + DOM accessibility tree; re-screenshot and re-identify after each interaction |

**Deadline Risk:**

The 21-day window is tight for a novel multimodal system. Risk mitigation: implement the voice barge-in pipeline first (highest innovation value, highest risk), not last. If the Live API integration proves unstable, the fallback is text-only input — the demo still demonstrates the thinking panel and dual-agent architecture credibly.

**Demo Risk:**

Record multiple demo takes. Use a controlled, stable web page for demo (not a site with frequent UI changes). Have text input fallback visible and available. The audit log should be pre-populated from earlier test runs to demonstrate completeness.
