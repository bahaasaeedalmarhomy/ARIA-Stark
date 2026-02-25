"""
Unit tests for services/session_service.py — verifying create_session()
produces a Firestore document with the correct fields (AC4).

Run with: cd aria-backend && pytest tests/test_session_service.py -v
"""
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_session_returns_session_id_and_stream_url():
    """create_session returns dict with session_id (sess_ prefix) and stream_url."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.set = AsyncMock()

    mock_collection = MagicMock()
    mock_collection.document = MagicMock(return_value=mock_doc_ref)

    mock_db = MagicMock()
    mock_db.collection = MagicMock(return_value=mock_collection)

    with patch("services.session_service._get_db", return_value=mock_db):
        from services.session_service import create_session

        result = await create_session("test-uid-abc", "Search for cats")

    assert "session_id" in result
    assert result["session_id"].startswith("sess_")
    assert "stream_url" in result
    assert result["stream_url"] == f"/api/stream/{result['session_id']}"


@pytest.mark.asyncio
async def test_create_session_firestore_document_has_correct_fields():
    """Firestore doc must contain: session_id, uid, task_description, status, created_at, steps."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.set = AsyncMock()

    mock_collection = MagicMock()
    mock_collection.document = MagicMock(return_value=mock_doc_ref)

    mock_db = MagicMock()
    mock_db.collection = MagicMock(return_value=mock_collection)

    with patch("services.session_service._get_db", return_value=mock_db):
        from services.session_service import create_session

        await create_session("uid-xyz", "Book a flight")

    # Verify Firestore .set() was called exactly once
    mock_doc_ref.set.assert_awaited_once()
    doc_data = mock_doc_ref.set.call_args[0][0]

    # Required fields per AC4
    assert doc_data["uid"] == "uid-xyz"
    assert doc_data["task_description"] == "Book a flight"
    assert doc_data["status"] == "pending"
    assert doc_data["steps"] == []

    # session_id: sess_ prefix + UUID4 format
    pattern = r"^sess_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(pattern, doc_data["session_id"]), f"Invalid session_id: {doc_data['session_id']}"

    # created_at: ISO 8601 with Z suffix
    assert doc_data["created_at"].endswith("Z")
    assert "T" in doc_data["created_at"]


@pytest.mark.asyncio
async def test_create_session_document_path_is_correct():
    """Firestore document must be created at sessions/{session_id}."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.set = AsyncMock()

    mock_collection = MagicMock()
    mock_collection.document = MagicMock(return_value=mock_doc_ref)

    mock_db = MagicMock()
    mock_db.collection = MagicMock(return_value=mock_collection)

    with patch("services.session_service._get_db", return_value=mock_db):
        from services.session_service import create_session

        result = await create_session("uid-123", "Test task")

    # Verify collection path
    mock_db.collection.assert_called_once_with("sessions")
    # Verify document ID matches session_id
    mock_collection.document.assert_called_once_with(result["session_id"])
