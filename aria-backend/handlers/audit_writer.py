import os
from dotenv import load_dotenv

load_dotenv()

# Stub: Firestore audit log writer will be implemented in Story 3.5
async def write_audit_log(session_id: str, step_index: int, data: dict) -> None:
    """Write an audit log entry to Firestore. Stub implementation."""
    pass
