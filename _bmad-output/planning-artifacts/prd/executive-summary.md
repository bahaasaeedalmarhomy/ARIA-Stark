# Executive Summary

ARIA (Adaptive Reasoning & Interaction Agent) is a voice-driven, multimodal UI navigator that executes web-based tasks on behalf of users while keeping them visibly in control throughout execution. Users assign tasks by speaking or typing; ARIA decomposes the task into a visible step plan, executes it in a live browser session using Gemini's Computer Use model, narrates its reasoning aloud, and accepts voice interruptions mid-action — allowing users to redirect without stopping and restarting. Before any irreversible action, ARIA surfaces a confirmation in both voice and UI. Every completed task generates a full audit log with annotated screenshots, replayable as undo history or step-by-step documentation.

ARIA is built on Google's full agentic stack: Gemini 3.1 Pro (Planner), Gemini 3 flash with built-in computer use (Executor), Gemini Live API with native VAD (voice streaming and barge-in), Google ADK (dual-agent orchestration and observability), Cloud Run, Firestore, and Firebase Hosting. It is entered in the **UI Navigator** category of the Google Gemini Live Agent Challenge, targeting the Grand Prize and Best of UI Navigators award.

### What Makes This Special

Every existing UI navigator — Atlas (OpenAI), Comet (Perplexity), browser-use, Skyvern, Manus (Meta) — was designed around execution. They assume the user's role ends at delegation. ARIA's core design bet is the opposite: **the user is always present, always able to redirect, and the system is always intelligible to them**. This is not a UX choice bolted on top of an automation engine — it is the product.

Three capabilities combine to make this real, none of which any competitor delivers:

1. **Voice interruption mid-execution** — Gemini Live API's native Voice Activity Detection enables true barge-in: users say "wait, wrong field" and ARIA pauses, re-listens, and adapts its plan in under 1 second. No buffering, no polling. This is only possible on this specific model stack.
2. **Full multimodal loop — audio in, live vision, audio out — all real-time** — ARIA does not use voice as a chat layer bolted on top of automation. Every stage of the interaction loop is natively multimodal: Gemini Live API processes streaming audio and responds in natural voice; Gemini Computer Use interprets live screenshots to navigate any UI without DOM parsing; voice narration closes the loop back to the user while execution is still in progress. No other UI navigator runs audio input, visual page understanding, and audio output simultaneously in a tight, real-time feedback cycle.
3. **Visible Planner + Executor architecture** — The dual-agent split (Gemini 3.1 Pro reasoning + Gemini Computer Use acting) is exposed to the user as the UX, not hidden as an implementation detail. Users experience an agent that *thinks before it acts*.

The core insight: users don't distrust AI agents because they lack capability. They distrust them because they can't see where the agent is heading and can't stop it in time. ARIA solves the visibility and control problem — and trust follows automatically.
### Project Classification

| Dimension | Value |
|---|---|
| **Project Type** | Web application (Next.js frontend, Python/ADK backend, real-time SSE + WebSocket) |
| **Domain** | General productivity — AI-native, no regulated domain constraints |
| **Complexity** | High — novel multimodal AI stack, dual-agent architecture, real-time voice streaming, GCP multi-service integration, hackathon deadline |
| **Project Context** | Greenfield — new product, no existing system |
