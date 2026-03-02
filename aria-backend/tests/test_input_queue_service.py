"""
Unit tests for input_queue_service — Story 3.4: Error Handling, CAPTCHA Pause, Input Resume.

AC coverage:
  AC 4 (user input delivery via queue) : all tests below
"""
import asyncio
import pytest

from services.input_queue_service import (
    clear_input_queue,
    get_input_queue,
    has_input_queue,
    put_user_input,
)


def _cleanup(*session_ids: str) -> None:
    """Remove test session queues to prevent test cross-contamination."""
    for sid in session_ids:
        clear_input_queue(sid)


# ──────────────────────────────────────────────────────────────────────────────
# get_input_queue
# ──────────────────────────────────────────────────────────────────────────────

def test_get_input_queue_creates_queue_lazily():
    """get_input_queue creates an asyncio.Queue when called the first time."""
    sid = "test-lazy-create"
    _cleanup(sid)
    try:
        queue = get_input_queue(sid)
        assert isinstance(queue, asyncio.Queue)
    finally:
        _cleanup(sid)


def test_get_input_queue_returns_same_instance_on_subsequent_calls():
    """Consecutive get_input_queue calls for the same session_id return the same queue."""
    sid = "test-same-instance"
    _cleanup(sid)
    try:
        q1 = get_input_queue(sid)
        q2 = get_input_queue(sid)
        assert q1 is q2, "Expected the same queue object to be returned on subsequent calls"
    finally:
        _cleanup(sid)


# ──────────────────────────────────────────────────────────────────────────────
# put_user_input
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_put_user_input_populates_queue():
    """put_user_input enqueues the value so queue.get() returns it."""
    sid = "test-put-input"
    _cleanup(sid)
    try:
        put_user_input(sid, "my response")
        queue = get_input_queue(sid)
        value = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert value == "my response"
    finally:
        _cleanup(sid)


@pytest.mark.asyncio
async def test_put_user_input_creates_queue_if_absent():
    """put_user_input creates the queue if it does not exist yet."""
    sid = "test-put-creates-queue"
    _cleanup(sid)
    try:
        assert not has_input_queue(sid), "Queue should not exist before put_user_input"
        put_user_input(sid, "hello")
        # Queue must now exist and contain the value
        assert has_input_queue(sid)
        value = await asyncio.wait_for(get_input_queue(sid).get(), timeout=1.0)
        assert value == "hello"
    finally:
        _cleanup(sid)


# ──────────────────────────────────────────────────────────────────────────────
# clear_input_queue
# ──────────────────────────────────────────────────────────────────────────────

def test_clear_input_queue_removes_queue():
    """clear_input_queue removes the queue so has_input_queue returns False."""
    sid = "test-clear"
    get_input_queue(sid)  # create
    assert has_input_queue(sid)
    clear_input_queue(sid)
    assert not has_input_queue(sid)


def test_clear_input_queue_no_op_when_queue_absent():
    """clear_input_queue is safe to call even when no queue exists (no exception)."""
    sid = "test-clear-absent"
    _cleanup(sid)
    try:
        clear_input_queue(sid)  # Must not raise
    finally:
        _cleanup(sid)


# ──────────────────────────────────────────────────────────────────────────────
# has_input_queue
# ──────────────────────────────────────────────────────────────────────────────

def test_has_input_queue_false_before_creation():
    """has_input_queue returns False before any queue is created for the session."""
    sid = "test-has-before"
    _cleanup(sid)
    try:
        assert not has_input_queue(sid)
    finally:
        _cleanup(sid)


def test_has_input_queue_true_after_creation():
    """has_input_queue returns True after get_input_queue is called once."""
    sid = "test-has-after"
    _cleanup(sid)
    try:
        get_input_queue(sid)
        assert has_input_queue(sid)
    finally:
        _cleanup(sid)


def test_has_input_queue_false_after_clear():
    """has_input_queue returns False after clear_input_queue is called."""
    sid = "test-has-after-clear"
    _cleanup(sid)
    try:
        get_input_queue(sid)
        clear_input_queue(sid)
        assert not has_input_queue(sid)
    finally:
        _cleanup(sid)


# ──────────────────────────────────────────────────────────────────────────────
# Session isolation
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_different_sessions_have_independent_queues():
    """Queues for different session_ids are fully independent."""
    sid1 = "test-isolation-1"
    sid2 = "test-isolation-2"
    _cleanup(sid1, sid2)
    try:
        put_user_input(sid1, "message-for-1")
        put_user_input(sid2, "message-for-2")

        val1 = await asyncio.wait_for(get_input_queue(sid1).get(), timeout=1.0)
        val2 = await asyncio.wait_for(get_input_queue(sid2).get(), timeout=1.0)

        assert val1 == "message-for-1"
        assert val2 == "message-for-2"
    finally:
        _cleanup(sid1, sid2)
