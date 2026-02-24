import os
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()

# Stub: SSE stream endpoint will be implemented in Story 2.2
router = APIRouter(prefix="/events", tags=["events"])
