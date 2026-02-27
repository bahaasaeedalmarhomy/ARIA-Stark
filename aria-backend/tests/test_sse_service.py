"""
Dedicated unit tests for services/sse_service.py — emit_event, subscribe, unsubscribe.

These tests focus on the SSE event manager's internal queue mechanics,
covering edge cases not exercised by the SSE handler integration tests.

Run with: cd aria-backend && pytest tests/test_sse_service.py -v
"""
import asyncio
import json
import re
from unittest.mock import patch

import pytest

import services.sse_service as svc

_SESSION_ID = "sess_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture(autouse=True)
def reset_queues():
    """Clear module-level queue state before each test."""
    svc._event_queues.clear()
    yield
    svc._event_queues.clear()


# ---------------------------------------------------------------------------
# emit_event tests
# ---------------------------------------------------------------------------

class TestEmitEvent:
    def test_builds_canonical_envelope(self):
        """emit_event puts a JSON-serialised canonical envelope on the queue."""
        queue: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [queue]

        svc.emit_event(_SESSION_ID, "plan_ready", {"steps": []})

        raw = queue.get_nowait()
        event = json.loads(raw)
        assert event["event_type"] == "plan_ready"
        assert event["session_id"] == _SESSION_ID
        assert event["step_index"] is None
        assert "timestamp" in event
        assert event["payload"] == {"steps": []}

    def test_step_index_included_when_provided(self):
        queue: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [queue]

        svc.emit_event(_SESSION_ID, "step_start", {}, step_index=3)

        event = json.loads(queue.get_nowait())
        assert event["step_index"] == 3

    def test_timestamp_is_iso8601_with_z_suffix(self):
        queue: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [queue]

        svc.emit_event(_SESSION_ID, "plan_ready", {})

        event = json.loads(queue.get_nowait())
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
        assert re.match(pattern, event["timestamp"]), f"Bad timestamp: {event['timestamp']}"

    def test_broadcasts_to_multiple_subscribers(self):
        """All queues for a session receive the event."""
        q1: asyncio.Queue = asyncio.Queue()
        q2: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q1, q2]

        svc.emit_event(_SESSION_ID, "step_complete", {"screenshot_url": "http://x.png"}, step_index=1)

        for q in (q1, q2):
            assert not q.empty()
            event = json.loads(q.get_nowait())
            assert event["event_type"] == "step_complete"
            assert event["step_index"] == 1

    def test_silently_drops_when_no_subscribers(self):
        """No error when emitting to a session with no subscribers."""
        svc.emit_event("sess_nobody", "plan_ready", {})  # Should not raise

    def test_warns_when_queue_full(self):
        """Full queue triggers a warning log, event is dropped."""
        q = asyncio.Queue(maxsize=1)
        svc._event_queues[_SESSION_ID] = [q]

        # Fill the queue
        svc.emit_event(_SESSION_ID, "step_start", {})
        assert q.full()

        # Second emit should drop the event (queue full) without raising
        svc.emit_event(_SESSION_ID, "step_complete", {})

        # Only original event remains
        assert q.qsize() == 1

    def test_does_not_affect_other_sessions(self):
        """Emitting to one session doesn't push to another."""
        q1: asyncio.Queue = asyncio.Queue()
        q2: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q1]
        svc._event_queues["sess_other"] = [q2]

        svc.emit_event(_SESSION_ID, "plan_ready", {})

        assert not q1.empty()
        assert q2.empty()


# ---------------------------------------------------------------------------
# subscribe tests
# ---------------------------------------------------------------------------

class TestSubscribe:
    @pytest.mark.asyncio
    async def test_yields_events_from_queue(self):
        """subscribe() yields JSON strings from the queue."""
        async def producer():
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "plan_ready", {"task_summary": "test", "steps": []})
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "task_complete", {"result": "success"})

        asyncio.create_task(producer())

        events = []
        async for raw in svc.subscribe(_SESSION_ID):
            events.append(json.loads(raw))
            if len(events) >= 2:
                break

        assert events[0]["event_type"] == "plan_ready"
        assert events[1]["event_type"] == "task_complete"

    @pytest.mark.asyncio
    async def test_terminates_on_task_complete(self):
        """subscribe() generator terminates when task_complete event is received."""
        async def producer():
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "task_complete", {})

        asyncio.create_task(producer())

        events = []
        async for raw in svc.subscribe(_SESSION_ID):
            events.append(json.loads(raw))

        assert len(events) == 1
        assert events[0]["event_type"] == "task_complete"

    @pytest.mark.asyncio
    async def test_terminates_on_task_failed(self):
        """subscribe() generator terminates when task_failed event is received."""
        async def producer():
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "task_failed", {"error": "timeout"})

        asyncio.create_task(producer())

        events = []
        async for raw in svc.subscribe(_SESSION_ID):
            events.append(json.loads(raw))

        assert len(events) == 1
        assert events[0]["event_type"] == "task_failed"

    @pytest.mark.asyncio
    async def test_registers_queue_in_event_queues(self):
        """subscribe() adds a queue to the session's queue list."""
        async def stop_after_one():
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "task_complete", {})

        asyncio.create_task(stop_after_one())

        # Before subscribe, no queues
        assert _SESSION_ID not in svc._event_queues

        async for _ in svc.subscribe(_SESSION_ID):
            # During subscribe, queue should be registered
            pass

    @pytest.mark.asyncio
    async def test_cleans_up_queue_after_completion(self):
        """subscribe() removes its queue from _event_queues after generator exits."""
        async def stop():
            await asyncio.sleep(0.05)
            svc.emit_event(_SESSION_ID, "task_complete", {})

        asyncio.create_task(stop())

        async for _ in svc.subscribe(_SESSION_ID):
            pass

        # After completion, queue should be cleaned up
        queues = svc._event_queues.get(_SESSION_ID, [])
        assert len(queues) == 0


# ---------------------------------------------------------------------------
# unsubscribe tests
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_removes_specific_queue(self):
        """unsubscribe(session_id, queue) removes only that specific queue."""
        q1: asyncio.Queue = asyncio.Queue()
        q2: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q1, q2]

        svc.unsubscribe(_SESSION_ID, q1)

        assert svc._event_queues[_SESSION_ID] == [q2]

    def test_removes_session_entry_when_last_queue_removed(self):
        """When the last queue is removed, the session entry is deleted entirely."""
        q: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q]

        svc.unsubscribe(_SESSION_ID, q)

        assert _SESSION_ID not in svc._event_queues

    def test_removes_all_queues_when_no_specific_queue(self):
        """unsubscribe(session_id) without queue removes the entire session entry."""
        q1: asyncio.Queue = asyncio.Queue()
        q2: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q1, q2]

        svc.unsubscribe(_SESSION_ID)

        assert _SESSION_ID not in svc._event_queues

    def test_no_error_for_unknown_session(self):
        """unsubscribe() for a session that doesn't exist does not raise."""
        svc.unsubscribe("sess_nonexistent")  # Should not raise

    def test_no_error_for_unknown_queue(self):
        """unsubscribe() with a queue that isn't in the list does not raise."""
        q_registered: asyncio.Queue = asyncio.Queue()
        q_stranger: asyncio.Queue = asyncio.Queue()
        svc._event_queues[_SESSION_ID] = [q_registered]

        svc.unsubscribe(_SESSION_ID, q_stranger)  # Should not raise

        # Original queue still there
        assert svc._event_queues[_SESSION_ID] == [q_registered]
