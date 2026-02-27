# Story 2.2: SSE Stream Endpoint for Agent Events

Status: done

## Story

As the frontend,
I want to subscribe to a Server-Sent Events stream for a session and receive structured agent events in real time,
so that the thinking panel can update immediately as the Planner and Executor produce output.

## Acceptance Criteria

1. **Given** a valid `session_id` exists, **When** `GET /api/stream/{session_id}` is requested with `Accept: text/event-stream`, **Then** the response has `Content-Type: text/event-stream`, `Cache-Control: no-cache`, and the connection stays open.

2. **Given** the Planner completes a step plan, **When** the plan is ready, **Then** a `plan_ready` SSE event is emitted with `payload: {steps: [...]}` containing the full canonical step plan within 500ms of Planner completion.

3. **Given** an SSE event is emitted, **When** the frontend `EventSource` receives it, **Then** the event data is a valid JSON object matching the canonical envelope: `{event_type, session_id, timestamp, payload}`.

4. **Given** an SSE connection drops (client disconnects), **When** the frontend reconnects with the same `session_id`, **Then** the backend accepts the new connection and resumes streaming from the current task state.

5. **Given** `GET /api/stream/{session_id}` is called with an unknown `session_id`, **When** the request is processed, **Then** the response is `404 Not Found` with the canonical error envelope.

## Tasks / Subtasks

- [x] Task 1: Create the SSE event manager service (AC: 2, 3)
  - [x] Create `services/sse_service.py` with an `SSEEventManager` class
  - [x] Implement a module-level dict of `asyncio.Queue` per session_id for event broadcasting
  - [x] Implement `emit_event(session_id, event_type, payload, step_index=None)` — creates canonical SSE envelope and puts on queue
  - [x] Implement `subscribe(session_id)` → returns an async generator that yields SSE event strings
  - [x] Implement `unsubscribe(session_id)` to clean up queue on disconnect
  - [x] SSE envelope MUST match exactly: `{event_type, session_id, step_index, timestamp, payload}`
  - [x] Timestamp must be ISO 8601 format with "Z" suffix (not Unix timestamp)

- [x] Task 2: Implement the SSE stream endpoint (AC: 1, 4, 5)
  - [x] Replace stub in `handlers/sse_handler.py` with full `GET /api/stream/{session_id}` endpoint
  - [x] Change router prefix from `/events` to `/api` (architecture spec: `/api/stream/{session_id}`)
  - [x] Use FastAPI `StreamingResponse` with `media_type="text/event-stream"`
  - [x] Set response headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`
  - [x] Validate `session_id` exists in Firestore via `get_session()` BEFORE opening stream
  - [x] Return `404` with canonical error envelope for unknown `session_id`
  - [x] On client disconnect, clean up the session's SSE queue
  - [x] Send initial `:keepalive` comment on connection to establish SSE channel

- [x] Task 3: Wire SSE emission into the Planner flow (AC: 2)
  - [x] Update `routers/task_router.py` `start_task()` to emit `plan_ready` SSE event after Planner success
  - [x] Import and call `emit_event(session_id, "plan_ready", {"steps": step_plan["steps"], "task_summary": step_plan["task_summary"]})` after step plan is stored
  - [x] Emit `task_failed` SSE event on Planner failure (before returning error response)
  - [x] Ensure `plan_ready` event is emitted within the same request lifecycle (not in a background task) to meet the 500ms latency requirement (NFR4)

- [x] Task 4: Register SSE handler router in `main.py` (AC: 1)
  - [x] Import `sse_router` from `handlers.sse_handler` (already exported in `handlers/__init__.py`)
  - [x] Add `app.include_router(sse_router)` after the existing `task_router` registration

- [x] Task 5: Write unit tests (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/test_sse_handler.py`
  - [x] Test: `GET /api/stream/{valid_session_id}` → response content-type is `text/event-stream`
  - [x] Test: `GET /api/stream/{unknown_session_id}` → `404` with canonical error envelope
  - [x] Test: emitting a `plan_ready` event → SSE client receives valid JSON matching canonical envelope
  - [x] Test: SSE envelope has all required fields: `event_type`, `session_id`, `timestamp`, `payload`
  - [x] Test: `timestamp` field matches ISO 8601 format
  - [x] Test: `step_index` field is present (null for events without step context)
  - [x] Test: client disconnect → queue is cleaned up (no memory leak)
  - [x] Mock Firestore `get_session()` — do NOT make real Firestore calls in tests
  - [x] Use FastAPI `TestClient` with `httpx` `stream()` for SSE response testing

- [x] Task 6: Git commit (all files)
  - [x] `git add -A && git commit -m "feat(story-2.2): implement SSE stream endpoint for agent events"`

## Dev Notes

### ⚠️ CRITICAL: SSE Router Prefix Mismatch

The existing `sse_handler.py` stub uses `prefix="/events"` — **this is WRONG**. The architecture specifies `GET /api/stream/{session_id}`. You MUST change the prefix to `/api` and the route path to `/stream/{session_id}`.

**Correct:** `GET /api/stream/{session_id}`  
**Wrong (current stub):** `GET /events/...`

[Source: architecture/core-architectural-decisions.md → "API & Communication Patterns"]

### SSE Canonical Event Envelope — EXACT

Every SSE event MUST match this exact schema. Do NOT rename, add, or remove fields:

```json
{
  "event_type": "step_start | step_complete | step_error | plan_ready | awaiting_confirmation | awaiting_input | task_complete | task_failed",
  "session_id": "sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "step_index": 0,
  "timestamp": "2026-02-26T14:30:00.000Z",
  "payload": {}
}
```

**SSE event types** use `snake_case` verb_noun format:
- `step_start`, `step_complete`, `step_error`
- `plan_ready`
- `awaiting_confirmation`, `awaiting_input`
- `task_complete`, `task_failed`

[Source: architecture/implementation-patterns-consistency-rules.md → "Communication Patterns / SSE event envelope"]

### SSE Event Format Over the Wire

The SSE protocol requires events formatted as `data: <json>\n\n`. Use this exact format:

```
data: {"event_type":"plan_ready","session_id":"sess_abc123","step_index":null,"timestamp":"2026-02-26T14:30:00.000Z","payload":{"steps":[...],"task_summary":"..."}}\n\n
```

Each event is a single `data:` line followed by two newlines. Do NOT use the `event:` field in SSE — all events are sent on the default message channel and differentiated by the `event_type` field in the JSON payload.

### FastAPI SSE Implementation Pattern

Use `StreamingResponse` with an async generator:

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from services.session_service import get_session
from services.sse_service import subscribe, unsubscribe

router = APIRouter(prefix="/api")

@router.get("/stream/{session_id}")
async def stream_events(session_id: str):
    # Validate session exists
    session = await get_session(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": {"code": "SESSION_NOT_FOUND", "message": "Session not found"}},
        )

    async def event_generator():
        try:
            yield ": keepalive\n\n"  # SSE comment to establish connection
            async for event in subscribe(session_id):
                yield f"data: {event}\n\n"
        finally:
            unsubscribe(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Prevents nginx/proxy buffering
        },
    )
```

### SSE Event Manager Service Pattern

```python
# services/sse_service.py
import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

_event_queues: dict[str, list[asyncio.Queue]] = {}

def emit_event(session_id: str, event_type: str, payload: dict, step_index: int | None = None) -> None:
    """Broadcast an SSE event to all subscribers of a session."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    event = json.dumps({
        "event_type": event_type,
        "session_id": session_id,
        "step_index": step_index,
        "timestamp": timestamp,
        "payload": payload,
    })
    if session_id in _event_queues:
        for queue in _event_queues[session_id]:
            queue.put_nowait(event)

async def subscribe(session_id: str) -> AsyncGenerator[str, None]:
    """Subscribe to SSE events for a session. Yields JSON event strings."""
    queue: asyncio.Queue = asyncio.Queue()
    if session_id not in _event_queues:
        _event_queues[session_id] = []
    _event_queues[session_id].append(queue)
    try:
        while True:
            event = await queue.get()
            yield event
    except asyncio.CancelledError:
        pass

def unsubscribe(session_id: str) -> None:
    """Clean up all queues for a session on disconnect."""
    # Note: in practice, individual queue removal is needed for multi-client
    # For MVP (single session, NFR17), cleaning all queues is fine
    _event_queues.pop(session_id, None)
```

**Key design decisions:**
1. **Module-level dict of queues** — simple, no external dependencies (Redis not needed per NFR17: single session)
2. **List of queues per session** — supports reconnection (old queue cleaned up, new one created)
3. **`put_nowait()`** — non-blocking broadcast; if no subscribers, events are silently dropped (this is correct — if no one is listening, there's no one to receive)
4. **ISO 8601 timestamp** — same format as `session_service.py` uses for `created_at`

### API Response Envelope — Error Responses

For the `404` case, use the canonical error envelope:

```json
{"success": false, "data": null, "error": {"code": "SESSION_NOT_FOUND", "message": "Session not found"}}
```

[Source: architecture/implementation-patterns-consistency-rules.md → "Format Patterns / API response wrapper"]

### Existing Code to Modify (DO NOT RECREATE)

| File | Current State | Action |
|---|---|---|
| `handlers/sse_handler.py` | Stub with `prefix="/events"` and no routes | Replace entirely with full SSE endpoint; change prefix to `/api` |
| `routers/task_router.py` | Returns step plan in REST response only | Add `emit_event()` call after `plan_ready` status update |
| `main.py` | Only includes `task_router` | Add `app.include_router(sse_router)` |

### Files to Create

| File | Purpose |
|---|---|
| `services/sse_service.py` | `SSEEventManager` — event queues, `emit_event()`, `subscribe()`, `unsubscribe()` |
| `tests/test_sse_handler.py` | Unit tests for SSE endpoint and event manager |

### Dependencies — Already Installed

All required packages are already in `requirements.txt`:
- `fastapi>=0.115.0` — includes `StreamingResponse` for SSE
- `uvicorn[standard]>=0.34.0` — ASGI server (required for SSE streaming)

**No new dependencies needed** — SSE uses standard HTTP, no additional libraries required. Do NOT install `sse-starlette` or similar packages; FastAPI's built-in `StreamingResponse` is sufficient and keeps the dependency graph minimal.

### Error Handling Pattern

Per architecture enforcement guidelines:
- All unhandled exceptions in the SSE handler MUST be caught and logged — never propagate as HTML 500 pages
- If `emit_event()` fails (e.g., queue full), log a warning but do NOT crash the request handler
- The SSE generator MUST have a `finally` block for cleanup to prevent resource leaks

### ⚠️ Important: SSE and the POST /api/task/start Race Condition

The frontend calls `POST /api/task/start` first, then subscribes to SSE with the returned `session_id`. This means the `plan_ready` event might be emitted BEFORE the SSE client connects. To handle this:

1. The `POST /api/task/start` response already includes the full step plan in `response_data["step_plan"]` — the frontend can use this as the initial state
2. The SSE stream, upon reconnection, should emit the current state. For MVP, the frontend can hydrate from the REST response and then listen for subsequent events (step_start, step_complete, etc.) via SSE
3. Do NOT add a buffering/replay mechanism — this is unnecessary complexity for NFR17 (single session). The frontend gets the plan from REST and subsequent events from SSE

### Testing Guidance

- **Mock Firestore** — use `unittest.mock.patch` on `services.session_service.get_session`
- **Use `httpx.AsyncClient`** for SSE stream testing with FastAPI `TestClient`
- **Test the SSE service independently** — `emit_event()` and `subscribe()` can be tested without HTTP
- **Existing test patterns:** See `tests/test_task_router.py` for FastAPI test client setup and mocking patterns
- **Do NOT test SSE reconnection timing** — this adds flakiness; test that the endpoint accepts connections and that disconnection cleans up

### Previous Story Intelligence

**From Story 2.1 (Planner Agent) — Critical Learnings:**
- `genai.Client()` was being created per-call (connection churn) → was fixed to module-level singleton. Apply same pattern: do NOT create per-request resources
- `_validate_step_plan()` was missing type checks → validate ALL fields, not just existence
- Retry logic was retrying `ValueError` schema errors → separate retryable errors from validation errors
- Firestore update failures were silently swallowed → added `warnings` field to response data. SSE emit failures should follow the same pattern (log warning, don't crash)
- Tests had no-op assertions (always True) → ensure every assertion can actually fail

**From Story 2.1 — Reusable Patterns:**
- `_error_response()` helper in `task_router.py` — reuse for SSE 404 error
- `session_service.get_session()` — already exists, use to validate session_id
- ISO 8601 timestamp format: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"` — already used in `session_service.py`
- `handlers/__init__.py` already exports `sse_router` — just need to register in `main.py`

**From Epic 1 Retrospective:**
- Error handling gaps recurred in every story — ensure `try/except` on ALL async calls
- Code review found issues in every story — keep code simple and testable
- All REST responses use `{success, data, error}` envelope — the SSE 404 must use this too

### Git Intelligence (Recent Commits)

```
7de476e (HEAD -> master) fix(story-2.1): apply code review fixes
...
f004492 feat: Document CI/CD pipeline for Cloud Run and Firebase Hosting
```

Story 2.1 is fully committed with code review fixes applied. CI/CD is green.

### Project Structure Notes

- `handlers/sse_handler.py` is the canonical location for the SSE endpoint per architecture spec
- `services/sse_service.py` follows the established pattern of business logic in `services/`
- Tests go in `tests/test_sse_handler.py` (not co-located) per Python convention
- The `handlers/__init__.py` already exports `sse_router` — the import will work once `sse_handler.py` has a proper `router`

### NFR Compliance

- **NFR4:** Thinking panel → Executor sync lag < 500ms per step. The `emit_event()` call in the same request lifecycle meets this
- **NFR16:** SSE auto-reconnect on connection drop. This is a FRONTEND responsibility (Story 2.3), but the backend must accept new connections for the same session_id
- **NFR17:** Backend supports one active session reliably. The in-memory queue approach is sufficient — no Redis/external pub-sub needed

### References

- Story AC source: [epics.md](../../_bmad-output/planning-artifacts/epics.md) → "Story 2.2: SSE Stream Endpoint for Agent Events"
- SSE event envelope: [implementation-patterns-consistency-rules.md](../../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Communication Patterns / SSE event envelope"
- SSE event types: [implementation-patterns-consistency-rules.md](../../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Naming Patterns / SSE event types"
- API error envelope: [implementation-patterns-consistency-rules.md](../../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Format Patterns / API response wrapper"
- SSE endpoint path: [core-architectural-decisions.md](../../_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) → "API & Communication Patterns"
- SSE handler file: [project-structure-boundaries.md](../../_bmad-output/planning-artifacts/architecture/project-structure-boundaries.md) → "handlers/sse_handler.py"
- Data flow: [project-structure-boundaries.md](../../_bmad-output/planning-artifacts/architecture/project-structure-boundaries.md) → "Data Flow / sse_handler emits plan_ready SSE event"
- NFR4 latency: [epics.md](../../_bmad-output/planning-artifacts/epics.md) → "NFR4: Thinking panel → Executor sync lag < 500ms per step"
- NFR16 reconnect: [epics.md](../../_bmad-output/planning-artifacts/epics.md) → "NFR16: SSE auto-reconnect on connection drop"
- NFR17 single session: [epics.md](../../_bmad-output/planning-artifacts/epics.md) → "NFR17: Backend supports one active session reliably"
- Previous story: [2-1-planner-agent-with-canonical-step-plan-output.md](./2-1-planner-agent-with-canonical-step-plan-output.md) → code review learnings
- Session service: [session_service.py](../../aria-backend/services/session_service.py) → `get_session()` for validation
- Task router: [task_router.py](../../aria-backend/routers/task_router.py) → `start_task()` for SSE emission wiring

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Fixed hanging test `test_stream_valid_session_content_type` by mocking the infinite `subscribe` async generator with a finite generator yielding a single event, allowing the `StreamingResponse` to complete so tests don't timeout.

### Code Review Fixes Applied

- **Critical**: Reverted endpoint test to use finite generator mock so the stream can be verified without hanging tests. Added a dedicated `test_stream_integration_payload_formatting` to test actual HTTP stream payload formatting.
- **High**: Added `Authorization` header and `token` query param validation to `GET /api/stream/{session_id}`.
- **High**: Made the `subscribe()` generator securely break on terminal `task_complete` and `task_failed` events.
- **Medium**: Fixed concurrent `unsubscribe()` removing all queues by specifying the explicit queue reference.
- **Low**: Caught `asyncio.CancelledError` properly in the event generator.

### Completion Notes List

- ✅ 1. Created `services/sse_service.py` providing `SSEEventManager` backed by an active-client dict of `asyncio.Queue` lists
- ✅ 2. Replaced `handlers/sse_handler.py` stub with full `GET /api/stream/{session_id}` endpoint checking Firestore for session validity
- ✅ 3. Wired `plan_ready` and `task_failed` SSE event emission into `start_task` in `routers/task_router.py`
- ✅ 4. Wired `events` router into `main.py`
- ✅ 5. 9 `pytest` test cases authored matching all ACs, including queue disconnect cleanup checks

### File List

- `aria-backend/services/sse_service.py` (Added)
- `aria-backend/handlers/sse_handler.py` (Modified)
- `aria-backend/routers/task_router.py` (Modified)
- `aria-backend/main.py` (Modified)
- `aria-backend/tests/test_sse_handler.py` (Added)
