---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - _bmad-output/brainstorming/brainstorming-session-2026-02-23.md
  - _bmad-output/planning-artifacts/research/market-ui-navigator-agents-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/domain-agentic-ai-computer-use-ux-research-2026-02-23.md
  - _bmad-output/planning-artifacts/research/technical-aria-stack-research-2026-02-23.md
date: 2026-02-23
author: Bahaa
---

# Product Brief: ARIA — Adaptive Reasoning & Interaction Agent

<!-- Content will be appended sequentially through collaborative workflow steps -->

---

## Executive Summary

ARIA (Adaptive Reasoning & Interaction Agent) is an AI that handles web-based tasks for you — any task, any website or web application — while you watch, steer, and stay in control. Say "fill out this insurance form" or "book the cheapest flight on this page" and ARIA opens your browser, looks at the page, plans the steps, and executes them visibly, narrating as it works. If it's going the wrong way, you say so — and it stops, listens, and adjusts. This continuous, voice-driven interaction is what separates ARIA from every existing browser automation tool, and it is made possible by Google Gemini's uniquely capable multimodal stack: a model that simultaneously sees the screen, hears your voice, and reasons about what to do next.

Transparency and voice interruption are not features added for their own sake — they are the direct mechanism through which ARIA achieves seamlessness. If users cannot see where the agent is headed, they cannot trust it to act; if they cannot interrupt it, they cannot steer it. ARIA makes both natural. Gemini's multimodal model family — combining vision-based UI understanding, live voice streaming, and deep reasoning — is the uniquely right platform for this: no other model stack can simultaneously see the screen, hear the user, reason about the task, and narrate its progress.

---

## Core Vision

### Problem Statement

Navigating software is a universal friction point. Whether someone is filling out a complex form, executing a repetitive workflow, or trying to accomplish a task on an unfamiliar application, the process is slow, manual, and cognitively demanding. Existing AI automation tools offer a false choice: either the user stays fully in control (manual work, just with AI suggestions) or hands the task entirely to an agent that acts silently, unpredictably, and without the ability to be steered mid-execution.

The core problem is not that automation exists — it is that current automation **breaks the interaction**. The user is excluded from the process the moment they delegate to it. They cannot tell if the agent is on the right path. They cannot correct it without stopping and restarting. The hand-off is irreversible until something goes wrong.

### Problem Impact

**Primary user:** The person who wants AI to handle their web tasks but doesn't trust systems they can't see or interrupt. They're not a developer. They can't write a script. But they've tried AI tools before, watched them go wrong, and decided the risk wasn't worth it. ARIA is built for them — the visibility and voice control exist specifically to earn this user's trust.

**Secondary users who benefit from the same design:**
- **Knowledge workers** executing repetitive multi-step web workflows who want to offload the mechanical work without losing oversight
- **Teams** who need documented, auditable execution trails — the audit log serves compliance and training needs without extra effort
- **Power users** who want to delegate the low-cognition parts of complex tasks while retaining strategic control

The problem is not a niche — it is any person who has ever watched an AI agent do the wrong thing and had no way to stop it in time.

### The Gap in the Market

The browser automation space has strong players — but every one of them was built around execution, not interaction. The gap that remains open is not technical capability; it is the interaction layer that makes capability trustworthy and usable.

| Competitor | What They Built Well | What They Left Unsolved |
|---|---|---|
| ChatGPT Atlas | Brand reach, GPT-5 reasoning | Acts silently; voice is chat-only, not UI action; no steering mid-task |
| Perplexity Comet | Speed, research synthesis | Black box execution; no control once delegated |
| browser-use / Skyvern | High navigation accuracy | Developer tools — no interaction UX for non-technical users |
| Manus (Meta-owned) | Multi-agent architecture | Passive watch-only; no voice; Meta acquisition creates roadmap uncertainty |

None of them have built the interaction layer. They all assume the user's job ends when the task is delegated. ARIA's entire design begins from the opposite assumption: **the user is always present, always able to redirect, and the system is always intelligible to them**.

### Proposed Solution

ARIA is a voice-driven multimodal UI navigator with a live reasoning panel. The user assigns a task by speaking or typing. ARIA — powered by a Gemini Planner agent — decomposes the task into visible, ordered steps and begins executing them through a specialized Gemini Computer Use Executor agent that sees and interacts with the browser like a human would. Throughout execution, the user sees a live annotated thinking panel: what ARIA is looking at, what it plans to do next, and how confident it is. At any point, the user can say "wait" or "stop that" and ARIA pauses, listens, and adapts.

Before any irreversible action — submitting a form, confirming a purchase, deleting a record — ARIA surfaces a confirmation in both voice and visual UI. Every task generates a full audit log with screenshots, which doubles as an undo history and an auto-generated step-by-step documentation of what was done.

The result is a UI navigator that feels not like running a script, but like working with a smart, attentive collaborator who explains what they're doing as they do it.

### Key Differentiators

**1. A native multimodal interaction loop — the core bet**
ARIA is built from the ground up on Gemini's multimodal stack: vision (Computer Use model), voice (Gemini Live API), and reasoning (Gemini 3.1 Pro). The user speaks, the agent sees the screen, executes, and narrates — all in one native pipeline. No setup, no scripting, no configuration beyond the task itself. No competitor uses Gemini Live API for UI navigation; no competitor has wired voice input through to browser action.

**2. Transparency as a steering mechanism**
The live thinking panel is not a debug log. It is the primary UX surface through which users decide whether to let ARIA continue or redirect it. Confidence scores, annotated screenshots, and step previews exist because the user needs to steer — not just watch. This is what makes delegation feel safe rather than risky.

**3. Voice interruption mid-execution**
Barge-in via Gemini Live API's native Voice Activity Detection allows users to say "wait, that's the wrong field" mid-action. ARIA pauses, re-listens, and adapts its plan. No existing UI navigator supports this. It is the single interaction pattern that makes ARIA feel like a collaborator rather than a script.

**Supporting capabilities** *(each strengthens the core three, none is a standalone differentiator)*
- **Audit log + auto-documentation:** Every task generates a replayable, screenshot-annotated log — serving as undo history, compliance record, and automatic step-by-step documentation
- **Gemini-native stack:** Gemini 3.1 Pro (Planner) + Gemini Computer Use model (Executor) + Gemini Live API (Voice) + ADK + Cloud Run + Firestore — ARIA is the flagship demonstration of what Google's full agentic platform can do together
- **Destructive action guard:** Before irreversible actions (submit, delete, purchase), ARIA surfaces a confirmation in voice and UI — the safety layer that makes broader task delegation trustworthy

---

## Target Users

### Primary User Profile

ARIA's primary user is defined not by profession or technical skill level, but by a shared expectation: they want to delegate a web-based task and remain comfortable throughout — able to follow along, redirect if needed, and trust that the agent is doing the right thing. They span age groups, technical backgrounds, and use cases. What unites them is that they find the act of navigating software either tedious, time-consuming, or outside their comfort zone — and they would hand it off if they trusted the tool.

### User Spectrum

ARIA serves a wide range of everyday users. Each persona below represents a real use case that requires no customization, no configuration, and no technical knowledge to activate:

| Persona | Context | Task They Hand to ARIA |
|---|---|---|
| **Sara, 34, operations manager** | Submits vendor forms and portal entries daily | "Fill out the monthly compliance form on this supplier portal" |
| **James, 22, college student** | Researches and compares options across multiple sites | "Go through these 5 hotel pages and collect their prices, ratings, and amenities into a list" |
| **Margaret, 61, retired teacher** | Occasional web tasks, not tech-confident | "Help me fill in my Medicare supplemental insurance application on this site" |
| **Ravi, 28, startup founder** | Wants to QA his own web app before a release | "Go through my checkout flow and check that every step works correctly" |
| **Leila, 41, travel blogger** | Plans complex multi-stop trips using multiple booking sites | "Find and book the cheapest connection from Cairo to Lisbon next Friday with one stop max" |
| **Chris, 19, gamer and content creator** | Repetitive account management and content submission tasks | "Upload my latest video to this platform and fill in the title, description, and tags I give you" |

### What Every Persona Has in Common

None of these users wants to watch a script run. They want to **stay present** — see what ARIA is doing, hear it explain its steps, and say "wait, not that" when it's heading the wrong way. The voice interaction, the thinking panel, and the live narration are not features targeted at any specific persona — they are the baseline experience that makes ARIA trustworthy and enjoyable for all of them.

### User Journey (Universal Pattern)

1. **Entry:** User speaks, types, or shares an image to describe the task — no setup, no tutorial
2. **Planning moment:** ARIA displays the step plan before acting — "Here's what I'll do. Starting now."
3. **Execution with narration:** ARIA works through the browser while the thinking panel shows each step live
4. **Steering moment:** User watches, corrects mid-task if needed ("actually, use the monthly view, not weekly")
5. **Safety gate:** Before any irreversible action, ARIA confirms — voice + visual
6. **Completion:** Task done; audit log available; user can replay, undo, or export documentation
7. **Trust built:** The next task is delegated with less hesitation than the first

### Demo Philosophy

The demo is not a task showcase — it is an **experience showcase**. The goal is for a viewer to watch 90 seconds of ARIA in action and feel: *"That looked easy. That looked smooth. I'd actually use that."* The specific task in the demo is secondary to the quality of the interaction — the voice flowing naturally into action, the thinking panel updating in real time, and the agent pausing to confirm before it submits. These moments, strung together fluently, are the demo.

---

## Success Metrics

### Hackathon Success Criteria

ARIA is competing in the **UI Navigator** category with a bid for the **Grand Prize** and the **Best of UI Navigators** award. The judging rubric maps directly to ARIA's design:

| Judging Dimension | Weight | What ARIA Must Demonstrate |
|---|---|---|
| Innovation & Multimodal UX | 40% | Voice-in → browser-action pipeline feels seamless and live; thinking panel makes the "see, hear, speak" paradigm tangible; experience feels context-aware, not turn-based |
| Technical Architecture | 30% | ADK dual-agent (Planner + Executor), Gemini Live API, Cloud Run deployment, Firestore audit log — all working and evidenced; grounding via accessibility tree; graceful error handling |
| Demo & Presentation | 30% | Video shows the actual software working; architecture diagram is clear; Cloud deployment is proven; problem + solution communicated in under 4 minutes |

**Definition of hackathon success:** A demo that makes a judge lean forward during the voice-interruption moment — when the user says "wait, wrong field" mid-execution and ARIA adapts in real time. That single moment validates all three judging dimensions simultaneously.

### Internal Quality Targets

These are measurable through internal testing and demo rehearsal before submission:

**Task execution quality**
- Task completion rate on demo scenarios: target 100% — the demo tasks must be reliable and repeatable without manual intervention
- Correct destructive action detection: ARIA must pause before every irreversible action in all tested scenarios — target 100%, zero misses acceptable

**Voice interaction quality**
- Voice-to-action latency: first browser action after voice command begins — target under 3 seconds end-to-end
- Barge-in response: time from user saying "stop/wait" to ARIA pausing — target under 1 second
- Gemini Live API round-trip latency: target 1–1.8s (streaming mode, not buffered)

**Technical robustness**
- No cold start failures during demo — Cloud Run `--min-instances 1` must be set before recording
- Chromium stability in Cloud Run container — zero crashes during a full demo run
- Thinking panel sync: panel steps must reflect Executor actions within 500ms

---

## MVP Scope

### Core Features (Must Ship)

These are the features without which ARIA fails to demonstrate its core thesis — voice-driven, transparent, steer-able browser navigation:

| Feature | What It Does | Why It's Core |
|---|---|---|
| **Voice task input** | User speaks a task; Gemini Live API transcribes and routes to Planner | Without this, ARIA is not multimodal — fails the 40% Innovation criterion |
| **Text task input** | Fallback for voice; user types a task | Needed for reliability in demo; voice-only is fragile |
| **Planner Agent (Gemini 3.1 Pro)** | Decomposes task into ordered, structured JSON step plan | The reasoning layer — without it, there's no "thinking" to show |
| **Executor Agent (Gemini Computer Use)** | Executes browser actions (click, type, navigate, scroll) via Playwright | The action layer — without it, nothing happens |
| **Live thinking panel** | Shows current step, annotated screenshot, confidence score in real time | The primary UX differentiator — must work and look compelling |
| **Voice narration** | Gemini Live API reads each step aloud as Executor acts | Makes the experience feel alive and transparent, not silent |
| **Destructive action guard** | Pauses before submit/delete/purchase; asks user to confirm | Demonstrates safety-first design; required for trust story |
| **Voice barge-in (interruption)** | User says "wait/stop" mid-execution; ARIA pauses and adapts | The single most impressive demo moment; validates the Live API usage |
| **Audit log (basic)** | Stores session steps + screenshots in Firestore/GCS | Required for demo proof of GCP usage; enables replay |
| **Cloud Run deployment** | Full backend hosted on Cloud Run | Required by hackathon rules; must be provable |

### Out of Scope for MVP

Explicitly deferred — not cut because they're unimportant, but because 21 days won't support them without risking the core:

| Feature | Why Deferred |
|---|---|
| **Audit log export / auto-documentation** | Nice-to-have; core audit log will be built, export formatting is polish |
| **Proactive co-pilot mode** | Requires session memory and behavioral modeling — post-hackathon |
| **Full desktop control** | Outside the hackathon category scope (UI Navigator = browser) |
| **"Teach me" mode** | Valuable but not essential for the demo story |
| **Playwright test generation** | Strong product feature, wrong timeline |
| **Multi-tab / multi-window navigation** | Complex edge case; single-tab is sufficient for demo |
| **Mobile UI control** | Adds scope without adding demo impact |
| **Custom autonomy dial** | Post-MVP UX refinement |

### 3-Week Build Plan

| Week | Focus | Deliverables |
|---|---|---|
| **Week 1** (Feb 23 – Mar 2) | Core agent pipeline | ADK scaffold, Planner + Executor agents working locally, SSE stream to frontend, thinking panel MVP, destructive action guard |
| **Week 2** (Mar 3 – Mar 10) | Voice + cloud | Gemini Live API voice pipeline, barge-in support, Cloud Run deployment with Playwright, Firestore audit log, confidence overlays on thinking panel |
| **Week 3** (Mar 11 – Mar 17) | Demo + polish | Demo scenario rehearsed and locked, error handling for known failure modes, architecture diagram, 4-minute video recorded and submitted |

### Future Vision (Post-Hackathon)

If ARIA wins or achieves strong recognition, the natural expansion path:
- **Audit log export** — auto-generate step-by-step documentation from any completed session
- **Session memory** — ARIA remembers past tasks and user preferences across sessions
- **Proactive co-pilot** — ARIA notices repetitive patterns and offers to automate them
- **SOP ingestion** — upload a standard operating procedure doc; ARIA executes it on any matching page
- **API / headless mode** — run ARIA programmatically for team workflow automation
