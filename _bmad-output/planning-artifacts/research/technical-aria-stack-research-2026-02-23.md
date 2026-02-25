---
stepsCompleted: [1, 2, 3]
research_type: technical
research_topic: "ARIA Technical Stack — ADK ComputerUse, Gemini Live API, GCP Services, Frontend, Playwright Cloud"
research_goals: "Provide implementation-ready technical decisions for the Architect and Dev agents covering all core ARIA components"
date: 2026-02-23
project: gemini-hackathon
---

# Technical Research: ARIA Implementation Stack

**Researcher:** Mary (Business Analyst Agent)  
**Date:** February 23, 2026  
**Purpose:** Implementation-ready technical decisions across all six core ARIA components — input to the Architect and Dev agents

---

## Executive Summary

This research answers the six concrete technical questions the ARIA team needs resolved before architecture and development can begin:

| Area | Verdict |
|---|---|
| **A — ADK ComputerUseToolset** | Use ADK v1.25+ with `ComputerUseToolset` + `PlaywrightComputer`; model `gemini-2.5-computer-use-preview-10-2025` (Gemini 3-backed update expected) |
| **B — Gemini Live API** | Use `gemini-live-2.5-flash-native-audio`; WebSocket transport; native VAD + barge-in; target <1s first-audio latency |
| **C — Gemini 3 Pro for Planner** | Use `gemini-3-pro` via ADK; structure Planner as Sequential + HITL workflow agent; output structured JSON step plan |
| **D — GCP Services** | Cloud Run for agent backend; Firestore for audit log + state; Cloud Storage for screenshots; Firebase Hosting for frontend; Vertex AI Agent Engine optional (post-hackathon) |
| **E — Frontend** | Next.js 16 + React + SSE for thinking panel stream; WebSocket for voice audio; Tailwind v4 + shadcn/ui |
| **F — Playwright in Cloud** | Official `mcr.microsoft.com/playwright` Docker image; Cloud Run with 2–4 GB RAM, `--no-sandbox` flag; `--disable-dev-shm-usage` required |

---

## Area A: Google ADK ComputerUseToolset

### A.1 Current ADK Version & Capabilities

**ADK v1.25** (latest as of Feb 2026) — production-grade, fully async-first.

Key capabilities relevant to ARIA:

| Capability | ADK Feature | Version Added |
|---|---|---|
| Computer use (browser control) | `ComputerUseToolset` + `PlaywrightComputer` | v1.8 |
| Native streaming (SSE) | Built-in progressive SSE | v1.22 |
| Bidirectional audio/video streaming | Native Gemini Live API integration | v1.22+ |
| YAML-based agent declaration | Declarative agent config | v1.0 |
| Multi-agent orchestration | Sequential / Parallel / Loop workflow agents | v1.0 |
| Hot reload dev server | `adk run --reload_agents` | v1.0 |
| One-command Cloud Run deploy | `adk deploy cloud-run` | v1.12 |
| MCP tool integration | `MCPToolset` (Streamable HTTP) | v1.0 (simplified) |
| OpenTelemetry observability | Built-in tracing | v1.0 |
| A2A Protocol | Cross-framework agent communication via gRPC | v1.15+ |
| Session rewind + compaction | `sessions` service | v1.20+ |

### A.2 ComputerUseToolset — Exact API

```python
from google.adk import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from .playwright import PlaywrightComputer

# Executor Agent (Computer Use)
executor_agent = Agent(
    model='gemini-2.5-computer-use-preview-10-2025',
    name='aria_executor',
    description='Executes browser actions on behalf of ARIA Planner',
    instruction='You are ARIA Executor. Receive step instructions and execute them precisely on the browser.',
    tools=[
        ComputerUseToolset(
            computer=PlaywrightComputer(screen_size=(1280, 936))
        )
    ],
)
```

**Actions available via `PlaywrightComputer`:**
- `screenshot()` — capture current browser state as image
- `click(x, y)` — click at pixel coordinates
- `type(text)` — type text at current focus
- `key(key_combo)` — keyboard shortcuts (Enter, Tab, Escape, etc.)
- `scroll(x, y, direction, amount)` — scroll the page
- `navigate(url)` — navigate to a URL
- `wait()` — wait for page load
- `get_accessibility_tree()` — structured element tree (hybrid enrichment)

### A.3 Planner Agent (Gemini 3 Pro)

```python
from google.adk import Agent
from google.adk.agents import SequentialAgent

# Planner Agent — uses Gemini 3 Pro (not computer use model)
planner_agent = Agent(
    model='gemini-3-pro',   # or 'gemini-3-1-pro' once available via ADK
    name='aria_planner',
    description='Decomposes user tasks into ordered, executable browser steps',
    instruction='''
    You are ARIA Planner. Given a user task description and current screenshot,
    decompose the task into a precise ordered list of steps.
    For each step output:
    {
      "step_number": int,
      "description": str,          // Human-readable step description
      "action_type": str,           // "click" | "type" | "navigate" | "wait" | "verify"
      "target_description": str,   // What element to target
      "confidence": float,          // 0.0-1.0 confidence in this step
      "is_destructive": bool        // true if irreversible (submit, delete, purchase)
    }
    Always output the FULL plan before execution begins.
    ''',
    sub_agents=[executor_agent],   # Executor is a sub-agent
)
```

### A.4 Dual-Agent Architecture in ADK

```python
from google.adk.agents import SequentialAgent

# ARIA Root: Sequential Planner → Executor pipeline
aria_root = SequentialAgent(
    name='aria_root',
    description='ARIA — Adaptive Reasoning & Interaction Agent',
    sub_agents=[planner_agent, executor_agent],
)
```

ADK's **8 multi-agent design patterns** map to ARIA:
- Pattern 4 (Orchestrator + Workers): `planner_agent` orchestrates `executor_agent`
- Pattern 6 (Human-in-the-loop): Triggered when `is_destructive=True` or `confidence < threshold`
- Pattern 1 (Sequential Pipeline): `SequentialAgent` chains Planner → Executor

### A.5 ADK Observability → Thinking Panel Feed

ADK has **built-in OpenTelemetry tracing** — every agent operation emits events. ARIA's thinking panel consumes this stream:

```python
# Every action emits an event — subscribe in the runner
async for event in runner.run_async(session_id, user_message):
    if event.type == "agent_action":
        await thinking_panel_stream.send({
            "step": event.step_number,
            "description": event.description,
            "confidence": event.confidence,
            "screenshot_b64": event.screenshot,
            "element_bbox": event.target_bbox,   # For annotation overlay
            "is_destructive": event.is_destructive
        })
```

**This is the technical backbone of the thinking panel** — no custom instrumentation needed; ADK exposes it natively.

---

## Area B: Gemini Live API (Voice Streaming)

### B.1 Supported Models

| Model | Status | Use Case |
|---|---|---|
| `gemini-live-2.5-flash-preview-native-audio-09-2025` | Public Preview | Cost-efficient real-time voice |
| `gemini-live-2.5-flash-native-audio` | Available | General voice agent use |
| `gemini-3-flash-preview` | Preview | Latest generation, voice-capable |

**Recommendation for ARIA:** `gemini-live-2.5-flash-native-audio` for hackathon; upgrade to `gemini-3` native audio when available.

### B.2 Key Features

| Feature | Detail |
|---|---|
| **Voice Activity Detection (VAD)** | Built-in — no external VAD library needed |
| **Barge-in / interruption** | Native support — user can say "wait, stop" mid-execution |
| **Tool use + function calling** | Live API supports tool calls during voice session |
| **Session management** | Long-running conversation with context compaction |
| **Ephemeral tokens** | Secure client-to-server authentication |
| **Low latency** | First audio response <1s with true streaming; ~1–1.8s full turns |
| **Audio quality** | Natural, realistic speech across multiple languages |
| **WebRTC partners** | LiveKit, Fishjam, Voximplant — pre-built integrations |

### B.3 ADK Integration — Enabling Voice on an Existing Agent

The key insight: **voice is just a model configuration change**, not an architectural change:

```python
# Standard agent → voice-enabled agent: change ONE line
planner_agent = Agent(
    # Before: model='gemini-3-pro'
    model='gemini-live-2.5-flash-native-audio',  # ← this is the only change
    name='aria_planner',
    # All tools, instructions, sub-agents remain identical
    ...
)
```

Per ADK docs: *"By simply updating your Agent Declaration to point to a supported Gemini Live model, your existing tools, prompts, and reasoning paths are instantly voice and video-enabled."*

### B.4 Transport Protocol

| Protocol | When to Use |
|---|---|
| **WebSocket** | Primary: Python backend ↔ Gemini Live API; bidirectional streaming |
| **WebRTC** | Via LiveKit/Fishjam partners; better for browser-direct audio with lower latency |
| **Gen AI SDK** | Python backend with `google-genai` SDK; simplest integration path |

**ARIA recommendation:** WebSocket on Python backend → relay audio to frontend via WebSocket. This keeps audio processing server-side (security + processing power).

### B.5 Latency Reality

- **Best case** (true streaming, minimal buffering): First audio <1s, full turn 1–1.8s
- **Pathological case** (buffered path): 3s+ (Reddit reports confirm this is a config issue, not API limit)
- **Fix:** Use streaming mode, not buffered — critical to configure correctly
- **Practical demo latency:** ~1.5s — fully acceptable for a hackathon demo

### B.6 Voice Flow in ARIA

```
User speaks  →  Browser captures audio (MediaRecorder API)
             →  WebSocket to Python backend
             →  Gemini Live API (VAD + STT)
             →  Planner Agent receives text task
             →  Planner decomposes → sends plan to thinking panel (SSE)
             →  Executor executes steps
             →  Each step result → Gemini Live API (TTS)
             →  Audio response streamed to browser (narration)
             →  User can barge-in at any point ("wait, stop that")
```

---

## Area C: Gemini 3 Pro for the Planner

### C.1 Model Specifications

| Model | Context Window | Status | Best For |
|---|---|---|---|
| `gemini-3-pro` | Very large (exact size not published, Gemini 2.5 Pro was 1M tokens) | GA | Complex reasoning, Planner role |
| `gemini-3-1-pro` | Improved over 3-pro | Preview (Feb 19, 2026) | Complex problem-solving |
| `gemini-3-flash` | Large | GA | Fast Executor verification loop |
| `gemini-3-deep-think` | Large | Available | Advanced research tasks |

**ARIA Planner → `gemini-3-1-pro`** (latest as of Feb 23, 2026)
**ARIA Executor → `gemini-2.5-computer-use-preview-10-2025`** (specialized for UI)
**ARIA Voice → `gemini-live-2.5-flash-native-audio`**

### C.2 ADK Deployment via Vertex AI

```python
# Access via Vertex AI (production path)
from google.adk.models.google_llm import Gemini

model = Gemini(
    model='gemini-3-1-pro',
    project='your-gcp-project',
    location='us-central1'
)
```

### C.3 Planner System Prompt Architecture

The Planner's system prompt should have four sections:

```
SECTION 1 — ROLE
You are ARIA Planner, the reasoning brain of ARIA (Adaptive Reasoning & Interaction Agent).
Your job is to interpret user tasks, observe the current browser state, and produce a precise,
ordered execution plan for ARIA Executor to follow.

SECTION 2 — INPUT FORMAT
You receive:
- user_task: Natural language task description (from voice or text)
- current_screenshot: Base64 image of the current browser/screen state
- session_context: Previous steps taken in this session (if any)

SECTION 3 — OUTPUT FORMAT
Always output a structured JSON plan:
{
  "task_summary": str,
  "total_steps": int,
  "steps": [
    {
      "step_number": int,
      "description": str,
      "action_type": "click|type|navigate|scroll|wait|verify|ask_user",
      "target_description": str,
      "expected_outcome": str,
      "confidence": float (0.0-1.0),
      "is_destructive": bool,
      "fallback": str (what to do if this step fails)
    }
  ],
  "overall_confidence": float,
  "requires_user_input": bool,
  "user_input_reason": str (if requires_user_input is true)
}

SECTION 4 — SAFETY RULES
- NEVER plan destructive actions (submit, delete, purchase) without is_destructive=true
- If confidence < 0.7 for any step, add a verify step after it
- If task is ambiguous, set requires_user_input=true before planning
- NEVER plan actions that could exfiltrate sensitive data outside the current task scope
```

---

## Area D: GCP Service Selection

### D.1 Compute: Cloud Run vs. Vertex AI Agent Engine

| | Cloud Run | Vertex AI Agent Engine |
|---|---|---|
| **Best for** | Full control, custom containers, Playwright | Managed hosting, simple agents |
| **Playwright support** | ✅ Full — custom Docker image with Chromium | ❌ Cannot run headless browsers |
| **Cost** | Pay-per-request, scales to zero | Higher baseline, managed compute |
| **Deploy command** | `adk deploy cloud-run --project X --region Y` | `aiplatform.Agent.create(...)` |
| **Cold start** | ~2–5s (acceptable for hackathon) | <1s (managed) |
| **Custom dependencies** | ✅ Full control via Dockerfile | ❌ Limited |
| **Hackathon verdict** | ✅ **Use Cloud Run** | Post-hackathon optimization |

**Decision: Cloud Run for ARIA backend.** Playwright requires custom runtime — Agent Engine can't support it. Cloud Run with ADK's one-command deploy is the right path.

### D.2 Storage: Firestore vs. Bigtable vs. Cloud Storage

| Service | Use in ARIA | Why |
|---|---|---|
| **Firestore** | Audit log (step records), session state, agent metadata | Document model fits step-by-step records; real-time subscriptions feed thinking panel; free tier for hackathon |
| **Cloud Storage (GCS)** | Screenshot storage (binary blobs) | Firestore has 1MB document limit — screenshots (~50–200KB each) won't fit inline; GCS handles binary at scale |
| **Bigtable** | NOT needed for hackathon | Overkill for <1000 tasks per day; Firestore is sufficient |

**Firestore document structure for audit log:**
```json
{
  "session_id": "sess_abc123",
  "task": "Fill out the contact form on example.com",
  "started_at": "2026-02-23T10:30:00Z",
  "steps": [
    {
      "step_number": 1,
      "description": "Navigate to example.com",
      "action_type": "navigate",
      "confidence": 0.98,
      "is_destructive": false,
      "screenshot_gcs_uri": "gs://aria-screenshots/sess_abc123/step_1.png",
      "outcome": "success",
      "completed_at": "2026-02-23T10:30:02Z"
    }
  ],
  "status": "completed | in_progress | paused | failed",
  "exported_doc_url": null
}
```

### D.3 Full GCP Architecture for ARIA

```
┌─────────────────────────────────────────────────────┐
│                    USER BROWSER                      │
│  Next.js Frontend (Firebase Hosting)                 │
│  ├── Voice: WebSocket → Backend                      │
│  ├── Thinking Panel: SSE ← Backend                   │
│  └── Audit Log: Firestore real-time subscription     │
└──────────────────┬──────────────────────────────────┘
                   │ HTTPS / WebSocket
┌──────────────────▼──────────────────────────────────┐
│              ARIA BACKEND (Cloud Run)                │
│  Python + Google ADK v1.25                           │
│  ├── Planner Agent (Gemini 3.1 Pro)                  │
│  ├── Executor Agent (Gemini 2.5 Computer Use)        │
│  ├── Playwright + Chromium (headless)                │
│  ├── Gemini Live API (WebSocket ↔ Gemini)            │
│  ├── SSE endpoint → Frontend thinking panel          │
│  └── Firestore + GCS writes (audit log)              │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│                  GCP SERVICES                        │
│  ├── Vertex AI (Gemini 3.1 Pro model serving)        │
│  ├── Gemini API (Computer Use + Live API)            │
│  ├── Firestore (audit log, session state)            │
│  ├── Cloud Storage (screenshots)                     │
│  ├── Google Search (ADK grounding tool)              │
│  └── Cloud Logging + Trace (OpenTelemetry)           │
└─────────────────────────────────────────────────────┘
```

---

## Area E: Frontend Tech Stack

### E.1 Framework Decision

**Next.js 16 + React** is the clear choice for ARIA's frontend in 2026:

| Requirement | Solution |
|---|---|
| Real-time thinking panel (step stream) | SSE via `EventSource` API or `fetch` streaming |
| Voice audio streaming | WebSocket (`WebSocket` API + `MediaRecorder`) |
| Annotated screenshot display | Canvas API or absolute-positioned React overlays |
| Audit log real-time updates | Firestore SDK real-time listener |
| Fast deployment | Firebase Hosting (`firebase deploy`) |
| AI-agent-specific patterns | Next.js has dedicated AI agent support (Next.js Conf 2025) |

**Why Next.js over plain React:**
- Built-in API routes → SSE endpoint co-located with frontend (reduces CORS complexity for hackathon)
- `route.ts` with `ReadableStream` for SSE streaming is native
- Firebase Hosting supports Next.js with SSR

### E.2 SSE vs. WebSocket for Thinking Panel

| | SSE (Server-Sent Events) | WebSocket |
|---|---|---|
| **Direction** | Server → Client only | Bidirectional |
| **Use for** | Thinking panel step stream ✅ | Voice audio stream ✅ |
| **Complexity** | Simple — native `EventSource` API | Requires WS client library |
| **Reconnection** | Automatic browser reconnect | Manual |
| **ADK built-in** | ADK SSE streaming built-in since v1.22 ✅ | Manual WebSocket setup needed |

**Decision:**
- **Thinking panel → SSE** (ADK native, unidirectional stream of step events)
- **Voice audio → WebSocket** (bidirectional, low-latency audio chunks)

### E.3 Thinking Panel — Implementation Pattern

```tsx
// Next.js: Subscribe to ARIA thinking panel SSE stream
const ThinkingPanel = () => {
  const [steps, setSteps] = useState([]);
  const [currentScreenshot, setCurrentScreenshot] = useState(null);

  useEffect(() => {
    const eventSource = new EventSource('/api/aria/stream');
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'step_planned') {
        setSteps(prev => [...prev, data.step]);
      }
      if (data.type === 'screenshot') {
        setCurrentScreenshot(data.screenshot_b64);
      }
    };
    
    return () => eventSource.close();
  }, []);

  return (
    <div className="thinking-panel">
      <AnnotatedScreenshot 
        src={currentScreenshot} 
        annotations={currentAnnotations}  // bbox + confidence overlays
      />
      <StepList steps={steps} />
    </div>
  );
};
```

### E.4 UI Component Library

**Recommendation: Tailwind CSS + shadcn/ui**
- shadcn/ui is component-copy-paste; no dependency lock-in
- Pre-built components: `Card`, `Badge`, `Progress`, `ScrollArea` — all useful for thinking panel
- Dark mode support out of box (fits the "agent console" aesthetic)
- Fastest to prototype with for a 21-day timeline

---

## Area F: Playwright in Cloud (Cloud Run)

### F.1 Official Docker Image

Microsoft publishes an official Playwright Docker image:

```dockerfile
FROM mcr.microsoft.com/playwright:v1.58.2-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Required for Cloud Run
EXPOSE 8080
CMD ["adk", "api_server", "--port", "8080", "--agent-dir", "./aria_agent"]
```

### F.2 Required Chromium Launch Flags for Cloud Run

```python
# In PlaywrightComputer implementation for Cloud Run:
browser = await playwright.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",               # REQUIRED in containerized environments
        "--disable-setuid-sandbox",   # REQUIRED in containerized environments
        "--disable-dev-shm-usage",    # CRITICAL: /dev/shm is only 64MB in Cloud Run
        "--disable-gpu",              # No GPU in Cloud Run
        "--disable-background-networking",
        "--disable-extensions",
        "--mute-audio",
    ]
)
```

> ⚠️ **`--disable-dev-shm-usage` is critical.** Cloud Run containers have only 64MB `/dev/shm` by default. Without this flag, Chromium will crash on pages with heavy rendering. This flag tells Chromium to use `/tmp` instead.

### F.3 Cloud Run Resource Requirements

| Resource | Minimum | Recommended | Notes |
|---|---|---|---|
| **Memory** | 2 GB | **4 GB** | Chromium alone uses ~500MB; each tab adds ~100–300MB |
| **CPU** | 1 vCPU | **2 vCPU** | Screenshot processing + LLM calls |
| **Concurrency** | 1 | 1–3 | Each request runs its own browser instance |
| **Timeout** | 60s default | **300s** | Complex multi-step tasks can run 2–5 minutes |
| **Min instances** | 0 | **1** (for demo) | Cold starts with Chromium are ~5–8s; keep 1 warm for demo |

**Cloud Run deploy command:**
```bash
adk deploy cloud-run \
  --project $GCP_PROJECT \
  --region us-central1 \
  --agent-dir ./aria_agent \
  --service-name aria-backend \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --min-instances 1
```

### F.4 Screenshot Storage Pipeline

```python
# Screenshot → GCS → Firestore reference
async def save_step_screenshot(session_id: str, step_number: int, screenshot_bytes: bytes):
    # Upload to GCS
    blob_name = f"sessions/{session_id}/step_{step_number}.png"
    bucket = storage_client.bucket("aria-screenshots")
    blob = bucket.blob(blob_name)
    blob.upload_from_string(screenshot_bytes, content_type="image/png")
    
    # Store GCS URI in Firestore audit log
    gcs_uri = f"gs://aria-screenshots/{blob_name}"
    doc_ref = firestore_client.collection("sessions").document(session_id)
    doc_ref.update({
        f"steps.{step_number}.screenshot_gcs_uri": gcs_uri
    })
    
    return gcs_uri
```

## Key Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `--disable-dev-shm-usage` forgotten → Chromium crash in Cloud Run | Medium | High | Add to Docker entrypoint check; test in container before demo |
| Gemini Live API latency >3s | Low (if streaming correctly) | Medium | Use true streaming mode (not buffered); test with `gemini-live-2.5-flash-native-audio` |
| Computer Use model coordinate drift on screenshots | Medium | Medium | Add accessibility tree fallback; verify-after-click loop |
| ADK SSE stream + thinking panel tight coupling | Low | Medium | Buffer events in Firestore; thinking panel reads from Firestore not raw stream |
| Cold start time for hackathon demo | Medium | High | Set `--min-instances 1` on Cloud Run; warm up before recording |
| Screenshot storage costs | Very Low | Very Low | GCS Standard is ~$0.02/GB; hackathon usage is negligible |
