"""
Unit tests for voice_instruction_service — Story 4.4 review fixes.

Tests the per-session asyncio.Queue used for delivering voice transcriptions
to the re-plan endpoint after a barge-in pause.
"""
import asyncio

import pytest

from services.voice_instruction_service import (
    create_voice_instruction_queue,
    get_instruction,
    release_voice_instruction_queue,
    try_put_instruction,
)


# ---------------------------------------------------------------------------
# Queue lifecycle tests
# ---------------------------------------------------------------------------


def test_basic_put_and_get():
    """create → put → get returns the instruction."""
    sid = "sess_vis_basic"
    create_voice_instruction_queue(sid)
    try_put_instruction(sid, "go back")

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(get_instruction(sid, timeout=1.0))
    loop.close()
    assert result == "go back"
    release_voice_instruction_queue(sid)


def test_put_no_queue_silently_drops():
    """try_put_instruction is a no-op when no queue exists."""
    try_put_instruction("nonexistent_session_vis", "hello")  # must not raise


def test_put_queue_full_silently_drops():
    """Second put is silently dropped when queue is full (maxsize=1)."""
    sid = "sess_vis_full"
    create_voice_instruction_queue(sid)
    try_put_instruction(sid, "first")
    try_put_instruction(sid, "second")  # should silently drop

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(get_instruction(sid, timeout=1.0))
    loop.close()
    assert result == "first"
    release_voice_instruction_queue(sid)


@pytest.mark.asyncio
async def test_get_instruction_timeout():
    """get_instruction returns None on timeout."""
    sid = "sess_vis_timeout"
    create_voice_instruction_queue(sid)
    result = await get_instruction(sid, timeout=0.1)
    assert result is None
    release_voice_instruction_queue(sid)


@pytest.mark.asyncio
async def test_get_instruction_no_queue():
    """get_instruction returns None when no queue exists."""
    result = await get_instruction("nonexistent_session_vis2", timeout=0.1)
    assert result is None


def test_release_prevents_future_puts():
    """After release, try_put_instruction silently drops."""
    sid = "sess_vis_release"
    create_voice_instruction_queue(sid)
    release_voice_instruction_queue(sid)
    try_put_instruction(sid, "should drop")  # must not raise


# ---------------------------------------------------------------------------
# Browser instance storage tests (session_service helpers)
# ---------------------------------------------------------------------------


def test_set_and_get_browser_instance():
    """set_browser_instance stores and get_browser_instance retrieves + removes."""
    from services.session_service import get_browser_instance, set_browser_instance

    sid = "sess_browser_inst_test"
    mock_pc = object()  # any object
    set_browser_instance(sid, mock_pc)
    result = get_browser_instance(sid)
    assert result is mock_pc
    # Second get should return None (pop semantics)
    assert get_browser_instance(sid) is None


def test_get_browser_instance_missing():
    """get_browser_instance returns None for unknown session."""
    from services.session_service import get_browser_instance

    assert get_browser_instance("nonexistent_browser_inst") is None
