import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: smoketest Playwright Chromium launch. Non-fatal outside Docker."""
    try:
        from tools.playwright_computer import smoketest_playwright
        await smoketest_playwright()
        logger.info("Playwright Chromium smoketest passed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright smoketest skipped (browser binaries unavailable): %s", exc)
    yield


app = FastAPI(title="ARIA Backend", version="1.0.0", lifespan=lifespan)

# Support comma-separated origins: "http://localhost:3000,http://localhost:5173"
_cors_raw = os.getenv("CORS_ORIGIN", "http://localhost:3000")
cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


# Mount routers here in future stories:
# from handlers.sse_handler import router as sse_router
# from handlers.voice_handler import router as voice_router
# app.include_router(sse_router)
# app.include_router(voice_router)
