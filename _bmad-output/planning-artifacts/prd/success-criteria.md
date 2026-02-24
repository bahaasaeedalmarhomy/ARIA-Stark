# Success Criteria

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
