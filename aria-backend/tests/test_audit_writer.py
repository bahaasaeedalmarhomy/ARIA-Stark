"""
Unit tests for handlers/audit_writer.py — Story 3.5.

Tests:
  1. write_audit_log appends step entry with all 8 required fields
  2. write_audit_log timestamp is ISO 8601 UTC with millisecond precision and Z suffix
  3. write_audit_log status is always "complete" regardless of input
  4. update_session_status delegates to session_service.update_session_status

AC coverage: AC 1
"""
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


_SESSION_ID = "sess_test-audit-001"
_STEP_DATA = {
    "action_type": "navigate",
    "description": "Go to URL",
    "result": "done",
    "screenshot_url": "https://storage.googleapis.com/bucket/sessions/sess/steps/0000.png",
    "confidence": 0.95,
}


def _make_mock_db():
    """Return a mock Firestore AsyncClient with collection/document/update wired up."""
    mock_doc_ref = AsyncMock()
    mock_doc_ref.update = AsyncMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection
    return mock_db, mock_doc_ref


# ─────────────────────────────── Test 1 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_write_audit_log_appends_step_entry():
    """
    write_audit_log calls doc_ref.update with ArrayUnion containing an entry
    that has all 8 required fields (AC: 1).
    """
    from google.cloud import firestore as real_firestore

    mock_db, mock_doc_ref = _make_mock_db()

    with patch("handlers.audit_writer._get_db", return_value=mock_db):
        from handlers.audit_writer import write_audit_log
        await write_audit_log(_SESSION_ID, 0, _STEP_DATA)

    mock_doc_ref.update.assert_called_once()
    update_arg = mock_doc_ref.update.call_args.args[0]
    assert "steps" in update_arg, f"Expected 'steps' key in update arg: {update_arg}"

    # Unwrap ArrayUnion to inspect the entry
    array_union = update_arg["steps"]
    assert isinstance(array_union, real_firestore.ArrayUnion), (
        f"Expected firestore.ArrayUnion, got {type(array_union)}"
    )
    entry_list = array_union.values if hasattr(array_union, "values") else list(array_union)
    assert len(entry_list) == 1, f"Expected 1 entry in ArrayUnion, got {len(entry_list)}"
    entry = entry_list[0]

    required_fields = [
        "step_index", "action_type", "description",
        "result", "screenshot_url", "confidence", "timestamp", "status",
    ]
    for field in required_fields:
        assert field in entry, f"Expected field '{field}' in entry: {entry}"

    assert entry["step_index"] == 0
    assert entry["action_type"] == "navigate"
    assert entry["description"] == "Go to URL"
    assert entry["result"] == "done"
    assert entry["screenshot_url"] == _STEP_DATA["screenshot_url"]
    assert entry["confidence"] == 0.95


# ─────────────────────────────── Test 2 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_write_audit_log_timestamp_is_iso8601_utc():
    """
    Timestamp in the audit entry must match format YYYY-MM-DDTHH:MM:SS.mmmZ (AC: 1).
    """
    from google.cloud import firestore as real_firestore

    mock_db, mock_doc_ref = _make_mock_db()

    with patch("handlers.audit_writer._get_db", return_value=mock_db):
        from handlers.audit_writer import write_audit_log
        await write_audit_log(_SESSION_ID, 0, _STEP_DATA)

    update_arg = mock_doc_ref.update.call_args.args[0]
    array_union = update_arg["steps"]
    entry_list = array_union.values if hasattr(array_union, "values") else list(array_union)
    entry = entry_list[0]

    ts = entry["timestamp"]
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
    assert re.match(pattern, ts), (
        f"Timestamp '{ts}' does not match ISO 8601 UTC format with ms precision"
    )


# ─────────────────────────────── Test 3 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_write_audit_log_status_is_always_complete():
    """
    status field in the audit entry is always "complete" — not controlled by caller (AC: 1).
    """
    from google.cloud import firestore as real_firestore

    mock_db, mock_doc_ref = _make_mock_db()

    with patch("handlers.audit_writer._get_db", return_value=mock_db):
        from handlers.audit_writer import write_audit_log
        # Pass a data dict that does NOT include "status"
        await write_audit_log(_SESSION_ID, 2, {"action_type": "click", "description": "Click btn"})

    update_arg = mock_doc_ref.update.call_args.args[0]
    array_union = update_arg["steps"]
    entry_list = array_union.values if hasattr(array_union, "values") else list(array_union)
    entry = entry_list[0]

    assert entry["status"] == "complete", f"Expected 'complete', got {entry['status']!r}"


# ─────────────────────────────── Test 4 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_update_session_status_delegates():
    """
    update_session_status in audit_writer MUST delegate to
    services.session_service.update_session_status (AC: wrapper pattern).
    """
    with patch(
        "services.session_service.update_session_status",
        new_callable=AsyncMock,
    ) as mock_delegate:
        from handlers.audit_writer import update_session_status
        await update_session_status(_SESSION_ID, "complete")

    mock_delegate.assert_called_once_with(_SESSION_ID, "complete")
