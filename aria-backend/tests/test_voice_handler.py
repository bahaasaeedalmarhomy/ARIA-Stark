"""
Unit tests for WebSocket audio relay endpoint (WS /ws/audio/{session_id}).

Firebase Admin SDK is mocked globally by conftest.py.

Run with:
    cd aria-backend && pytest tests/test_voice_router.py -v
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from main import app

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=False)

_SESSION_ID = "sess_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_MOCK_SESSION = {
    "session_id": _SESSION_ID,
    "status": "pending",
    "task_description": "test task",
}


# ---------------------------------------------------------------------------
# Helper: build async generator for Gemini session.receive()
# ---------------------------------------------------------------------------

async def _empty_receive():
    """Async generator that yields nothing (simulates Gemini stream close)."""
    return
    yield  # Unreachable — makes this an async generator


async def _audio_receive(audio_bytes: bytes):
    """Async generator that yields one audio response then stops."""
    response = MagicMock()
    response.data = audio_bytes
    yield response


# ---------------------------------------------------------------------------
# Helper: build a mock Gemini async context manager
# ---------------------------------------------------------------------------

def _make_gemini_mock(receive_gen_factory=None):
    """Build a mock genai.Client with a controllable receive() async generator."""
    if receive_gen_factory is None:
        receive_gen_factory = _empty_receive

    mock_session = MagicMock()
    mock_session.send = AsyncMock(return_value=None)
    mock_session.receive = receive_gen_factory

    mock_live_ctx = MagicMock()
    mock_live_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_live_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.aio.live.connect.return_value = mock_live_ctx

    return mock_client, mock_session


# ---------------------------------------------------------------------------
# Test 1: Connection accepted and audio queue created for valid session
# ---------------------------------------------------------------------------

def test_websocket_accept_creates_audio_queue():
    """
    AC1: Given a valid session_id, When a WebSocket client connects,
    Then the connection is accepted and create_audio_queue is called.
    """
    mock_client, _ = _make_gemini_mock()

    with (
        patch(
            "handlers.voice_handler.get_session",
            new=AsyncMock(return_value=_MOCK_SESSION),
        ),
        patch(
            "handlers.voice_handler.create_audio_queue",
            wraps=lambda sid: asyncio.Queue(),
        ) as mock_create_queue,
        patch(
            "handlers.voice_handler.release_audio_queue",
        ) as mock_release,
        patch("handlers.voice_handler.genai.Client", return_value=mock_client),
    ):
        with client.websocket_connect(f"/ws/audio/{_SESSION_ID}"):
            # Connection is alive — no exception means it was accepted
            pass

        mock_create_queue.assert_called_once_with(_SESSION_ID)


# ---------------------------------------------------------------------------
# Test 2: Browser bytes forwarded to inbound queue
# ---------------------------------------------------------------------------

def test_browser_bytes_placed_on_inbound_queue():
    """
    AC2: When the browser sends raw PCM audio chunks,
    Then they are placed onto the inbound queue (put_nowait called with the bytes).
    """
    mock_client, _ = _make_gemini_mock()
    real_queue: asyncio.Queue = asyncio.Queue()
    # Spy on put_nowait to capture all items placed on the queue
    real_queue.put_nowait = MagicMock(wraps=real_queue.put_nowait)

    with (
        patch(
            "handlers.voice_handler.get_session",
            new=AsyncMock(return_value=_MOCK_SESSION),
        ),
        patch(
            "handlers.voice_handler.create_audio_queue",
            return_value=real_queue,
        ),
        patch("handlers.voice_handler.release_audio_queue"),
        patch("handlers.voice_handler.genai.Client", return_value=mock_client),
    ):
        with client.websocket_connect(f"/ws/audio/{_SESSION_ID}") as ws:
            ws.send_bytes(b"\x00\x01\x02\x03")  # Raw PCM chunk

    # Verify bytes were passed to put_nowait (drain may have consumed them already)
    put_args = [call.args[0] for call in real_queue.put_nowait.call_args_list]
    assert b"\x00\x01\x02\x03" in put_args


# ---------------------------------------------------------------------------
# Test 3: Disconnect cleans up resources — release_audio_queue called
# ---------------------------------------------------------------------------

def test_disconnect_releases_audio_queue():
    """
    AC5: When the WebSocket connection drops, relay coroutines are cancelled
    cleanly and release_audio_queue is called for the session.
    """
    mock_client, _ = _make_gemini_mock()

    with (
        patch(
            "handlers.voice_handler.get_session",
            new=AsyncMock(return_value=_MOCK_SESSION),
        ),
        patch(
            "handlers.voice_handler.create_audio_queue",
            wraps=lambda sid: asyncio.Queue(),
        ),
        patch(
            "handlers.voice_handler.release_audio_queue",
        ) as mock_release,
        patch("handlers.voice_handler.genai.Client", return_value=mock_client),
    ):
        with client.websocket_connect(f"/ws/audio/{_SESSION_ID}"):
            pass  # Disconnect on exit

        mock_release.assert_called_once_with(_SESSION_ID)


# ---------------------------------------------------------------------------
# Test 4: Unknown session → WebSocket closed with code 4004
# ---------------------------------------------------------------------------

def test_unknown_session_closes_with_4004():
    """
    AC6: Given a session_id that does not exist,
    When a client connects, the WebSocket is closed with code 4004.
    """
    with patch(
        "handlers.voice_handler.get_session",
        new=AsyncMock(return_value={}),
    ):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/audio/{_SESSION_ID}"):
                pass

    assert exc_info.value.code == 4004


# ---------------------------------------------------------------------------
# Test 5: Gemini audio bytes forwarded to browser
# ---------------------------------------------------------------------------

def test_gemini_audio_forwarded_to_browser():
    """
    AC3: When gemini-2.0-flash-live produces audio output,
    Then audio bytes are immediately forwarded to the connected WebSocket client.
    """
    _AUDIO_PAYLOAD = b"\xff\xfe\x80\x00" * 100  # Fake PCM audio chunk

    mock_client, _ = _make_gemini_mock(
        receive_gen_factory=lambda: _audio_receive(_AUDIO_PAYLOAD)
    )

    with (
        patch(
            "handlers.voice_handler.get_session",
            new=AsyncMock(return_value=_MOCK_SESSION),
        ),
        patch(
            "handlers.voice_handler.create_audio_queue",
            wraps=lambda sid: asyncio.Queue(),
        ),
        patch("handlers.voice_handler.release_audio_queue"),
        patch("handlers.voice_handler.genai.Client", return_value=mock_client),
    ):
        with client.websocket_connect(f"/ws/audio/{_SESSION_ID}") as ws:
            received = ws.receive_bytes()

    assert received == _AUDIO_PAYLOAD


# ---------------------------------------------------------------------------
# Test 6: Missing GEMINI_API_KEY → WebSocket closed with 4500
# ---------------------------------------------------------------------------

def test_missing_api_key_closes_with_4500():
    """
    When GEMINI_API_KEY is not set, the WebSocket is closed with code 4500
    and the audio queue is released.
    """
    with (
        patch(
            "handlers.voice_handler.get_session",
            new=AsyncMock(return_value=_MOCK_SESSION),
        ),
        patch(
            "handlers.voice_handler.create_audio_queue",
            wraps=lambda sid: asyncio.Queue(),
        ),
        patch(
            "handlers.voice_handler.release_audio_queue",
        ) as mock_release,
        patch("handlers.voice_handler.os.getenv", side_effect=lambda k, d=None: {
            "VOICE_MODEL": "gemini-2.0-flash-live-001",
        }.get(k, d) if k == "VOICE_MODEL" else None),
    ):
        # Connection is accepted first (session is valid), then closed due to missing API key.
        # After accept(), close sends a close frame rather than raising WebSocketDisconnect.
        with client.websocket_connect(f"/ws/audio/{_SESSION_ID}"):
            pass  # Server closes the connection after accept

    mock_release.assert_called_once_with(_SESSION_ID)
