# Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

9 areas where AI agents could make incompatible choices without explicit rules.

---

### Naming Patterns

**API field naming:** `snake_case` everywhere in JSON payloads exchanged between backend and frontend.
- Backend (Python) produces snake_case naturally; frontend converts at the API layer boundary only.
- Example: `session_id`, `step_index`, `is_destructive`, `screenshot_url`
- Anti-pattern: mixing `sessionId` in some endpoints and `session_id` in others

**REST endpoint naming:** plural nouns for collections, kebab-case paths.
- Correct: `POST /api/task/start`, `GET /api/task/{session_id}/status`
- Anti-pattern: `POST /api/startTask`, `GET /api/getTaskStatus`

**Route/path parameters:** `{session_id}` style (not `:session_id`).

**SSE event types:** `snake_case` verb_noun format.
- Correct: `step_start`, `step_complete`, `task_complete`, `awaiting_confirmation`
- Anti-pattern: `StepStarted`, `stepStart`, `STEP_START`

**Python code:** `snake_case` for all functions, variables, files, and module names.
- Agent files: `planner_agent.py`, `executor_agent.py`
- Functions: `run_planner()`, `write_audit_step()`

**TypeScript/React code:** `camelCase` for variables and functions; `PascalCase` for components and types.
- Components: `ThinkingPanel`, `VoiceWaveform`, `AuditLog`
- Hooks: `useVoice`, `useThinkingPanel`
- Store slices: `sessionSlice`, `voiceSlice`

**Firestore collection/document naming:** `camelCase` collection names, `snake_case` field names.
- Collection: `sessions` (plural)
- Fields: `session_id`, `created_at`, `task_description`

---

### Structure Patterns

**Python agent structure:**
```
aria-backend/
  agents/
    __init__.py          # exports root_agent
    planner_agent.py
    executor_agent.py
    root_agent.py        # SequentialAgent wiring
  tools/
    playwright_computer.py
  handlers/
    voice_handler.py     # Gemini Live API WebSocket relay
    sse_handler.py       # ADK events → SSE stream
    audit_writer.py      # Firestore + GCS writes
  prompts/
    planner_system.py
    executor_system.py
  main.py                # FastAPI app entrypoint
```

**TypeScript project structure:** Feature-based under `src/components/`, type-based only for `src/lib/`.
- All voice UI components live in `src/components/voice/`
- All thinking panel components live in `src/components/thinking-panel/`
- No component files directly in `src/components/` root

**Test file location:** Co-located with source — `foo.test.ts` next to `foo.ts` for frontend; `tests/test_foo.py` at backend root for Python.

---

### Format Patterns

**API response wrapper — ALL REST responses use this envelope:**
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```
Error case:
```json
{
  "success": false,
  "data": null,
  "error": { "code": "TASK_NOT_FOUND", "message": "Session not found" }
}
```

**HTTP error codes:** `200` success, `400` bad request, `401` unauthorized, `404` not found, `409` conflict (e.g. task already running), `500` server error. Never use `200` for errors.

**Dates/timestamps:** ISO 8601 strings everywhere (`2026-02-24T14:30:00Z`). Never Unix timestamps in API or Firestore.

**Planner JSON step plan — canonical schema (all agents must match exactly):**
```json
{
  "task_summary": "string",
  "steps": [
    {
      "step_index": 0,
      "description": "string",
      "action": "navigate | click | type | scroll | screenshot | wait",
      "target": "string or null",
      "value": "string or null",
      "confidence": 0.0,
      "is_destructive": false,
      "requires_user_input": false,
      "user_input_reason": "string or null"
    }
  ]
}
```

---

### Communication Patterns

**SSE event envelope — canonical (frontend EventSource consumer must match exactly):**
```json
{
  "event_type": "step_start | step_complete | step_error | plan_ready | awaiting_confirmation | awaiting_input | task_complete | task_failed",
  "session_id": "sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "step_index": 0,
  "timestamp": "ISO8601",
  "payload": {}
}
```

**Zustand state updates:** Always use immer-style via Zustand's `set()` — never mutate state directly.
```typescript
// Correct
set((state) => { state.steps.push(newStep); });
// Anti-pattern
state.steps.push(newStep); // direct mutation
```

**WebSocket audio chunks:** Raw PCM, 16kHz, 16-bit, mono. Fixed format — no runtime encoding negotiation.

---

### Process Patterns

**Error handling:**
- Backend: all agent errors caught at the FastAPI route level; emit `task_failed` SSE event; never propagate exceptions as HTML 500 pages
- Frontend: all SSE `task_failed` events update `taskStatus` to `'failed'` and surface `error.message` in UI — no silent failures
- Retry: Executor retries a failed action at most **2 times** before escalating to `step_error` SSE and pausing for user input

**Loading states:** Each stream has its own loading boolean in Zustand — `isSessionStarting`, `isVoiceConnecting`, `isThinkingPanelConnecting`. Never a single global loading flag.

**Destructive action flow — exact sequence all agents must follow:**
1. Planner sets `is_destructive: true` on the step
2. Executor detects flag before executing — never executes without confirmation
3. Backend emits `awaiting_confirmation` SSE event
4. Frontend shows confirmation UI + speaks TTS confirmation
5. User confirms via voice or UI → `POST /api/task/{session_id}/confirm`
6. Executor proceeds only after receiving confirm signal

**Context window management:** Executor context = system prompt + current step plan + last 3 completed step results + current screenshot. Older steps summarized into a single `completed_steps_summary` string.

**Barge-in cancellation primitive:** Each session owns one `asyncio.Event` keyed by `session_id`, stored in a module-level dict in `session_service.py`. Pattern:

```python
# session_service.py
_cancel_flags: dict[str, asyncio.Event] = {}

def get_cancel_flag(session_id: str) -> asyncio.Event:
    if session_id not in _cancel_flags:
        _cancel_flags[session_id] = asyncio.Event()
    return _cancel_flags[session_id]

def signal_barge_in(session_id: str):
    get_cancel_flag(session_id).set()

def reset_cancel_flag(session_id: str):
    get_cancel_flag(session_id).clear()
```

`voice_handler.py` calls `signal_barge_in(session_id)` when VAD detects speech mid-execution. `playwright_computer.py` checks `cancel_flag.is_set()` before AND after every Playwright `await` call and raises `BargeInException` if set. The Executor's step loop catches `BargeInException`, stops execution, and returns control to `voice_handler.py` for replanning. This is the correct Python pattern — `task.cancel()` is NOT used because it injects `CancelledError` unpredictably across unrelated awaits.

**Audio relay queue pattern:** `voice_handler.py` must treat the browser ↔ Gemini Live relay as a pure pass-through pipe using `asyncio.Queue`. No logging, no inspection, no JSON parsing of audio bytes in the relay path:

```python
# voice_handler.py — canonical structure
async def relay_audio(session_id: str, browser_ws: WebSocket):
    inbound_q: asyncio.Queue[bytes] = asyncio.Queue()
    outbound_q: asyncio.Queue[bytes] = asyncio.Queue()

    async def browser_to_queue():
        async for chunk in browser_ws.iter_bytes():
            await inbound_q.put(chunk)  # never inspect or log chunk

    async def queue_to_gemini(gemini_session):
        while True:
            chunk = await inbound_q.get()
            await gemini_session.send(chunk)

    async def gemini_to_browser(gemini_session):
        async for response in gemini_session:
            await outbound_q.put(response.audio)

    async def queue_to_browser():
        while True:
            audio = await outbound_q.get()
            await browser_ws.send_bytes(audio)

    await asyncio.gather(
        browser_to_queue(),
        queue_to_gemini(gemini_session),
        gemini_to_browser(gemini_session),
        queue_to_browser(),
    )
```

Rationale: Python's GIL causes micro-stutters when the event loop is busy with JSON parsing or logging while audio chunks are waiting. The queue decouples receipt from forwarding, keeping the hot path non-blocking. Any barge-in detection logic runs in a separate coroutine that reads from a side-channel, never from the audio queue itself.

---

### Enforcement Guidelines

**All AI Agents MUST:**
- Use `snake_case` for all JSON field names in API payloads and Firestore documents
- Use the canonical SSE event envelope schema exactly — no additional top-level fields
- Use the canonical Planner step plan schema exactly — no field renames
- Wrap all REST responses in the `{ success, data, error }` envelope
- Never execute a step where `is_destructive: true` without a confirmed `POST /confirm`
- Always emit a `task_failed` SSE event on unhandled exceptions — no silent failures
- Use `sess_` prefix + UUID v4 for all session IDs (format: `sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- Never use `task.cancel()` for barge-in — always use the session `asyncio.Event` cancellation primitive
- Never log, inspect, or await anything in the audio relay hot path — pure `asyncio.Queue` pass-through only
- Deploy with `--concurrency 1 --memory 4Gi` — never rely on Cloud Run default concurrency (80) for Playwright workloads

---
