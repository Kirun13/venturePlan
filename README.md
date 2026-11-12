# VenturePlan

A local multiuser business-planning app built with FastAPI, LangGraph, PostgreSQL and Next.js.
Market and competitor agents run in parallel, followed by operations, deterministic Python finance and validation. A reviewer can request one revision; unresolved issues remain visible in the draft. The workspace provides agent progress, saved versions and PDF, DOCX and JSON exports.

## Requirements

- Docker Desktop with the engine running and Docker Compose v2.
- Free local ports **3000** and **8000**.
- An OpenAI API key only if you enable real model calls. Mock mode works without one.

Docker installs Python, Node.js and application dependencies inside the containers.

## Install and run

Extract the source archive, open PowerShell in the `business-plan-mas` folder, then run:

```powershell
# First setup only: keep an existing .env unchanged.
if (-not (Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
docker compose up --build -d
docker compose ps
```

On Linux or macOS, use `cp backend/.env.example backend/.env` for the first setup, then the same Docker commands.

Open [the workspace](http://localhost:3000), create an account with a password of at least 12 characters, and select **Create a business plan**. Database migrations run automatically. The first build downloads dependencies and may take several minutes.

The default `AGENT_MODE=mock` uses placeholder research and costs. To enable real agents, edit `backend/.env`:

```dotenv
AGENT_MODE=openai
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-id
OPENAI_WEB_SEARCH=false
```

Set `OPENAI_MODEL` to an API model available to your account. Real generation uses paid provider calls. Set `OPENAI_WEB_SEARCH=true` to enable search for the research agents; findings without provider citations remain unverified assumptions. Keep API keys in `backend/.env` and out of the frontend.

Apply backend configuration changes:

```powershell
docker compose up -d --force-recreate backend worker
```

## Everyday commands

```powershell
docker compose logs --tail=100 backend worker  # Diagnose a failed task
docker compose down                          # Stop; retain the database volume
docker compose up -d                         # Start existing containers
```

API documentation is at [localhost:8000/docs](http://localhost:8000/docs); database readiness is at [localhost:8000/ready](http://localhost:8000/ready).

## Development and checks

To develop the frontend locally, install Node.js 22 and npm. Start the Docker stack first, then stop its frontend to free port 3000:

```powershell
docker compose stop frontend
npm --prefix frontend ci
npm --prefix frontend run dev
```

The local frontend proxies `/api` to the backend on port 8000. Use `NEXT_PUBLIC_API_URL=/api` if creating `frontend/.env`.

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run build
docker compose -p ventureplan-tests -f compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p ventureplan-tests -f compose.test.yml down
```

Backend tests use a separate temporary database and mock agents. Frontend browser tests are in `frontend/tests`; install Chromium with `npm --prefix frontend exec -- playwright install chromium`, then run `npm --prefix frontend run test:e2e` against a mock instance.

## Source layout

- `backend/app/graph`, `agents`, `finance`: orchestration, specialist roles, calculations and validation.
- `backend/app/api`, `db`, `worker.py`: authenticated jobs, storage and background execution.
- `backend/alembic`, `backend/tests`: migrations and backend tests.
- `frontend/app`, `lib`, `tests`: workspace UI, API client and browser tests.

Generated plans support early planning; demand and operating costs still require independent verification. Financial scenarios exclude taxes, financing and launch ramp-up.
