# Starter Template Evaluation

### Primary Technology Domain

Full-stack split architecture: TypeScript/Next.js frontend + Python/ADK backend deployed as separate services. Two project starters required.

### Starter Options Considered

**Frontend:** `create-next-app` (official Next.js CLI) — the only supported way to bootstrap a Next.js 16 project with App Router, TypeScript, and Tailwind in one command.

**Backend:** Google ADK CLI scaffold (`adk new`) — official ADK project generator that produces a ready-to-run multi-agent Python project with correct `pyproject.toml`, agent directory structure, and `.env` convention.

### Selected Starters

#### Frontend: create-next-app

**Initialization Command:**

```bash
npx create-next-app@latest aria-frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"
```

**Architectural Decisions Provided by Starter:**

- **Language & Runtime:** TypeScript strict mode, Node.js 20+
- **Framework:** Next.js 16 with App Router (`app/` directory) — server components by default, client components opt-in
- **Styling Solution:** Tailwind CSS v4 — utility-first; CSS-native `@theme inline` replaces `tailwind.config.ts`; shadcn/ui components added post-init via `npx shadcn@latest init`
- **Build Tooling:** Turbopack (stable default in Next.js 16 — replaces Webpack as the production-ready bundler)
- **Linting/Formatting:** ESLint with Next.js config; Prettier added separately
- **Project Structure:** `src/app/` for routes, `src/components/` for UI, `src/lib/` for utilities
- **Real-time Transport:** Native `EventSource` API (SSE) for thinking panel; native `WebSocket` API for voice audio relay

#### Backend: Google ADK Python Scaffold

**Initialization Command:**

```bash
pip install google-adk
adk new aria-backend
cd aria-backend
```

**Architectural Decisions Provided by Starter:**

- **Language & Runtime:** Python 3.11+ (required for ADK v1.25 async patterns)
- **Framework:** Google ADK v1.25+ — declarative agent config, built-in OpenTelemetry, `adk run` dev server with hot reload
- **Package Management:** `pyproject.toml` + `pip`; `requirements.txt` for Docker layer caching
- **Agent Structure:** `agents/` directory with one Python file per agent; `__init__.py` exports root agent
- **Build Tooling:** Docker via `mcr.microsoft.com/playwright:v1.50.0-jammy` base image
- **Executor model:** `gemini-3-flash` with built-in computer use (via ADK `ComputerUseToolset`) — replaces `gemini-2.5-computer-use-preview-10-2025`
- **Testing:** pytest + ADK's built-in `adk eval` for agent evaluation
- **Deployment:** `adk deploy cloud-run --project $GCP_PROJECT --region us-central1 --min-instances 1`

**Note:** Project initialization using both commands above should be the first two implementation stories — frontend first, then backend scaffold with Playwright image configuration.

---

