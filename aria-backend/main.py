import logging
import os
from contextlib import asynccontextmanager

import firebase_admin
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize Firebase Admin SDK and smoketest Playwright Chromium."""
    # Firebase Admin SDK — uses Application Default Credentials (ADC).
    # On Cloud Run: ADC provided by aria-backend-sa service account attachment.
    # Locally: run `gcloud auth application-default login` first.
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
        logger.info("Firebase Admin SDK initialized")

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Wrap Pydantic 422 errors in canonical {success, data, error} envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
        },
    )


@app.get("/healthz")
async def health_check():
    return {"success": True, "data": {"status": "ok"}, "error": None}


# Routers
from routers.task_router import router as task_router  # noqa: E402
app.include_router(task_router)
