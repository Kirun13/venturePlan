# VenturePlan backend 1.0

Use the root README for startup, test and administration commands.

- app/auth.py: registration, password hashing, opaque cookie sessions and sign-in throttling.
- app/api/jobs.py: owned tasks, project filters/renaming, immutable versions, events and exports.
- app/db/jobs.py: atomic limits, claims, heartbeat, ownership, events, retries and completion.
- app/worker.py: bounded job execution and shutdown recovery.
- app/graph: observed graph, parallel research and one revision pass.
- app/agents: mock and OpenAI structured outputs, provider citations and usage.
- app/finance: deterministic finance/scenarios and review rules.
- app/exports.py: Unicode PDF, DOCX and JSON exports.
- app/manage.py: explicit legacy-data assignment and database backups.
- alembic: incremental migrations from the original job schema.

GET /health checks the process. GET /ready checks database connectivity.
POST /plans/generate has been retired with HTTP 410 so generation always uses persisted jobs and per-user limits.
No API keys or detailed provider exceptions are sent to the browser.

The Docker production environment is Linux/Python 3.12. Native development requires Python 3.11+ and PostgreSQL.
Integration tests accept only the dedicated ventureplan_test database and force mock mode.
