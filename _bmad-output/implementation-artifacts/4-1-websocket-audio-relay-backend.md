# Story 4.1: WebSocket Audio Relay Backend

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a WebSocket endpoint that relays raw PCM audio between the browser and gemini-2.0-flash-live in real time,
So that the voice pipeline has a low-latency bidirectional audio channel with no buffering in the hot path.

## Acceptance Criteria

1. **Given** a `session_id` exists, **When** a WebSocket client connects to `/ws/audio/{session_id}`, **Then** the connection is accepted, an `asyncio.Queue` is created for inbound audio chunks, and the relay coroutines start.

2. **Given** the WebSocket relay is running, **When** the browser sends raw PCM audio chunks (16kHz, 16-bit, mono), **Then** the chunks are placed onto the inbound queue and forwarded to `gemini-2.0-flash-live` without JSON parsing, logging, or inspection in the relay path — pure pass-through (architecture audio relay queue pattern).

3. **Given** `gemini-2.0-flash-live` produces audio output (TTS narration), **When** audio bytes are received from the model, **Then** they are immediately forwarded to the connected WebSocket client without buffering.

4. **Given** the Gemini Live API round-trip, **When** measured end-to-end in streaming mode, **Then** the latency is 1–1.8 seconds from audio sent to first audio byte received back (NFR3) — this is an architecture mandate for raw PCM streaming only; any buffering or JSON re-encoding in the hot path will break this target.

5. **Given** the WebSocket connection drops unexpectedly, **When** the disconnect is detected, **Then** the relay coroutines are cancelled cleanly, the asyncio resources for that session are released, and there is no lingering per-session queue entry.

6. **Given** a `session_id` that does not exist in Firestore, **When** a WebSocket client attempts to connect to `/ws/audio/{session_id}`, **Then** the WebSocket is closed with code 4004 and reason `"Session not found"`.

## Tasks / Subtasks

- [x] Task 1: Create `aria-backend/services/voice_service.py` — per-session audio queue management (AC: 1, 5)
  - [x] Follow the same module-level dict pattern as `_cancel_flags` in `session_service.py`
  - [x] Add `_audio_queues: dict[str, asyncio.Queue[bytes | None]] = {}` (sentinel `None` signals shutdown)
  - [x] Implement `create_audio_queue(session_id: str) -> asyncio.Queue[bytes | None]`
    - Creates and stores a new `asyncio.Queue(maxsize=0)` (unbounded) for inbound audio chunks
    - Returns the queue for immediate use by the relay
  - [x] Implement `get_audio_queue(session_id: str) -> asyncio.Queue[bytes | None] | None`
    - Returns existing queue or `None` if not found
  - [x] Implement `release_audio_queue(session_id: str) -> None`
    - Pops the queue from the dict (no cleanup needed — caller must cancel coroutines first)
  - [x] Do NOT put Gemini client lifecycle in this service — keep it in `voice_handler.py` where the coroutines live

- [x] Task 2: Implement `aria-backend/handlers/voice_handler.py` — replace stub with full WebSocket relay (AC: 1–5)
  - [x] Replace stub content (`# Stub: WebSocket audio relay will be implemented in Story 4.1`) with full implementation
  - [x] Import: `fastapi.WebSocket`, `fastapi.WebSocketDisconnect`, `google.genai.Client`, `google.genai.types`, `asyncio`, `os`, `logging`
  - [x] Import: `services.session_service.get_session`, `services.voice_service.create_audio_queue`, `services.voice_service.release_audio_queue`
  - [x] Router is `APIRouter(prefix="/ws", tags=["voice"])` — already planned in stub, already exported in `handlers/__init__.py`
  - [x] WebSocket endpoint: `@router.websocket("/audio/{session_id}")`
  - [x] **Connection setup** (AC: 1, 6):
    ```python
    @router.websocket("/audio/{session_id}")
    async def audio_relay(websocket: WebSocket, session_id: str):
        session = await get_session(session_id)
        if not session:
            await websocket.close(code=4004, reason="Session not found")
            return
        await websocket.accept()
        inbound_queue = create_audio_queue(session_id)
    ```
  - [x] **Three concurrent asyncio tasks** — never `await` Gemini in the inbound hot path:
    1. `relay_inbound_to_queue(ws, queue)` — reads bytes from WebSocket, puts on queue via put_nowait(); signals shutdown with None sentinel in finally
    2. `drain_queue_to_gemini(queue, gemini_session)` — drains `inbound_queue` items and calls `await gemini_session.send(input=item, end_of_turn=False)`; exits on `None` sentinel
    3. `relay_gemini_to_browser(ws, gemini_session)` — `async for response in gemini_session.receive()`: extract audio bytes, `await ws.send_bytes(audio_bytes)` immediately
  - [x] **Gemini Live API session** (AC: 2, 3, 4):
    ```python
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    config = genai.types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=genai.types.SpeechConfig(
            voice_config=genai.types.VoiceConfig(
                prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )
    async with client.aio.live.connect(model="gemini-2.0-flash-live-001", config=config) as gemini_session:
        # start three coroutines here
    ```
  - [x] **Cleanup on disconnect** (AC: 5): wrap the three `asyncio.gather` tasks in a `try/except WebSocketDisconnect`; in `finally`: put `None` sentinel on inbound_queue, cancel all tasks, call `release_audio_queue(session_id)`
  - [x] Error handling: log exceptions at WARNING level; re-raise `WebSocketDisconnect` is NOT needed — `finally` handles it
  - [x] CRITICAL: No JSON parsing, no logging of audio content, no `await` on Gemini inside the receive-from-browser hot path (all Gemini I/O in separate tasks)

- [x] Task 3: Register voice_router in `aria-backend/main.py` (AC: 1)
  - [x] The voice_router is already exported from `handlers/__init__.py` (was added as part of Epic 4 prep)
  - [x] Add two lines to `main.py` after the existing SSE router registration:
    ```python
    from handlers import voice_router  # noqa: E402
    app.include_router(voice_router)
    ```
  - [x] The CORS middleware already allows all methods/headers — no CORS changes needed for WebSocket routes (WebSocket uses Upgrade: websocket, not standard CORS headers)

- [x] Task 4: Verify `google-genai` package availability and model name (AC: 2, 3)
  - [x] `google-genai` is a transitive dependency of `google-adk>=1.25.0` — already installed
  - [x] Confirm `google.genai.Client().aio.live.connect()` is available at ADK v1.25+ (it ships `google-genai>=0.8.0` which includes Live API)
  - [x] Model string: `"gemini-2.0-flash-live-001"` — this is the production stable Live API model (maps to architecture's `gemini-3-flash` branding; same mapping used for executor `"gemini-2.0-flash"`)
  - [x] If `gemini-2.0-flash-live-001` is not available in the project's GCP region, fall back to `"gemini-2.0-flash-exp"` — log a warning on startup
  - [x] Do NOT hardcode the model name — read from `VOICE_MODEL` env var with default `"gemini-2.0-flash-live-001"`

- [x] Task 5: Write tests — `aria-backend/tests/test_voice_router.py` (AC: 1, 5, 6)
  - [x] Use `pytest-anyio` (already in `requirements-dev.txt`) and `httpx` `AsyncClient` + `httpx_ws` for WebSocket testing OR use FastAPI `TestClient` WebSocket support
  - [x] **Test 1**: `GET /ws/audio/{valid_session_id}` — mock `get_session` returning a valid session dict; assert connection accepted and audio queue created
  - [x] **Test 2**: Browser sends bytes → assert `inbound_queue.put_nowait` was called (mock `create_audio_queue` to return a real `asyncio.Queue`, check it received the bytes)
  - [x] **Test 3**: Client disconnect → assert `release_audio_queue(session_id)` is called and tasks are cancelled without exception
  - [x] **Test 4**: `get_session` returns `{}` (not found) → assert WebSocket closed with code 4004
  - [x] **Test 5**: Audio bytes received from Gemini mock → assert `websocket.send_bytes` called with those bytes

## Dev Notes

### Architecture Pattern: asyncio.Queue Pass-Through

Per the architecture spec: *"Audio relay: asyncio.Queue pass-through in voice_handler.py — no audio inspection in hot path"*.

The hot path is: **browser → WebSocket receive → queue.put_nowait() — done**. A separate coroutine (`drain_queue_to_gemini`) drains the queue asynchronously to Gemini. This ensures the WebSocket receive loop is never blocked on Gemini I/O. The same pattern applies in reverse: Gemini `receive()` is in its own coroutine — it sends bytes directly with `ws.send_bytes()` without any transformation.

```
Browser  -->  ws.receive_bytes()  -->  inbound_queue.put_nowait()
                                              |
                             drain_queue_to_gemini() (separate task)
                                              |
                                    gemini_session.send(chunk)
                                              |
                              gemini_session.receive() --> ws.send_bytes()
```

### Gemini Live API Usage (`google.genai`)

The `google.genai` package is a transitive dependency of `google-adk>=1.25.0`. The Live API for real-time bidirectional streaming:

```python
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async with client.aio.live.connect(
    model="gemini-2.0-flash-live-001",
    config=genai.types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=genai.types.SpeechConfig(
            voice_config=genai.types.VoiceConfig(
                prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    ),
) as session:
    # Send audio chunks:
    await session.send(input=audio_bytes, end_of_turn=False)
    
    # Receive audio responses:
    async for response in session.receive():
        if response.data:  # audio bytes
            await ws.send_bytes(response.data)
        elif response.text:  # transcription or text response (can be sent via SSE)
            pass
```

**IMPORTANT**: `client.aio.live.connect()` is an async context manager — the Gemini Live session is scoped to the `async with` block. The WebSocket connection and the Gemini `async with` block must be co-aligned: both open when connection starts, both close on disconnect.

### Per-Session Resource Pattern

Follow the established pattern from `session_service.py`:

```python
# voice_service.py
import asyncio

_audio_queues: dict[str, asyncio.Queue[bytes | None]] = {}

def create_audio_queue(session_id: str) -> asyncio.Queue[bytes | None]:
    q: asyncio.Queue[bytes | None] = asyncio.Queue()
    _audio_queues[session_id] = q
    return q

def get_audio_queue(session_id: str) -> asyncio.Queue[bytes | None] | None:
    return _audio_queues.get(session_id)

def release_audio_queue(session_id: str) -> None:
    _audio_queues.pop(session_id, None)
```

The `None` sentinel is the shutdown signal: the relay puts `None` before cancelling tasks (prevents the drain coroutine blocking on queue forever after disconnect).

### FastAPI WebSocket + asyncio Task Management

Three concurrent tasks need to run until any one completes or an error occurs:

```python
tasks = await asyncio.gather(
    relay_inbound_to_queue(websocket, inbound_queue),
    drain_queue_to_gemini(inbound_queue, gemini_session),
    relay_gemini_to_browser(websocket, gemini_session),
    return_exceptions=True,
)
```

Use `return_exceptions=True` so one task failure doesn't cancel the others — let the `finally` block handle cleanup. On `WebSocketDisconnect`, all three tasks will naturally resolve (the WebSocket receive raises `WebSocketDisconnect`, and the Gemini async-for ends when the session is closed via context manager exit).

### Router Registration

The stub in `handlers/voice_handler.py` already has:
```python
router = APIRouter(prefix="/ws", tags=["voice"])
```

And `handlers/__init__.py` already exports `voice_router`. Only `main.py` needs two lines appended:
```python
from handlers import voice_router  # noqa: E402
app.include_router(voice_router)
```

After this, the WebSocket endpoint is served at `/ws/audio/{session_id}`.

### Model Name Note

The architecture spec says `gemini-3-flash` for voice model. In practice, the project maps:
- `gemini-3-flash` → `gemini-2.0-flash` (executor, currently running)
- `gemini-3-flash` Live API → `gemini-2.0-flash-live-001`

Read the model from `VOICE_MODEL` env var (`default="gemini-2.0-flash-live-001"`) for flexibility without code changes.

### Authentication Scope

Story 4.1 does NOT add authentication to the WebSocket endpoint. The `session_id` itself acts as a capability token (if you know the session UUID you can connect). Story 4.2+ can add query-param token auth. This matches the `/{session_id}/input` endpoint pattern from Story 3.4 which also uses session_id as an implicit capability token.

### Test Strategy

The Gemini Live API is external — mock `client.aio.live.connect()` using `unittest.mock.AsyncMock` with an async context manager mock. The key behaviors to test are:
1. WebSocket accept + queue creation
2. Bytes flow from browser to queue (not to Gemini — that's mocked)
3. Cleanup on disconnect (release_audio_queue called)
4. 4004 close on unknown session

### Baseline Test Counts

After Story 3.6: **164 backend tests pass**, **129 frontend tests pass** (per test-summary.md). Story 4.1 adds 5 backend tests. Frontend tests unchanged (no frontend work in this story).

### Project Structure Notes

- `aria-backend/services/voice_service.py` — **new**: per-session audio queue management
- `aria-backend/handlers/voice_handler.py` — **implement**: replace stub with WebSocket relay
- `aria-backend/main.py` — **modify**: add 2 lines to register `voice_router`
- `aria-backend/tests/test_voice_router.py` — **new**: 5 WebSocket relay tests
- Other files: no changes required

### References

- [Source: aria-backend/handlers/voice_handler.py] — Stub to implement (Task 2)
- [Source: aria-backend/handlers/__init__.py] — voice_router already exported (Task 3)
- [Source: aria-backend/main.py] — Where to register voice_router (Task 3)
- [Source: aria-backend/services/session_service.py#_cancel_flags] — Resource dict pattern for Task 1
- [Source: aria-backend/services/session_service.py#get_session] — Import for session existence check (Task 2)
- [Source: aria-backend/agents/executor_agent.py] — Model name mapping pattern (gemini-3-flash → gemini-2.0-flash)
- [Source: aria-frontend/src/lib/store/aria-store.ts#VoiceSlice] — voiceStatus values: "idle" | "connecting" | "listening" | "speaking" | "paused" | "disconnected" (referenced in AC 5, updated by Story 4.2's frontend hook)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1] — Epic story definition, ACs, FRs
- [Source: _bmad-output/implementation-artifacts/3-6-audit-log-viewer-ui-and-task-cancel.md] — Previous story completion notes, test count baseline

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Test 2 initially failed: bytes consumed by `drain_queue_to_gemini` before assertion. Fixed by switching to `put_nowait` (non-blocking, since queue is unbounded) and spying on the method via `MagicMock(wraps=...)` to capture all calls regardless of consumption.
- `google.genai` import is slow (~30s) on first load due to `lark`/`rfc3987_syntax` grammar parsing in transitive deps; no action needed — tests pass once import completes.

### Completion Notes List

- Created `aria-backend/services/voice_service.py` with module-level `_audio_queues` dict following `_cancel_flags` pattern from `session_service.py`. Implements `create_audio_queue`, `get_audio_queue`, `release_audio_queue`.
- Replaced stub in `aria-backend/handlers/voice_handler.py` with full WebSocket relay: router prefix changed from `/voice` to `/ws`, three concurrent coroutines (`relay_inbound_to_queue`, `drain_queue_to_gemini`, `relay_gemini_to_browser`) gathered with `return_exceptions=True`. Hot path uses `put_nowait` (no Gemini I/O). `relay_inbound_to_queue` puts `None` sentinel in its own `finally` to cleanly signal drain. Belt-and-suspenders `None` also put in handler's `finally`.
- Registered `voice_router` in `aria-backend/main.py` (2 lines after SSE router).
- Verified `google-genai` is available as transitive dep of `google-adk>=1.25.0`. `VOICE_MODEL` env var used (default `gemini-2.0-flash-live-001`).
- 5 new tests in `aria-backend/tests/test_voice_router.py` using FastAPI `TestClient` WebSocket support with mocked Gemini client (async context manager mock + async generator for receive()). All 5 pass. Full suite: **169 tests pass**, no regressions.
### Senior Developer Review (AI) — 2026-03-03

**Reviewer**: Claude Opus 4.6 (adversarial code review)

**Findings**: 2 HIGH, 2 MEDIUM, 4 LOW — all fixed automatically.

| # | Severity | Finding | Fix Applied |
|---|---|---|---|
| 1 | HIGH | `return_exceptions=True` in `asyncio.gather` causes infinite hang on disconnect when `relay_gemini_to_browser` blocks on receive | Removed `return_exceptions=True`; exceptions now propagate to `except`/`finally` immediately |
| 2 | HIGH | `except WebSocketDisconnect` handler unreachable (dead code) with `return_exceptions=True` | Fixed by #1 — handler now reachable |
| 3 | MEDIUM | Task exceptions silently swallowed (gather return values never inspected) | Fixed by #1 — exceptions propagate naturally |
| 4 | MEDIUM | No `GEMINI_API_KEY` validation — `None` passed to SDK produces confusing error | Added early check: closes with 4500 + releases queue if unset |
| 5 | LOW | `asyncio.ensure_future()` is legacy API | Replaced with `asyncio.create_task()` |
| 6 | LOW | `response.text` from Gemini silently ignored without comment | Added clarifying comment |
| 7 | LOW | `create_audio_queue` silently overwrites existing queue | Added `logger.warning` for overwrite case |
| 8 | LOW | Test file named `test_voice_router.py` vs architecture spec `test_voice_handler.py` | Renamed to match spec |

**Additional test added**: `test_missing_api_key_closes_with_4500` (test 6)
**Final count**: 170 tests passing, 0 regressions
### File List

- `aria-backend/services/voice_service.py` — **new**: per-session audio queue management
- `aria-backend/handlers/voice_handler.py` — **modified**: full WebSocket relay replaces stub
- `aria-backend/main.py` — **modified**: registered voice_router
- `aria-backend/tests/test_voice_handler.py` — **new**: 6 WebSocket relay tests (renamed from test_voice_router.py per architecture spec)

### Change Log

- Story 4.1 implemented: WebSocket audio relay backend — 4 files changed/created, 5 tests added, 169 total tests passing (Date: 2026-03-03)
- Code review fixes applied (Date: 2026-03-03):
  - **HIGH**: Removed `return_exceptions=True` from `asyncio.gather` — prevented infinite hang on disconnect when Gemini receive was blocked
  - **HIGH**: `except WebSocketDisconnect` handler now reachable (was dead code with return_exceptions=True)
  - **MEDIUM**: Task exceptions now propagate instead of being silently swallowed
  - **MEDIUM**: Added `GEMINI_API_KEY` validation — closes with 4500 if unset instead of cryptic SDK error
  - **LOW**: Replaced `asyncio.ensure_future()` with `asyncio.create_task()` (modern API)
  - **LOW**: Added comment documenting intentional `response.text` ignore in relay_gemini_to_browser
  - **LOW**: Added warning log for audio queue overwrite on rapid reconnect
  - **LOW**: Renamed test file from `test_voice_router.py` to `test_voice_handler.py` per architecture spec
  - Added test 6: `test_missing_api_key_closes_with_4500`
  - Total: 170 tests passing, 0 regressions

