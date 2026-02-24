import os
from dotenv import load_dotenv

load_dotenv()

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")

# Stub: GCS service will be implemented in Story 3.3
async def upload_screenshot(session_id: str, step_index: int, image_bytes: bytes) -> str:
    """Upload a screenshot to GCS. Stub implementation."""
    return ""
