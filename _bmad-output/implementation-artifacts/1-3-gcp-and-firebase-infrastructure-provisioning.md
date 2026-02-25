# Story 1.3: GCP and Firebase Infrastructure Provisioning

Status: done

## Story

As a developer,
I want all required GCP and Firebase services provisioned and environment variables documented,
so that the backend can connect to Cloud Run, Firestore, GCS, and Firebase Hosting without manual setup per developer.

## Acceptance Criteria

1. **Given** a GCP project is selected, **When** the provisioning steps are followed, **Then** a Cloud Run service placeholder exists in `us-central1`, a GCS bucket named per `GCS_BUCKET_NAME` env var exists, and Google Secret Manager contains `GEMINI_API_KEY`.

2. **Given** Firebase is configured for the project, **When** setup is complete, **Then** a Firestore database exists in Native mode, Firebase Hosting is initialized for `aria-frontend`, and Firebase Anonymous Auth is enabled.

3. **Given** a `.env.local` file in `aria-frontend/` and a `.env` file in `aria-backend/`, **When** both apps start locally, **Then** they read `GEMINI_API_KEY`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `GCS_BUCKET_NAME`, and `CORS_ORIGIN` from their respective env files without error.

4. **Given** the Firestore security rules, **When** rules are deployed, **Then** session documents in the `sessions` collection are read/write only by the authenticated uid that owns the document (Firebase Anonymous Auth).

## Tasks / Subtasks

- [ ] Task 1: GCP project setup and API enablement (AC: 1)
  - [ ] Select or create a GCP project. Note the **Project ID** (e.g., `aria-hackathon-2026`) — this is `GCP_PROJECT` throughout
  - [ ] Authenticate with GCP: `gcloud auth login && gcloud config set project $GCP_PROJECT`
  - [ ] Enable all required APIs in one command:
    ```bash
    gcloud services enable \
      run.googleapis.com \
      artifactregistry.googleapis.com \
      secretmanager.googleapis.com \
      storage.googleapis.com \
      firestore.googleapis.com \
      firebase.googleapis.com \
      iam.googleapis.com
    ```
  - [ ] Verify enablement: `gcloud services list --enabled --filter="name:run OR name:secretmanager OR name:storage OR name:firestore"` — all four should appear

- [ ] Task 2: Google Artifact Registry setup (AC: 1, prerequisite for Story 1.6)
  - [ ] Create Docker repository for backend images:
    ```bash
    gcloud artifacts repositories create aria-backend \
      --repository-format=docker \
      --location=us-central1 \
      --description="ARIA backend Docker images"
    ```
  - [ ] Note the full image path: `us-central1-docker.pkg.dev/$GCP_PROJECT/aria-backend/aria-backend` — this is the `IMAGE_NAME` used in Story 1.6

- [ ] Task 3: Cloud Run placeholder service (AC: 1)
  - [ ] Deploy a lightweight placeholder so the Cloud Run service name is reserved and its URL is known:
    ```bash
    gcloud run deploy aria-backend \
      --image gcr.io/cloudrun/hello \
      --region us-central1 \
      --allow-unauthenticated \
      --min-instances 1 \
      --concurrency 1 \
      --memory 4Gi \
      --cpu 2 \
      --port 8080
    ```
  - [ ] Note the assigned Cloud Run URL (format: `https://aria-backend-HASH-uc.a.run.app`) — this becomes `CORS_ORIGIN` value for the backend and the frontend's `NEXT_PUBLIC_BACKEND_URL` in production; for now store it
  - [ ] Note: The placeholder image (`gcr.io/cloudrun/hello`) is replaced with the real Docker image in Story 1.6

- [ ] Task 4: GCS bucket creation (AC: 1)
  - [ ] Choose a globally unique bucket name: convention `${GCP_PROJECT}-aria-screenshots` (e.g., `aria-hackathon-2026-aria-screenshots`)
  - [ ] Create the bucket:
    ```bash
    gsutil mb -p $GCP_PROJECT -l us-central1 gs://$GCS_BUCKET_NAME
    ```
  - [ ] Set uniform bucket-level access (required for service account IAM binding):
    ```bash
    gsutil uniformbucketlevelaccess set on gs://$GCS_BUCKET_NAME
    ```
  - [ ] Verify the bucket exists: `gsutil ls -p $GCP_PROJECT`

- [ ] Task 5: Google Secret Manager — store `GEMINI_API_KEY` (AC: 1)
  - [ ] Store the Gemini API key in Secret Manager (obtained from Google AI Studio):
    ```bash
    echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY \
      --data-file=- \
      --project=$GCP_PROJECT
    ```
  - [ ] Verify: `gcloud secrets versions access latest --secret=GEMINI_API_KEY` — should print the key
  - [ ] **NEVER** put the Gemini API key in `.env.example`, commit messages, or any tracked file

- [ ] Task 6: Firebase project setup (AC: 2)
  - [ ] Go to [Firebase Console](https://console.firebase.google.com) → "Add project" → select your existing GCP project (`$GCP_PROJECT`) — Firebase layers on top of GCP, same project ID
  - [ ] Note `FIREBASE_PROJECT_ID` = same as `GCP_PROJECT`
  - [ ] **Enable Firestore** (Native mode):
    - Firebase Console → Build → Firestore Database → Create database
    - Select **Native mode** (NOT Datastore mode — incompatible with real-time listeners)
    - Region: `us-central1` (same as Cloud Run)
  - [ ] **Enable Firebase Hosting:**
    - Firebase Console → Build → Hosting → Get started
    - Register site (site name can be `aria-hackathon-2026` or custom)
    - Note the Firebase Hosting URL: `https://${FIREBASE_PROJECT_ID}.web.app` — this becomes the **production** `CORS_ORIGIN`
  - [ ] **Enable Anonymous Auth:**
    - Firebase Console → Build → Authentication → Sign-in method
    - Enable "Anonymous" provider → Save
  - [ ] **Register a Web App** to get the Firebase SDK config:
    - Firebase Console → Project settings → Your apps → Add app → Web
    - App nickname: `aria-frontend`
    - Check "Also set up Firebase Hosting for this app"
    - Copy the `firebaseConfig` object — it contains `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`

- [ ] Task 7: Create backend service account with correct IAM roles (AC: 1, prereq for Stories 2–4)
  - [ ] Create a dedicated service account for the Cloud Run backend:
    ```bash
    gcloud iam service-accounts create aria-backend-sa \
      --display-name="ARIA Backend Service Account" \
      --project=$GCP_PROJECT
    export BACKEND_SA="aria-backend-sa@$GCP_PROJECT.iam.gserviceaccount.com"
    ```
  - [ ] Grant required roles:
    ```bash
    # Firestore read/write
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$BACKEND_SA" \
      --role="roles/datastore.user"

    # GCS screenshot uploads
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$BACKEND_SA" \
      --role="roles/storage.objectAdmin" \
      --condition="expression=resource.name.startsWith('projects/_/buckets/$GCS_BUCKET_NAME'),title=BucketScoped"

    # Secret Manager read (GEMINI_API_KEY)
    gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
      --member="serviceAccount:$BACKEND_SA" \
      --role="roles/secretmanager.secretAccessor" \
      --project=$GCP_PROJECT
    ```
  - [ ] Attach the service account to the Cloud Run service:
    ```bash
    gcloud run services update aria-backend \
      --service-account=$BACKEND_SA \
      --region=us-central1
    ```
  - [ ] Create a CI/CD service account for Story 1.6 (GitHub Actions):
    ```bash
    gcloud iam service-accounts create github-actions-sa \
      --display-name="GitHub Actions CI/CD" \
      --project=$GCP_PROJECT
    export CICD_SA="github-actions-sa@$GCP_PROJECT.iam.gserviceaccount.com"

    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$CICD_SA" \
      --role="roles/run.admin"
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$CICD_SA" \
      --role="roles/artifactregistry.writer"
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$CICD_SA" \
      --role="roles/iam.serviceAccountUser"
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
      --member="serviceAccount:$CICD_SA" \
      --role="roles/firebase.admin"
    ```
  - [ ] Download the GitHub Actions service account key (for GitHub Actions secret):
    ```bash
    gcloud iam service-accounts keys create cicd-sa-key.json \
      --iam-account=$CICD_SA
    ```
  - [ ] **DO NOT commit `cicd-sa-key.json`** — add to `.gitignore`. This file will be base64-encoded and stored as `GCP_SA_KEY` in GitHub Secrets in Story 1.6

- [ ] Task 8: Create Firebase config files (AC: 2, 4)
  - [ ] Install Firebase CLI if not installed: `npm install -g firebase-tools && firebase login`
  - [ ] Create `aria-frontend/firebase.json`:
    ```json
    {
      "firestore": {
        "rules": "firestore.rules"
      },
      "hosting": {
        "public": "out",
        "cleanUrls": true,
        "trailingSlash": false,
        "ignore": [
          "firebase.json",
          "**/.*",
          "**/node_modules/**"
        ],
        "rewrites": [
          {
            "source": "**",
            "destination": "/index.html"
          }
        ]
      }
    }
    ```
    **Note:** `"public": "out"` — Next.js static export generates to `out/`. This requires `output: "export"` in `next.config.ts` (Task 9)
  - [ ] Create `aria-frontend/.firebaserc`:
    ```json
    {
      "projects": {
        "default": "$FIREBASE_PROJECT_ID"
      }
    }
    ```
    (Replace `$FIREBASE_PROJECT_ID` with the actual project ID string — not a variable)
  - [ ] Create `aria-frontend/firestore.rules` (Firestore security rules):
    ```
    rules_version = '2';
    service cloud.firestore {
      match /databases/{database}/documents {
        // Sessions collection: only the owning uid can read or write
        match /sessions/{sessionId} {
          // Read: authenticated user who owns this session
          allow read: if request.auth != null
                       && request.auth.uid == resource.data.uid;

          // Create: authenticated user, must set their own uid as the owner
          allow create: if request.auth != null
                         && request.resource.data.uid == request.auth.uid;

          // Update: only the session owner — backend uses Admin SDK (bypasses rules)
          allow update: if request.auth != null
                         && request.auth.uid == resource.data.uid;

          // Delete: not permitted from client
          allow delete: if false;
        }

        // Deny all other paths
        match /{document=**} {
          allow read, write: if false;
        }
      }
    }
    ```
  - [ ] Deploy Firestore security rules: from `aria-frontend/`, run `firebase deploy --only firestore:rules`
  - [ ] Verify deployment: Firebase Console → Firestore → Rules — should show the above rules with current timestamp

- [ ] Task 9: Configure Next.js for static export (AC: 2, prereq for Story 1.6)
  - [ ] Update `aria-frontend/next.config.ts` to enable static HTML export:
    ```typescript
    import type { NextConfig } from "next";

    const nextConfig: NextConfig = {
      output: "export",
      trailingSlash: false,
      // Static export disables Image Optimization API — use unoptimized images or next/image with loader
      images: { unoptimized: true },
    };

    export default nextConfig;
    ```
  - [ ] Verify static export works: from `aria-frontend/`, run `npm run build` — should produce an `out/` directory
  - [ ] Confirm `out/index.html` exists after build

- [ ] Task 10: Populate environment variable files (AC: 3)
  - [ ] **`aria-backend/.env`** — update with real values (this file is gitignored):
    ```
    GEMINI_API_KEY=your-gemini-api-key-here
    GCP_PROJECT=your-gcp-project-id
    FIREBASE_PROJECT_ID=your-gcp-project-id
    GCS_BUCKET_NAME=your-gcp-project-id-aria-screenshots
    CORS_ORIGIN=http://localhost:3000
    ```
    (For local dev, `CORS_ORIGIN=http://localhost:3000`. Production value is `https://${FIREBASE_PROJECT_ID}.web.app` — set via Secret Manager in Story 1.6)
  - [ ] **`aria-frontend/.env.local`** — update with Firebase SDK config values copied from Firebase Console → Project settings → Your apps → Web app → Config:
    ```
    NEXT_PUBLIC_BACKEND_URL=http://localhost:8080
    NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSy...
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-gcp-project-id
    NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
    NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
    NEXT_PUBLIC_FIREBASE_APP_ID=1:123456789:web:abc123
    ```
  - [ ] **`aria-frontend/.env.example`** — update to include all Firebase keys (blank values, for documentation):
    ```
    NEXT_PUBLIC_BACKEND_URL=http://localhost:8080
    NEXT_PUBLIC_FIREBASE_API_KEY=
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=
    NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
    NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
    NEXT_PUBLIC_FIREBASE_APP_ID=
    ```
  - [ ] Verify `aria-frontend/.gitignore` has `.env*.local` pattern (created by Next.js scaffold — should already be present)
  - [ ] Verify `aria-backend/.gitignore` has `.env` (created in Story 1.1 — should already be present)

- [ ] Task 11: Install Firebase SDK in `aria-frontend` (AC: 3)
  - [ ] From `aria-frontend/`, install the Firebase JavaScript SDK:
    ```bash
    npm install firebase
    ```
  - [ ] Verify `firebase` appears in `aria-frontend/package.json` dependencies
  - [ ] **Do NOT** populate `aria-frontend/src/lib/firebase.ts` yet — that stub is populated in Story 1.4 with `initializeApp`, `getAuth`, and `signInAnonymously` logic. Story 1.3 only adds the SDK dependency.

- [ ] Task 12: End-to-end validation (AC: 1–4)
  - [ ] **Backend env test:** from `aria-backend/`, run `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('GEMINI_API_KEY', 'MISSING'))"` — must print the key, not "MISSING"
  - [ ] **Frontend env test:** from `aria-frontend/`, run `npm run build` — must complete with 0 errors (confirms `NEXT_PUBLIC_*` vars are defined in `.env.local`)
  - [ ] **Firestore rules test:** Firebase Console → Firestore → Rules → Rules Playground
    - Simulate read on `sessions/sess_test` with auth `uid: "user1"` and document `uid: "user2"` → must be **DENIED**
    - Simulate read on `sessions/sess_test` with auth `uid: "user1"` and document `uid: "user1"` → must be **ALLOWED**
  - [ ] **Cloud Run placeholder check:** `curl https://aria-backend-HASH-uc.a.run.app` — placeholder service should respond (any 200 response confirms the URL is valid)
  - [ ] **GCS bucket check:** `gsutil ls gs://$GCS_BUCKET_NAME` — should return empty listing without error
  - [ ] **Secret Manager check:** `gcloud secrets versions access latest --secret=GEMINI_API_KEY` — prints the API key

## Dev Notes

### Critical Architecture Requirements — DO NOT DEVIATE

1. **Firestore must be Native mode, NOT Datastore mode** — real-time `onSnapshot` listeners (used in Story 3.6 for audit log) are unavailable in Datastore compatibility mode. Once a Firestore database is created in Datastore mode, it cannot be switched without deleting and recreating the entire database.

2. **Firebase project = GCP project** — Firebase is layered on GCP; they share the same Project ID. `FIREBASE_PROJECT_ID` and `GCP_PROJECT` will be identical strings. Do not create a separate Firebase project.

3. **Firestore region must be `us-central1`** — must match Cloud Run region to minimize ADK→Firestore latency. Firestore region is set at database creation time and is **immutable**. Using a different region (e.g., `us-east1`) will not break functionality but adds ~50ms to every audit write.

4. **`output: "export"` in `next.config.ts` is mandatory for Firebase Hosting** — Firebase Hosting serves static files; it cannot run a Node.js server. The Next.js app must be exported to static HTML. Since ARIA is a fully client-side SPA (one route, all data from APIs), static export is perfectly compatible. **Caveat:** static export disables Next.js server-side features (SSR, API routes, middleware). ARIA does not use any of these — all API calls go to the Cloud Run backend.

5. **CORS_ORIGIN in production must be the exact Firebase Hosting URL** — no wildcards. The backend's `main.py` from Story 1.1 accepts comma-separated origins. For local dev: `http://localhost:3000`. For production (Story 1.6): `https://${FIREBASE_PROJECT_ID}.web.app`. Set in Cloud Run env vars via Secret Manager in Story 1.6.

6. **Firestore security rules: `allow delete: if false`** — session documents are never deleted from the client, only by backend Admin SDK (which bypasses rules). Strict rule prevents accidental data loss.

7. **`cicd-sa-key.json` MUST NOT be committed** — the CI/CD service account key created in Task 7 must remain local. It will be base64-encoded and stored as `GCP_SA_KEY` in GitHub repository secrets in Story 1.6. Committing it would expose full GCP project access.

### Google Secret Manager Integration — How the Backend Reads GEMINI_API_KEY

In local development, `aria-backend/.env` is loaded by `python-dotenv` (`load_dotenv()` in `main.py`). In production (Cloud Run), environment variables must be explicitly mapped from Secret Manager in the deploy command (done in Story 1.6):

```bash
gcloud run deploy aria-backend \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  ...
```

This maps Secret Manager secret → Cloud Run environment variable. The Python code `os.getenv("GEMINI_API_KEY")` works identically in both environments since `load_dotenv()` does not override existing environment variables.

### Firebase SDK Config — All 6 Fields Are Required

The `firebaseConfig` object from the Firebase Console has 6 fields. All 6 must be in `.env.local` as `NEXT_PUBLIC_*` vars — Firebase throws `FirebaseError: Firebase: Firebase App named '[DEFAULT]' already exists` (or worse) if partial config is passed. `messagingSenderId` and `appId` look optional but are required for Firebase Auth to function correctly.

### `firestore.rules` — Security Rule Logic Explained

```
allow read: if request.auth != null && request.auth.uid == resource.data.uid;
```
- `request.auth` — the requesting user's Firebase Auth token (populated by `signInAnonymously()`)
- `resource.data.uid` — the `uid` field on the existing Firestore document (set by backend at creation in Story 1.4)
- This ensures user A cannot read user B's session

```
allow create: if request.auth != null && request.resource.data.uid == request.auth.uid;
```
- `request.resource.data.uid` — the `uid` field on the **incoming** write (the new document)
- Prevents user A from creating a document with `uid: "user_B"` to hijack B's session
- NOTE: In the actual implementation, session creation is done by the backend via Firebase Admin SDK (which bypasses these rules). This rule is defensive belt-and-suspenders.

### Files Created/Modified in This Story

| File | Action | Notes |
|---|---|---|
| `aria-frontend/firebase.json` | Create | Firestore rules + Hosting static export config |
| `aria-frontend/.firebaserc` | Create | Maps `default` to project ID |
| `aria-frontend/firestore.rules` | Create | Session collection uid-scoped read/write |
| `aria-frontend/next.config.ts` | Update | Add `output: "export"`, `images: { unoptimized: true }` |
| `aria-frontend/.env.local` | Update | Fill in all `NEXT_PUBLIC_FIREBASE_*` values |
| `aria-frontend/.env.example` | Update | Document all `NEXT_PUBLIC_FIREBASE_*` keys |
| `aria-backend/.env` | Update | Fill in all real values for local dev |
| `aria-frontend/package.json` | Update | Add `firebase` SDK dependency |

### Context from Previous Stories

**From Story 1.1 (Backend):**
- `aria-backend/.env.example` already exists with the correct 5 keys (`GEMINI_API_KEY`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `GCS_BUCKET_NAME`, `CORS_ORIGIN`) — no changes needed to `.env.example`
- `aria-backend/.env` exists as gitignored placeholder with empty values — Task 10 fills it in
- `main.py` uses comma-split CORS: `cors_origins = [o.strip() for o in cors_raw.split(",")]` — supports multiple origins
- `python-dotenv` is already installed and called on startup

**From Story 1.2 (Frontend):**
- `aria-frontend/.env.local` and `aria-frontend/.env.example` already exist — Task 10 updates them
- `aria-frontend/src/lib/firebase.ts` exists as an **empty stub** — do NOT populate it in this story. Population happens in Story 1.4 (`initializeApp`, `getAuth`, `signInAnonymously` setup)
- `npm run build` passes with 0 errors as of Story 1.2 completion — verify it still passes after `next.config.ts` changes in Task 9

### Architecture Gaps Resolved by This Story

The architecture-validation-results.md document noted these items as important gaps to address in the first implementation sprint:
- `firestore.rules` not listed in project tree → **resolved: Task 8 creates it**
- `firebase.json` and `.firebaserc` not listed in project tree → **resolved: Task 8 creates them**

### GCS Bucket Naming Convention

Bucket names must be **globally unique** across all of GCP. Convention: `{GCP_PROJECT_ID}-aria-screenshots`. This ensures uniqueness within the project's namespace. If the project ID contains numbers or special chars, gsutil will accept them as long as the name is 3–63 chars, lowercase only, no underscores.

### Cloud Run Service Account vs. Application Default Credentials

The `aria-backend-sa` service account created in Task 7 is used in two ways:
1. **Cloud Run runtime:** Attached to the Cloud Run service, it is automatically used when `google-cloud-firestore`, `google-cloud-storage`, and the Gemini SDK authenticate via Application Default Credentials (ADC)
2. **Local dev:** On a developer's machine, ADC is provided by `gcloud auth application-default login` — or by setting `GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json`. For hackathon dev, `gcloud auth application-default login` is sufficient

### `next.config.ts` — Static Export Notes

Enabling `output: "export"` affects:
1. **No API routes**: `src/app/api/` routes will not work. ARIA does not use Next.js API routes (all backend calls go to Cloud Run).
2. **No `<Image>` optimization**: Next.js Image Optimization requires a Node.js server. Setting `images: { unoptimized: true }` disables this. ARIA's current design uses CSS backgrounds and SVG icons — no remote image sources.
3. **Dynamic routes require `generateStaticParams`**: ARIA has no dynamic routes — only `src/app/page.tsx`
4. `npm run build` now produces both `.next/` (build artifacts) and `out/` (static export) — `out/` is what gets deployed

### Story 1.6 Prerequisites Prepared in This Story

| Story 1.6 Requirement | Prepared Here |
|---|---|
| Artifact Registry repository | Task 2 creates `aria-backend` Docker repo |
| Cloud Run service (name reserved) | Task 3 deploys placeholder service |
| Backend service account | Task 7 creates `aria-backend-sa` with correct roles |
| CI/CD service account | Task 7 creates `github-actions-sa` with deploy roles |
| SA key for GitHub Secrets | Task 7 generates `cicd-sa-key.json` (local only) |
| Firebase Hosting site registered | Task 6 initializes via Firebase Console |
| Static export configured | Task 9 adds `output: "export"` to `next.config.ts` |

### Environment Variables — Complete Reference

| Variable | Where Used | Local Value | Production Source |
|---|---|---|---|
| `GEMINI_API_KEY` | `aria-backend/.env` | Your API key | Secret Manager `GEMINI_API_KEY:latest` |
| `GCP_PROJECT` | `aria-backend/.env` | Your project ID | Cloud Run env var |
| `FIREBASE_PROJECT_ID` | `aria-backend/.env` | Same as GCP_PROJECT | Cloud Run env var |
| `GCS_BUCKET_NAME` | `aria-backend/.env` | `{GCP_PROJECT}-aria-screenshots` | Cloud Run env var |
| `CORS_ORIGIN` | `aria-backend/.env` | `http://localhost:3000` | Cloud Run env var (`https://{project}.web.app`) |
| `NEXT_PUBLIC_BACKEND_URL` | `aria-frontend/.env.local` | `http://localhost:8080` | `https://aria-backend-HASH-uc.a.run.app` |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | `aria-frontend/.env.local` | From Firebase Console | Same (public key, safe in browser) |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `aria-frontend/.env.local` | `{project}.firebaseapp.com` | Same |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | `aria-frontend/.env.local` | Your project ID | Same |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | `aria-frontend/.env.local` | `{project}.appspot.com` | Same |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | `aria-frontend/.env.local` | From Firebase Console | Same |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | `aria-frontend/.env.local` | From Firebase Console | Same |

**Note on `NEXT_PUBLIC_*` Firebase vars:** Firebase web config (apiKey, authDomain, etc.) is **not secret** — it is embedded in every web request and is visible in the browser. Firebase Security Rules and Anonymous Auth prevent unauthorized access. The `NEXT_PUBLIC_` prefix is simply required for Next.js to include client-side accessible env vars in the browser bundle.

### Testing Standards

This story has no compiled code — validation is entirely CLI-based and manual. Acceptance is met when:
- All 6 Task 12 validation checks pass
- `npm run build` in `aria-frontend/` produces an `out/` directory with 0 errors
- Firestore security rules deployed successfully (Firebase Console shows deployment timestamp)
- `GET https://aria-backend-HASH-uc.a.run.app` returns any HTTP 200 (placeholder deployed)

### References

- Required env vars: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Infrastructure & Deployment / Required environment variables"
- Firestore document structure: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Data Architecture / Firestore document structure"
- Auth & Security design: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Authentication & Security / Firebase Anonymous Auth"
- CORS constraint: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Authentication & Security / CORS locked to Firebase Hosting origin"
- Cloud Run deploy params: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Infrastructure & Deployment / Concurrency constraint rationale"
- CI/CD pipeline spec: [architecture/core-architectural-decisions.md](_bmad-output/planning-artifacts/architecture/core-architectural-decisions.md) — "Infrastructure & Deployment / CI/CD GitHub Actions"
- Architecture gaps resolved: [architecture/architecture-validation-results.md](_bmad-output/planning-artifacts/architecture/architecture-validation-results.md) — "Gap Analysis / Important (address in first implementation sprint)"
- Project structure (firebase.json location): [architecture/project-structure-boundaries.md](_bmad-output/planning-artifacts/architecture/project-structure-boundaries.md) — "Complete Project Directory Structure"
- Story AC source: [epics.md](_bmad-output/planning-artifacts/epics.md) — Story 1.3

## Dev Agent Record

### Agent Model Used

Gemini-3-Pro-Preview (200k)

### Debug Log References

### Completion Notes List

- Provisioned all GCP resources: Cloud Run placeholder, GCS bucket, Artifact Registry repo, Secret Manager secret.
- Configured Firebase: Firestore (Native mode), Hosting, Anonymous Auth.
- Created Service Accounts: `aria-backend-sa` (runtime) and `github-actions-sa` (CI/CD) with correct IAM roles.
- Generated CI/CD key: `cicd-sa-key.json` (local only, added to .gitignore).
- Configured Frontend: `firebase.json`, `firestore.rules`, `.firebaserc`, `next.config.ts` (static export).
- Populated Environment Variables: `aria-backend/.env` and `aria-frontend/.env.local` with real values.
- Validated Setup:
  - `npm run build` passes (Next.js static export works).
  - Cloud Run placeholder URL is active.
  - GCS bucket exists and is accessible.
  - Secret Manager contains `GEMINI_API_KEY`.
  - Artifact Registry repo `aria-backend` created.
  - Firestore rules deployed.

### Code Review Findings (Fixed)

- **Fixed:** `aria-frontend/firebase.json`, `.firebaserc`, and `firestore.rules` were untracked. Added to git.
- **Fixed:** `aria-frontend/.env.example` was ignored by `.gitignore`. Updated `.gitignore` to track it.
- **Fixed:** `aria-frontend/package.json` and `package-lock.json` were modified but missing from File List. Added.

### File List

- aria-backend/.env
- aria-frontend/.env.local
- aria-frontend/.env.example
- aria-frontend/firebase.json
- aria-frontend/.firebaserc
- aria-frontend/firestore.rules
- aria-frontend/next.config.ts
- aria-frontend/package.json
- aria-frontend/package-lock.json
- aria-frontend/.gitignore
- .gitignore
