---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-gemini-hackathon-2026-02-23.md
  - _bmad-output/planning-artifacts/research/domain-agentic-ai-computer-use-ux-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/market-ui-navigator-agents-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/technical-aria-stack-research-2026-02-23.md
  - _bmad-output/brainstorming/brainstorming-session-2026-02-23.md
workflowType: 'prd'
date: 2026-02-23
author: Bahaa
classification:
  projectType: web_app
  domain: general
  complexity: high
  projectContext: greenfield
---

# Product Requirements Document - gemini-hackathon

**Author:** Bahaa
**Date:** 2026-02-23

## Executive Summary

ARIA (Adaptive Reasoning & Interaction Agent) is a voice-driven, multimodal UI navigator that executes web-based tasks on behalf of users while keeping them visibly in control throughout execution. Users assign tasks by speaking or typing; ARIA decomposes the task into a visible step plan, executes it in a live browser session using Gemini's Computer Use model, narrates its reasoning aloud, and accepts voice interruptions mid-action — allowing users to redirect without stopping and restarting. Before any irreversible action, ARIA surfaces a confirmation in both voice and UI. Every completed task generates a full audit log with annotated screenshots, replayable as undo history or step-by-step documentation.

ARIA is built on Google's full agentic stack: Gemini 3.1 Pro (Planner), Gemini 2.5 Computer Use (Executor), Gemini Live API with native VAD (voice streaming and barge-in), Google ADK (dual-agent orchestration and observability), Cloud Run, Firestore, and Firebase Hosting. It is entered in the **UI Navigator** category of the Google Gemini Live Agent Challenge, targeting the Grand Prize and Best of UI Navigators award.

### What Makes This Special

Every existing UI navigator — Atlas (OpenAI), Comet (Perplexity), browser-use, Skyvern, Manus (Meta) — was designed around execution. They assume the user's role ends at delegation. ARIA's core design bet is the opposite: **the user is always present, always able to redirect, and the system is always intelligible to them**. This is not a UX choice bolted on top of an automation engine — it is the product.

Three capabilities combine to make this real, none of which any competitor delivers:

1. **Voice interruption mid-execution** — Gemini Live API's native Voice Activity Detection enables true barge-in: users say "wait, wrong field" and ARIA pauses, re-listens, and adapts its plan in under 1 second. No buffering, no polling. This is only possible on this specific model stack.
2. **Live thinking panel** — ADK's native OpenTelemetry observability feeds a real-time reasoning panel showing what ARIA is looking at, what it plans to do next, and its confidence per step. Transparency is the steering mechanism — users decide whether to let ARIA continue or redirect based on what they see.
3. **Visible Planner + Executor architecture** — The dual-agent split (Gemini 3.1 Pro reasoning + Gemini Computer Use acting) is exposed to the user as the UX, not hidden as an implementation detail. Users experience an agent that *thinks before it acts*.

The core insight: users don't distrust AI agents because they lack capability. They distrust them because they can't see where the agent is heading and can't stop it in time. ARIA solves the visibility and control problem — and trust follows automatically. On 10 of 12 competitive dimensions, no existing product matches ARIA's capability set.

### Project Classification

| Dimension | Value |
|---|---|
| **Project Type** | Web application (Next.js frontend, Python/ADK backend, real-time SSE + WebSocket) |
| **Domain** | General productivity — AI-native, no regulated domain constraints |
| **Complexity** | High — novel multimodal AI stack, dual-agent architecture, real-time voice streaming, GCP multi-service integration, hackathon deadline |
| **Project Context** | Greenfield — new product, no existing system |

## Success Criteria

### User Success

- User completes a task by speaking a natural language instruction — no setup, no tutorial, no configuration required
- User observes ARIA's live thinking panel and can follow exactly what the agent is doing at each step
- User successfully interrupts ARIA mid-execution with voice ("wait", "stop") and ARIA pauses and adapts within 1 second
- User receives a voice + visual confirmation before any irreversible action (submit, delete, purchase) — zero silent destructive actions
- User can review the completed task audit log with annotated screenshots after execution

### Business Success

ARIA is scoped to the Google Gemini Live Agent Challenge hackathon (deadline: March 17, 2026). Business success is defined entirely by hackathon outcome:

| Judging Dimension | Weight | Success Threshold |
|---|---|---|
| Innovation & Multimodal UX | 40% | Voice-in → browser-action pipeline feels seamless; thinking panel is live and compelling; experience is context-aware, not turn-based |
| Technical Architecture | 30% | ADK dual-agent (Planner + Executor), Gemini Live API, verified Cloud Run deployment, Firestore audit log — all working and demonstrated |
| Demo & Presentation | 30% | Video shows real working software; architecture diagram is clear; Cloud deployment is proven; problem + solution in under 4 minutes |

**Primary target:** Grand Prize + Best of UI Navigators award.
**Definition of success:** A judge leans forward during the voice-interruption moment — that single scene validates all three judging dimensions simultaneously.

### Technical Success

- Full backend deployed and running on **Google Cloud Run** — not local, cloud deployment is mandatory and must be demonstrable
- Cloud Run configured with `--min-instances 1` — no cold start failures during demo recording
- Gemini Live API latency: target 1–1.8s round-trip (streaming mode, not buffered)
- Thinking panel sync: panel steps reflect Executor actions within 500ms
- Chromium stability: zero crashes during a complete demo run

### Measurable Outcomes

| Metric | Target |
|---|---|
| Task completion rate on demo scenarios | 100% — zero manual intervention |
| Destructive action detection accuracy | 100% — zero misses acceptable |
| Voice-to-first-browser-action latency | < 3 seconds end-to-end |
| Barge-in response time | < 1 second from utterance to ARIA pause |
| Gemini Live API round-trip | 1–1.8s (streaming mode) |
| Thinking panel → Executor sync lag | < 500ms |

## User Journeys

### Journey 1: Sara — The Operations Manager (Repetitive Professional Workflow)

Sara has been submitting the same vendor compliance form every month for two years. It's a 15-field portal with dropdowns, date fields, and an attachments section that always seems to move. She knows every field by memory — and that's exactly what makes it maddening. It's not hard. It's just slow, manual, and beneath her.

She opens ARIA and says: *"Fill out the monthly compliance form on the supplier portal. I'll give you the values as you go."*

ARIA opens the portal. The thinking panel activates — she can see it scanning the page, identifying fields, building a step plan. *"I can see 14 form fields. Here's what I'll do: I'll fill each field in order and pause before submitting."* It starts moving. Vendor name, filled. Category code, filled. She watches the panel update in real time.

On the attachments field, ARIA pauses: *"I need the certificate file path — I don't have that. Can you provide it?"* Sara uploads the file. ARIA continues.

When it reaches the Submit button, it stops: *"This will submit the form to the vendor portal. This action cannot be undone — shall I proceed?"* Sara says *"Yes, submit."* The form goes through.

She looks at the audit log — every field, every value, every screenshot, timestamped. Next month, she'll hand this to an intern with the log as the guide.

**Requirements revealed:** Voice task input, Planner step plan display, Executor form-filling, mid-task user input request, destructive action guard, audit log.

---

### Journey 2: James — The College Student (Research Aggregation)

James is comparing five hotels for a family trip. He has five tabs open and a blank Google Doc. He's been copying and pasting for 20 minutes. The prices don't line up, the amenity lists use different words, and he's lost track of which tab he's on.

He opens ARIA and says: *"Go through these 5 hotel pages and collect the nightly price, star rating, free breakfast availability, and pool availability into a list."*

ARIA starts on the first tab. The thinking panel shows it reading the page — *"I can see the price listed as $142/night in the booking summary section."* It moves through each page methodically, narrating what it finds. James watches, occasionally correcting: *"Wait, that's the weekend price — I need weekday."* ARIA pauses, re-reads the page, finds the weekday rate.

Five pages later, ARIA presents a clean comparison list in the chat panel. James copies it into his doc.

**Requirements revealed:** Voice task input, multi-step Executor navigation, live thinking panel, voice barge-in/correction mid-task, structured output display.

---

### Journey 3: Margaret — The Retired Teacher (Low-Tech Confidence, High-Stakes Form)

Margaret needs to complete her Medicare supplemental insurance application online. The form is long, the language is bureaucratic, and she's already made one mistake that required starting over. Her daughter set up ARIA for her.

She clicks the microphone and says slowly: *"Help me fill in my Medicare insurance application on this site."*

ARIA responds warmly in voice: *"I can see the application. It has 8 sections. I'll go through them one by one and ask you for each piece of information I need."* The thinking panel shows each section as ARIA reaches it. Margaret can see exactly where they are in the form.

ARIA reads each field aloud and waits for her answer. When it reaches a field it can infer from context — her name, already shown on the page header — it fills it automatically and narrates: *"I've filled in your name from the page — does that look right?"*

Before submitting: *"I'm about to submit your application. Once submitted, this cannot be changed. Shall I go ahead?"* Margaret says *"Yes please."*

She feels none of the anxiety she had before. The audit log shows her exactly what was submitted — she screenshots it for her records.

**Requirements revealed:** Voice task input, voice narration throughout, conversational mid-task data collection, destructive action guard with voice confirmation, audit log.

---

### Journey 4: Ravi — The Startup Founder (QA / Power User)

Ravi is 2 hours from a product launch. He needs to walk through the entire checkout flow — add to cart, enter shipping, apply a promo code, confirm payment — and verify every step works on the staging environment. His QA person is sick. He's doing it himself.

He opens ARIA and types: *"Go through my checkout flow at staging.myapp.com. Add the item called 'Pro Plan', use the test promo code LAUNCH20, enter shipping address [X], and verify the order confirmation page shows the correct discounted total."*

ARIA starts. The thinking panel shows it navigating each step, highlighting the element it's about to interact with. It applies the promo code — and the thinking panel shows: *"Confidence low — the discount field shows $0 instead of the expected 20% reduction. This may be a bug."* It pauses and flags the issue to Ravi.

Ravi leans in: *"Good catch. Stop there."* He fixes the promo code logic in his codebase, restarts staging, and runs ARIA again. This time it completes cleanly.

The audit log is a complete record of both runs — screenshots, steps, the flagged anomaly. He pastes the second run into the launch ticket as QA evidence.

**Requirements revealed:** Text task input, Planner structured step plan, Executor navigation + form interaction, live confidence scoring in thinking panel, voice/text barge-in stop, audit log as QA artifact.

---

### Journey 5: Leila — The Travel Blogger (Complex Multi-Step Research + Booking)

Leila needs to book a Cairo → Lisbon flight for next Friday — one stop maximum, cheapest available. She's on three booking sites simultaneously and losing track of which results are comparable.

She opens ARIA: *"Find the cheapest flight from Cairo to Lisbon next Friday with one stop max. Check Google Flights, Skyscanner, and Kayak. Tell me the top 3 options before booking anything."*

ARIA opens Google Flights first. The thinking panel shows it setting the origin, destination, and date fields, filtering by stops. It extracts the top results and narrates: *"On Google Flights, the cheapest one-stop option is EgyptAir via Istanbul at $340."* It moves to Skyscanner, then Kayak.

After all three sites, ARIA surfaces a comparison: *"Cheapest overall: $298 on Skyscanner via Madrid. Would you like me to proceed to booking?"* Leila says *"Yes, the Skyscanner one."*

ARIA navigates to the booking flow. Before entering payment: *"I've reached the payment step. This is an irreversible purchase of $298. Shall I proceed?"* Leila confirms.

**Requirements revealed:** Voice task input, multi-site navigation by Executor, structured results aggregation and display, user confirmation before proceeding, destructive action guard on purchase.

---

### Journey 6: Chris — The Content Creator (Repetitive Upload Workflow)

Chris uploads a new video every week to three platforms. Same process every time: title, description, tags, thumbnail, category. He's done it 80 times. It's 20 minutes of his life he'll never get back — every single week.

He opens ARIA and pastes his metadata doc, then says: *"Upload my latest video to YouTube. The file is on my desktop. Use the title, description, and tags from this doc."*

ARIA opens the YouTube upload interface. The thinking panel shows it locating the upload button, dragging the file, then systematically filling each metadata field from the doc. Chris watches, doing something else.

The thinking panel flags: *"The tags field has a 500-character limit. Your provided tags exceed this. I've trimmed to fit — want to review before I continue?"* Chris glances over: *"Yeah that's fine, continue."*

Before publishing: *"I'm about to publish this video publicly. This will make it live immediately. Confirm?"* Chris says *"Confirm."*

**Requirements revealed:** Text + document input, Executor file interaction and form-filling, constraint detection and flagging in thinking panel, user micro-confirmation mid-task, destructive action guard on publish.

---

### Journey Requirements Summary

| Capability | Journeys That Require It |
|---|---|
| Voice task input | Sara, Margaret, Leila, Chris (partial) |
| Text task input | Ravi, Chris, James (partial) |
| Planner step plan display | All journeys |
| Executor browser/form actions | All journeys |
| Live thinking panel with confidence | All journeys — Ravi specifically needs confidence scoring |
| Voice narration | Margaret (critical), Sara, Leila |
| Mid-task user input request | Sara (file upload), Margaret (field data), Chris (tag review) |
| Voice barge-in / interruption | James (correction), Ravi (stop), Sara (implicit) |
| Destructive action guard | Sara (submit), Margaret (submit), Leila (purchase), Chris (publish) |
| Structured output / results display | James (comparison list), Leila (flight options) |
| Audit log | Sara (compliance record), Ravi (QA evidence), Margaret (personal record) |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Voice-in → Browser-Action as a Native Interaction Paradigm**
No existing UI navigator routes voice input through to live browser actions. Atlas (OpenAI), Comet, browser-use, Skyvern, and Manus all treat voice as a chat interface, not an action trigger. ARIA is the first product to wire Gemini Live API's native audio stream directly into a browser automation pipeline — user speaks, browser moves. This is a new interaction category, not a feature addition to an existing one.

**2. Barge-in Interruption Mid-Execution**
Mid-execution voice interruption with sub-1-second response is only achievable via Gemini Live API's native Voice Activity Detection. No buffered or polling approach reaches this latency target. The ability to say "wait, wrong field" and have an actively-executing agent pause, re-listen, and adapt its plan is unprecedented in the UI navigator space. It is the moment that makes ARIA feel like a collaborator rather than a script.

**3. Transparency as a Steering Mechanism (not just feedback)**
The live thinking panel is not a debug log or status indicator. It is the primary UX surface through which users actively decide whether to let ARIA continue or redirect it. Confidence scores, step previews, and annotated screenshots serve agency, not just information. Manus shows a passive computer-view; no competitor has built a transparency layer designed explicitly to empower user steering.

**4. Visible Dual-Agent Architecture as the UX**
The Planner + Executor split (Gemini 3.1 Pro reasoning → Gemini Computer Use acting) is intentionally exposed to the user as the product experience. Users see an agent that thinks before it acts. Every competitor hides their internal architecture; ARIA makes it the demonstration.

**5. Full Gemini Multimodal Stack Integration (First-of-Kind Demo)**
ARIA is the first product to combine Gemini 3.1 Pro + Gemini Computer Use + Gemini Live API + ADK + Cloud Run in a single coherent user-facing product. Each component is available individually; no one has assembled them into this specific interaction loop. In the context of a Google-hosted hackathon, this stack integration is itself an innovation demonstration.

### Market Context & Competitive Landscape

Across all five major competitors — Atlas, Comet, browser-use, Skyvern, Manus — zero support voice-in → UI-action. Zero show a live reasoning panel. Zero expose a visible planner layer. Zero implement barge-in interruption. ARIA leads on 10 of 12 competitive dimensions (per market research). The gap is not incremental — it is structural: competitors built execution engines; ARIA builds an interaction layer on top of execution capability.

The browser automation benchmark ceiling (89.1% on WebVoyager for browser-use; 85.85% for Skyvern) confirms that execution accuracy is no longer the differentiating frontier. The open frontier is trust, transparency, and real-time human-agent collaboration — exactly where ARIA operates.

### Validation Approach

| Innovation | Validation Method |
|---|---|
| Voice-in → browser-action | End-to-end latency test: voice command to first browser action < 3s on Cloud Run |
| Barge-in interruption | Timed test: utterance of "stop" to ARIA pause < 1s across 10 consecutive runs |
| Live thinking panel accuracy | Panel step vs. Executor action sync: < 500ms lag, verified via OpenTelemetry trace |
| Destructive action detection | 100% detection rate across all demo scenarios — zero misses acceptable |
| Demo as innovation proof | 4-minute demo video must show all four innovations in sequence on real working software |

### Risk Mitigation

Innovation-specific risks and mitigations are documented in the **Risk Mitigation Strategy** section under Project Scoping & Phased Development.

## Web Application Specific Requirements

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

## Project Scoping & Phased Development

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

## Functional Requirements

### Task Input & Session Initiation

- **FR1:** User can assign a task to ARIA using natural language voice input
- **FR2:** User can assign a task to ARIA using natural language text input
- **FR3:** User can provide supplementary context (e.g., paste document content, provide field values) as part of a task assignment
- **FR4:** User can start a new task session at any time
- **FR5:** User can cancel an in-progress task session
- **FR6:** ARIA displays the interpreted task back to the user before execution begins
- **FR7:** ARIA presents an ordered, human-readable step plan to the user before the Executor begins acting

### Agent Execution (Browser Navigation)

- **FR8:** ARIA can navigate to a URL in a controlled browser session
- **FR9:** ARIA can click interactive elements (buttons, links, checkboxes, dropdowns) on a web page
- **FR10:** ARIA can type text into input fields and text areas on a web page
- **FR11:** ARIA can scroll a web page vertically and horizontally
- **FR12:** ARIA can submit forms on a web page
- **FR13:** ARIA can read and extract visible text content from a web page
- **FR14:** ARIA can identify and interact with UI elements using visual understanding of the current page state
- **FR15:** ARIA can detect when a page has finished loading before proceeding to the next action
- **FR16:** ARIA can recover from a failed action by re-evaluating the page state and retrying

### Live Transparency & Thinking Panel

- **FR17:** User can view a real-time feed of ARIA's current step, what it is looking at, and what action it plans to take next
- **FR18:** User can view an annotated screenshot of the current browser state within the thinking panel
- **FR19:** User can view ARIA's confidence level for the current action within the thinking panel
- **FR20:** The thinking panel updates to reflect each new Executor action as it occurs
- **FR21:** ARIA narrates its actions aloud in natural language as it executes each step
- **FR22:** User can view the full ordered step plan and track which step is currently active

### Voice Interaction & Barge-in

- **FR23:** User can speak to ARIA at any time during task execution without needing to press a button to activate listening
- **FR24:** User can interrupt ARIA mid-execution with a voice command and ARIA stops the current action
- **FR25:** ARIA resumes listening for a new instruction after a barge-in interruption
- **FR26:** ARIA adapts its execution plan in response to a mid-task voice correction from the user
- **FR27:** ARIA responds to the user in natural spoken voice during and after task execution

### Safety, Control & Confirmation

- **FR28:** ARIA detects when an action is irreversible (form submission, purchase confirmation, record deletion, content publishing) before executing it
- **FR29:** ARIA pauses execution and presents a confirmation request to the user before executing any detected irreversible action
- **FR30:** ARIA presents the confirmation request in both voice (spoken) and visual (UI) form simultaneously
- **FR31:** ARIA proceeds with the irreversible action only upon explicit user approval
- **FR32:** ARIA cancels the irreversible action and remains in a paused state if the user declines or does not respond
- **FR33:** ARIA pauses execution and requests missing information from the user when required data is unavailable (e.g., a field value it cannot infer)

### Audit Log & Session Record

- **FR34:** ARIA records every action taken during a task session, including the step description, action type, and timestamp
- **FR35:** ARIA captures a screenshot of the browser state at each significant step and associates it with the corresponding audit log entry
- **FR36:** User can view the audit log for a completed session, including all steps and screenshots, after execution finishes
- **FR37:** The audit log is persisted to durable storage and survives browser refresh or session end

### System & Deployment

- **FR38:** The ARIA backend runs as a deployed service on Google Cloud Run accessible via HTTPS
- **FR39:** The ARIA frontend is accessible via a public URL without requiring local installation
- **FR40:** ARIA operates within a sandboxed browser environment isolated from the user's local machine
- **FR41:** ARIA handles page load failures and network errors during execution without crashing the session
- **FR42:** ARIA handles CAPTCHA encounters by pausing and notifying the user that manual intervention is required

## Non-Functional Requirements

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
