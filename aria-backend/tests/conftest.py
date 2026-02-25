"""
Shared test fixtures for aria-backend.

Mocks Firebase Admin SDK at MODULE-LEVEL so it happens before ANY test module
imports `main` (which triggers lifespan → firebase_admin.initialize_app()).
"""
from unittest.mock import MagicMock, patch

# ──────────────────────────────────────────────────────────────────────────────
# Module-level patching — runs at import/collection time, before any test
# module's `from main import app` triggers Firebase Admin SDK init.
# ──────────────────────────────────────────────────────────────────────────────
import firebase_admin

# Trick: pre-populate _apps dict so the `if not firebase_admin._apps:` guard
# in main.py's lifespan sees it as already initialized.
firebase_admin._apps["[DEFAULT]"] = MagicMock()

# Also stub initialize_app so any call is a no-op.
firebase_admin.initialize_app = MagicMock()
