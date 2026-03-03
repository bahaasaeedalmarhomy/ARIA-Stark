"""
WebSocket audio relay handler — Story 4.1

Routes:
  WS /ws/audio/{session_id}

Architecture: asyncio.Queue pass-through hot path.
  Browser → ws.receive_bytes() → inbound_queue.put() (hot path, no Gemini I/O)
  drain_queue_to_gemini() → gemini_session.send()  (separate task)
  gemini_session.receive() → ws.send_bytes()        (separate task)
"""
import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai

from services.session_service import get_session
from services.voice_service import create_audio_queue, release_audio_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["voice"])


# ---------------------------------------------------------------------------
# Relay coroutines
# ---------------------------------------------------------------------------


async def relay_inbound_to_queue(
    ws: WebSocket,
    queue: asyncio.Queue[bytes | None],
) -> None:
    """Read raw PCM bytes from the browser WebSocket and put them on the inbound queue.

    CRITICAL: No Gemini I/O here — pure pass-through to keep latency minimal.
    """
    try:
        while True:
            data = await ws.receive_bytes()
            queue.put_nowait(data)  # Non-blocking: queue is unbounded
    finally:
        # Signal drain_queue_to_gemini to stop when this coroutine exits
        queue.put_nowait(None)


async def drain_queue_to_gemini(
    queue: asyncio.Queue[bytes | None],
    gemini_session,
) -> None:
    """Drain the inbound queue and forward chunks to the Gemini Live session."""
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        await gemini_session.send(input=chunk, end_of_turn=False)


async def relay_gemini_to_browser(
    ws: WebSocket,
    gemini_session,
) -> None:
    """Receive audio bytes from Gemini Live and forward them immediately to the browser."""
    async for response in gemini_session.receive():
        if response.data:
            await ws.send_bytes(response.data)
        # response.text (transcription) intentionally ignored — handled in Story 4.2+


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/audio/{session_id}")
async def audio_relay(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional raw PCM audio relay between browser and Gemini Live API."""
    session = await get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    inbound_queue = create_audio_queue(session_id)

    voice_model = os.getenv("VOICE_MODEL", "gemini-2.0-flash-live-001")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set — cannot start voice relay for session %s", session_id)
        release_audio_queue(session_id)
        await websocket.close(code=4500, reason="Server configuration error")
        return
    client = genai.Client(api_key=api_key)
    config = genai.types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=genai.types.SpeechConfig(
            voice_config=genai.types.VoiceConfig(
                prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
    )

    tasks: list[asyncio.Task] = []
    try:
        async with client.aio.live.connect(model=voice_model, config=config) as gemini_session:
            tasks = [
                asyncio.create_task(relay_inbound_to_queue(websocket, inbound_queue)),
                asyncio.create_task(drain_queue_to_gemini(inbound_queue, gemini_session)),
                asyncio.create_task(relay_gemini_to_browser(websocket, gemini_session)),
            ]
            # On disconnect, relay_inbound_to_queue raises WebSocketDisconnect
            # which propagates immediately (no return_exceptions) so finally
            # block cancels remaining tasks and releases resources promptly.
            await asyncio.gather(*tasks)
    except WebSocketDisconnect:
        logger.warning("WebSocket disconnected for session %s", session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Voice relay error for session %s: %s", session_id, exc)
    finally:
        # Belt-and-suspenders: ensure drain can exit if not already signalled
        inbound_queue.put_nowait(None)
        for task in tasks:
            if not task.done():
                task.cancel()
        release_audio_queue(session_id)
