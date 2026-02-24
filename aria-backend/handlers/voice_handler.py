import os
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()

# Stub: WebSocket audio relay will be implemented in Story 4.1
router = APIRouter(prefix="/voice", tags=["voice"])
