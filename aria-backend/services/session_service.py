import os
from dotenv import load_dotenv

load_dotenv()

# Stub: Session service will be implemented in Story 1.4
async def create_session(user_id: str) -> dict:
    """Create a new session. Stub implementation."""
    return {}


async def get_session(session_id: str) -> dict:
    """Retrieve a session by ID. Stub implementation."""
    return {}
