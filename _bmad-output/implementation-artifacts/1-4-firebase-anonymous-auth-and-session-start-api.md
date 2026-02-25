# Story 1.4: Firebase Anonymous Auth and Session Start API

Status: done

## Story

As a user,
I want the application to silently authenticate me and create a session when I arrive,
so that my task data is isolated to my session without requiring me to sign up or log in.

## Acceptance Criteria

1. **Given** a user opens the ARIA frontend, **When** the page loads, **Then** Firebase `signInAnonymously()` is called automatically, a uid is obtained, and a JWT `idToken` is stored in the Zustand session slice.

2. **Given** a valid `idToken` is available, **When** `POST /api/task/start` is called with `{"task_description": "test task"}` and `Authorization: Bearer {idToken}`, **Then** the backend verifies the Firebase ID token, creates a Firestore document in `sessions/{session_id}` scoped to the uid, and returns `{"success": true, "data": {"session_id": "sess_{uuid4}", "stream_url": "/api/stream/{session_id}"}}`.

3. **Given** `POST /api/task/start` is called without a valid token, **When** the request is received, **Then** the response is `401 Unauthorized` with `{"success": false, "data": null, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}}`.

4. **Given** a session is created, **When** the Firestore document is inspected, **Then** it contains `session_id`, `uid`, `created_at` (ISO 8601), `task_description`, and `status: "pending"`.

## Tasks / Subtasks

- [x] Task 1: Implement `aria-frontend/src/lib/firebase.ts` (AC: 1)
  - [x] Replace stub with real Firebase app init and auth export
  - [x] Import `initializeApp`, `getApp`, `getApps` from `firebase/app`
  - [x] Import `getAuth` from `firebase/auth`
  - [x] Use all 6 `NEXT_PUBLIC_FIREBASE_*` env vars in `firebaseConfig`
  - [x] Export `app` (singleton using `getApps().length` guard) and `auth`

- [x] Task 2: Add `uid` and `idToken` fields to Zustand session slice (AC: 1)
  - [x] In `aria-frontend/src/lib/store/aria-store.ts`, add `uid: string | null` and `idToken: string | null` to `SessionSlice` interface
  - [x] Initialize both to `null` in `immer` store body
  - [x] Keep existing `sessionId`, `taskStatus`, `taskDescription` fields — do NOT remove them

- [x] Task 3: Implement auto sign-in in `aria-frontend/src/app/layout.tsx` (AC: 1)
  - [x] Import `auth` from `@/lib/firebase`
  - [x] Import `signInAnonymously`, `onAuthStateChanged` from `firebase/auth`
  - [x] Import `useARIAStore` from `@/lib/store/aria-store`
  - [x] In a `useEffect` (or equivalent client component), call `signInAnonymously(auth)` once on mount
  - [x] On auth state change via `onAuthStateChanged`, call `user.getIdToken()` and update Zustand: set `uid = user.uid`, `idToken = idToken`
  - [x] **Must be "use client"** component — Firebase Auth uses browser APIs
  - [x] **Do NOT** block rendering while auth is pending — render UI optimistically; session start button is held back by `idToken === null` until auth completes

- [x] Task 4: Create `aria-frontend/src/lib/api/task.ts` (AC: 2)
  - [x] Create (or update) the `task.ts` API wrapper file
  - [x] Implement `startTask(taskDescription: string, idToken: string): Promise<StartTaskResponse>`:
    - URL: `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/task/start`
    - Method: `POST`
    - Headers: `Content-Type: application/json`, `Authorization: Bearer {idToken}`
    - Body: `JSON.stringify({ task_description: taskDescription })`
    - Returns the full `{ success, data, error }` envelope typed as `StartTaskResponse`
  - [x] Define `StartTaskResponse` type in `aria-frontend/src/types/aria.ts`:
    ```typescript
    export interface StartTaskData {
      session_id: string;
      stream_url: string;
    }
    export interface StartTaskResponse {
      success: boolean;
      data: StartTaskData | null;
      error: { code: string; message: string } | null;
    }
    ```

- [x] Task 5: Implement backend `POST /api/task/start` route (AC: 2, 3, 4)
  - [x] Create `aria-backend/services/session_service.py`:
    - Implement `create_session(uid: str, task_description: str) -> dict`:
      - Generates `session_id = "sess_" + str(uuid.uuid4())`
      - Creates Firestore document at `sessions/{session_id}` via Firebase Admin SDK with fields: `session_id`, `uid`, `task_description`, `status="pending"`, `created_at=datetime.utcnow().isoformat() + "Z"`, `steps=[]`
      - Returns `{"session_id": session_id, "stream_url": f"/api/stream/{session_id}"}`
  - [x] Create `aria-backend/routers/task_router.py`:
    - Define FastAPI `APIRouter` with prefix `/api/task`
    - Implement `POST /start` route handler:
      - Parse `Authorization: Bearer {idToken}` header — return `401` if missing
      - Call Firebase Admin SDK `auth.verify_id_token(id_token)` — return `401` with `UNAUTHORIZED` error code if invalid/expired
      - Extract `uid` from decoded token
      - Call `create_session(uid, task_description)` from `session_service`
      - Return `{"success": True, "data": {...}, "error": None}` with HTTP 200
    - Use the canonical response envelope for ALL responses (success and error)
  - [x] Update `aria-backend/main.py`:
    - Import and mount `task_router` with `app.include_router(task_router)`
    - Initialize Firebase Admin SDK in `lifespan` context (if not already initialized): `firebase_admin.initialize_app()` — uses Application Default Credentials automatically on Cloud Run
  - [x] Install Firebase Admin SDK: add `firebase-admin` to `aria-backend/requirements.txt`

- [x] Task 6: Install Firebase Admin SDK and verify Firestore writes (AC: 4)
  - [x] From `aria-backend/`, run `pip install firebase-admin` and update `requirements.txt`
  - [x] Confirm `google-cloud-firestore` is also in requirements (Firebase Admin pulls it transitively, but pin it)
  - [x] For local dev: `gcloud auth application-default login` provides ADC — no `GOOGLE_APPLICATION_CREDENTIALS` file needed locally
  - [x] Test locally: start backend, call `POST /api/task/start` with a valid Firebase idToken — check Firestore Console to verify document appears at `sessions/{session_id}`

- [x] Task 7: End-to-end validation (AC: 1–4)
  - [x] Start frontend (`npm run dev`), open browser devtools → Application → Firebase Auth → confirm anonymous user uid appears
  - [x] Confirm Zustand store shows `uid` and `idToken` set (React DevTools or `window.__ARIA_STORE__` debug)
  - [x] Start backend (`uvicorn main:app --reload --port 8080`), make manual `POST /api/task/start` with `Authorization: Bearer {idToken}` — expect 200 + `session_id`
  - [x] Check Firestore Console → `sessions` collection → confirm document with correct fields and `status: "pending"`
  - [x] Test 401: call `POST /api/task/start` with no Authorization header — expect `{"success": false, "data": null, "error": {"code": "UNAUTHORIZED", ...}}`
  - [x] Test 401: call with a forged token — expect same 401 response
  - [x] Run `npm run build` in `aria-frontend/` — must complete with 0 errors

## Dev Notes

### Critical Architecture Requirements — DO NOT DEVIATE

1. **Firebase app singleton pattern** — `initializeApp` must use the `getApps().length ? getApp() : initializeApp(config)` guard to prevent `FirebaseError: Firebase App named '[DEFAULT]' already exists` in hot-reload environments (Next.js dev server re-imports modules):
   ```typescript
   // aria-frontend/src/lib/firebase.ts
   import { initializeApp, getApps, getApp } from "firebase/app";
   import { getAuth } from "firebase/auth";

   const firebaseConfig = {
     apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
     authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
     projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
     storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
     messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
     appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
   };

   export const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
   export const auth = getAuth(app);
   ```

2. **All 6 Firebase config fields are required** — `messagingSenderId` and `appId` look optional but Firebase Auth silently fails without them. All 6 `NEXT_PUBLIC_FIREBASE_*` env vars must be in `aria-frontend/.env.local`.

3. **Firebase Admin SDK uses Application Default Credentials (ADC)** — `firebase_admin.initialize_app()` with no arguments uses ADC automatically. On Cloud Run, ADC is provided by the `aria-backend-sa` service account (attached to Cloud Run in Story 1.3). Locally, run `gcloud auth application-default login`. Do NOT hardcode `GOOGLE_APPLICATION_CREDENTIALS` or service account keys in any file.

4. **`idToken` has a 1-hour TTL** — `user.getIdToken(false)` returns the cached token if not expired; `user.getIdToken(true)` forces refresh. For the hackathon MVP, `getIdToken(false)` is sufficient. If the token is expired when `startTask` is called, Firebase Auth automatically refreshes it before returning.

5. **`onAuthStateChanged` vs direct `signInAnonymously` result** — prefer `onAuthStateChanged` to capture uid because: (a) it fires on page reload when the user is already signed in (Firebase persists anonymous auth across reloads by default via `browserLocalPersistence`), avoiding unnecessary new sign-ins. Pattern:
   ```typescript
   useEffect(() => {
     const unsubscribe = onAuthStateChanged(auth, async (user) => {
       if (user) {
         const token = await user.getIdToken();
         useARIAStore.setState({ uid: user.uid, idToken: token });
       } else {
         await signInAnonymously(auth); // triggers onAuthStateChanged again
       }
     });
     return () => unsubscribe();
   }, []);
   ```

6. **Session ID format: `sess_` prefix + UUID v4** — the `session_id` field in all Firestore documents, SSE events, WebSocket paths, and REST endpoints must use this exact format: `sess_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Never `session-`, `s-`, or bare UUID. Python: `"sess_" + str(uuid.uuid4())`.

7. **Canonical response envelope on ALL routes** — ALL REST responses (200, 400, 401, 404, 500) must use `{ "success": bool, "data": {...} | null, "error": {...} | null }`. Never return a plain `{ "detail": "..." }` (FastAPI default HTTPException format). Raise custom exceptions or return `JSONResponse` directly.

8. **Firestore `status` field initial value: `"pending"`** — subsequent stories update this to `"running"`, `"paused"`, `"completed"`, `"failed"`. The field must be set to `"pending"` at document creation in this story. The architecture doc shows `"pending"` is not in the running state enum (`running | paused | awaiting_confirmation | completed | failed`) — that's correct; `"pending"` is the pre-execution state before ADK runner starts.

9. **Backend must NOT start ADK runner in this story** — `POST /api/task/start` only creates the Firestore document and returns `session_id`. The actual ADK agent execution (`root_agent.run_async()`) is wired in Story 2.1 (Planner Agent). This story only establishes auth → session creation → response pattern.

### Backend Route Implementation Pattern

```python
# aria-backend/routers/task_router.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import firebase_admin.auth as firebase_auth
from services.session_service import create_session

router = APIRouter(prefix="/api/task")


class StartTaskRequest(BaseModel):
    task_description: str


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"success": False, "data": None, "error": {"code": code, "message": message}},
    )


@router.post("/start")
async def start_task(request: Request, body: StartTaskRequest):
    # 1. Extract token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)
    id_token = auth_header.split("Bearer ", 1)[1]

    # 2. Verify token
    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception:
        return _error_response("UNAUTHORIZED", "Invalid or missing token", 401)

    uid = decoded["uid"]

    # 3. Create session
    session_data = await create_session(uid, body.task_description)

    return JSONResponse(
        status_code=200,
        content={"success": True, "data": session_data, "error": None},
    )
```

### Firebase Admin SDK Initialization in `main.py`

```python
# Add to main.py lifespan:
import firebase_admin
from firebase_admin import credentials

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Firebase Admin SDK
    if not firebase_admin._apps:
        firebase_admin.initialize_app()  # ADC auto-detected (Cloud Run SA or gcloud local)
        logger.info("Firebase Admin SDK initialized")
    # ... existing Playwright smoketest ...
    yield
```

### Zustand Session Slice Update Pattern

```typescript
// aria-store.ts — SessionSlice additions (keep existing fields)
interface SessionSlice {
  sessionId: string | null;
  taskStatus: TaskStatus;
  taskDescription: string;
  uid: string | null;       // ADD: Firebase Anonymous Auth uid
  idToken: string | null;   // ADD: JWT token for API Authorization header
}
// Initialize:
uid: null,
idToken: null,
```

### Project Structure — Files Touched in This Story

| File | Action | Notes |
|---|---|---|
| `aria-frontend/src/lib/firebase.ts` | **Update** | Replace stub with real `initializeApp` + `getAuth` |
| `aria-frontend/src/lib/store/aria-store.ts` | **Update** | Add `uid` and `idToken` to `SessionSlice` |
| `aria-frontend/src/app/layout.tsx` | **Update** | Add `signInAnonymously` + `onAuthStateChanged` logic in client component |
| `aria-frontend/src/lib/api/task.ts` | **Create** | `startTask()` fetch wrapper with `Authorization` header |
| `aria-frontend/src/types/aria.ts` | **Update** | Add `StartTaskData` and `StartTaskResponse` types |
| `aria-backend/routers/task_router.py` | **Create** | `POST /api/task/start` route handler |
| `aria-backend/services/session_service.py` | **Create** | `create_session()` — Firestore document creation |
| `aria-backend/main.py` | **Update** | Mount `task_router`; init Firebase Admin SDK in lifespan |
| `aria-backend/requirements.txt` | **Update** | Add `firebase-admin` |

### Context from Previous Stories

**From Story 1.1 (Backend):**
- `main.py` uses `lifespan` async context manager — Firebase Admin SDK init goes there
- CORS is already configured with comma-split origins; `http://localhost:3000` is the default CORS_ORIGIN
- `python-dotenv` `load_dotenv()` is called at module top — backend env vars load from `aria-backend/.env`

**From Story 1.2 (Frontend):**
- `next.config.ts` has `output: "export"` (static export) — **no API routes in Next.js**; all calls go to Cloud Run
- All frontend API calls must go to `process.env.NEXT_PUBLIC_BACKEND_URL` (default: `http://localhost:8080`)
- `aria-frontend/src/lib/firebase.ts` exists as a stub — this story replaces that stub
- shadcn/ui, Tailwind, and Zustand with immer middleware are already installed
- `"use client"` directive is required for any component that uses Firebase Auth or Zustand hooks

**From Story 1.3 (Infrastructure):**
- Firebase Anonymous Auth is enabled in Firebase Console
- Firebase SDK (`firebase` npm package) is installed in `aria-frontend/package.json`
- `aria-frontend/.env.local` has all 6 `NEXT_PUBLIC_FIREBASE_*` values set
- Firestore security rules are deployed — `sessions/{session_id}` allows create/read/update only by matching `uid`
- `aria-backend-sa` service account is attached to Cloud Run — ADC works on Cloud Run with no additional config
- `FIREBASE_PROJECT_ID` env var is in `aria-backend/.env`

### Testing Standards

This story introduces the first code with real Firebase integration. Testing approach:

**Backend unit tests — `aria-backend/tests/test_task_router.py`:**
- Mock `firebase_auth.verify_id_token` using `pytest-mock` / `monkeypatch`
- Test: no Authorization header → 401 `UNAUTHORIZED`
- Test: invalid token → 401 `UNAUTHORIZED`
- Test: valid token + valid body → 200 + `session_id` and `stream_url` in `data`
- Test: Firestore document created with correct fields (mock Firestore client)

**Frontend integration (manual for MVP):**
- Open browser → DevTools → Application → Local Storage: check Firebase auth persistence key exists
- Open React DevTools or browser console `useARIAStore.getState()` to see `uid` and `idToken` populated

**Playwright E2E (if time permits):**
- Page load → auth state → `uid` present → call `startTask` → Firestore document created

### Architecture Compliance Checklist

- [ ] Session ID uses `sess_` prefix + UUID v4 format
- [ ] All REST responses use `{ success, data, error }` envelope
- [ ] HTTP 401 (not 403) for missing/invalid token
- [ ] Firestore document fields: `session_id`, `uid`, `created_at` (ISO 8601 + `Z`), `task_description`, `status: "pending"`, `steps: []`
- [ ] `firebase_admin.initialize_app()` called once (guard with `if not firebase_admin._apps`)
- [ ] Frontend uses `onAuthStateChanged` pattern (not just one-shot `signInAnonymously`)
- [ ] `idToken` stored in Zustand `sessionSlice` (not component local state)
- [ ] snake_case for all JSON API fields
- [ ] No ADK runner invoked in this story — session creation only

### References

- Auth pattern: [architecture/core-architectural-decisions.md](../_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) → "Authentication & Security / Firebase Anonymous Auth"
- REST envelope: [architecture/implementation-patterns-consistency-rules.md](../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Format Patterns / API response wrapper"
- Firestore structure: [architecture/core-architectural-decisions.md](../_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) → "Data Architecture / Firestore document structure"
- Session ID format: [architecture/implementation-patterns-consistency-rules.md](../_bmad-output/planning-artifacts/architecture/implementation-patterns-consistency-rules.md) → "Enforcement Guidelines"
- Project file locations: [architecture/project-structure-boundaries.md](../_bmad-output/planning-artifacts/architecture/project-structure-boundaries.md) → "Complete Project Directory Structure"
- Story AC source: [epics.md](../_bmad-output/planning-artifacts/epics.md) → Story 1.4

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (Antigravity)

### Debug Log References

- **Test fix**: Firestore `AsyncClient()` was being instantiated at module-level in `session_service.py`, causing ADC credential lookup at import time which broke test collection. Fixed by converting to lazy initialization via `_get_db()` helper.
- **Layout strategy**: `layout.tsx` must remain a Server Component for Next.js metadata export. Created separate `FirebaseAuthProvider` client component (renders null) to handle auth side-effects.
- **conftest.py**: Firebase Admin SDK `_apps` dict must be patched at module level in `conftest.py` (not in a fixture) because `from main import app` triggers lifespan at import time.

### Completion Notes List

- ✅ Task 1: Replaced `firebase.ts` stub with real `initializeApp`/`getAuth` using singleton guard, all 6 `NEXT_PUBLIC_FIREBASE_*` env vars
- ✅ Task 2: Added `uid: string | null` and `idToken: string | null` to Zustand `SessionSlice`, initialized to `null`
- ✅ Task 3: Created `FirebaseAuthProvider` client component with `onAuthStateChanged` + `signInAnonymously` pattern, mounted in `layout.tsx`
- ✅ Task 4: Created `task.ts` API wrapper (`startTask()`) and `StartTaskData`/`StartTaskResponse` types in `aria.ts`
- ✅ Task 5: Implemented `POST /api/task/start` in `task_router.py`, `create_session()` in `session_service.py`, Firebase Admin SDK init in `main.py` lifespan
- ✅ Task 6: `firebase-admin` installed locally and already in `requirements.txt`; `google-cloud-firestore` already pinned
- ✅ Task 7: Backend pytest 7/7 pass (6 new + 1 healthz regression); Frontend `npm run build` 0 errors

### File List

- `aria-frontend/src/lib/firebase.ts` — **Modified**: replaced stub with real Firebase init
- `aria-frontend/src/lib/store/aria-store.ts` — **Modified**: added `uid`, `idToken` to SessionSlice
- `aria-frontend/src/app/layout.tsx` — **Modified**: added FirebaseAuthProvider
- `aria-frontend/src/components/providers/firebase-auth-provider.tsx` — **New**: client component for anonymous auth
- `aria-frontend/src/lib/api/task.ts` — **New**: `startTask()` API wrapper
- `aria-frontend/src/types/aria.ts` — **Modified**: added StartTaskData, StartTaskResponse interfaces
- `aria-backend/routers/__init__.py` — **New**: empty init for routers package
- `aria-backend/routers/task_router.py` — **New**: POST /api/task/start route handler
- `aria-backend/services/session_service.py` — **Modified**: replaced stub with Firestore create_session/get_session
- `aria-backend/main.py` — **Modified**: Firebase Admin SDK init in lifespan, mounted task_router
- `aria-backend/tests/conftest.py` — **New**: module-level Firebase Admin SDK mock
- `aria-backend/tests/test_task_router.py` — **Modified**: 6 original + 2 new tests (empty description 422, Firestore failure 500)
- `aria-backend/tests/test_session_service.py` — **New**: 3 unit tests verifying Firestore document fields (AC4)

## Change Log

- 2026-02-25: Implemented Story 1.4 — Firebase Anonymous Auth (frontend) and POST /api/task/start (backend) with session creation, token verification, canonical response envelope, and comprehensive test coverage
- 2026-02-25: Code review (AI) — Fixed 6 issues: [H1] Firestore failure now returns canonical 500 envelope; [H2] `task_description` min_length=1 validation + global `RequestValidationError` → canonical 422; [H3] `startTask()` fetch wrapped in try/catch returning typed `NETWORK_ERROR` envelope; [M1] Added `test_session_service.py` with 3 tests verifying AC4 Firestore document fields; [M2] `/healthz` now returns canonical `{success, data, error}` envelope; [L1] `signInAnonymously` error logged via `.catch()`. Backend: 12/12 tests pass. Frontend build: 0 errors.
