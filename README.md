# QAHub - Phase 5

QAHub is a project-scoped QA platform with authentication, team membership, bug
tracking, secure functional API testing, controlled load/performance testing,
and reusable scheduled API automation. Phase 5 adds separate automation and
scheduler workers while preserving the Phase 1-4 workflows.

## Phase 5 - Advanced Automation & Scheduled Testing

- Project-scoped suites, ordered cases, and a visual six-type step builder
- Saved or standalone HTTP requests, assertions, extraction, assignment, delays,
  and simple conditions with `${variable}` and `{{variable}}` substitution
- Redis-backed execution, cancellation, attempt history, and automatic result aggregation
- Five-field cron schedules with IANA timezones and overlapping-run prevention
- Opt-in failure bugs linked to runs/results, with unresolved-failure deduplication
- Dashboard, run history/detail, schedules, statistics, and failure trends
- Encrypted secrets, masked results, destination allowlists, bounded requests,
  production safeguards, and project/role checks

See [the automation guide](docs/AUTOMATION.md) for API examples, configuration,
worker operations, limitations, and a manual verification checklist.

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 automation-worker scheduler-worker
```

The backend applies migration `0005_automation` before the new workers start.
For local development, run `alembic upgrade head`, then start each worker in a
separate terminal from `backend/` with the same database, Redis, and secret keys:

```sh
python -m workers.automation.worker
python -m workers.automation.scheduler
```

## Phase 4 - Load & Performance Testing

- Reusable standalone or API-request-backed definitions with smoke, baseline,
  load, stress, spike, soak, and custom profiles
- Redis queue plus a dedicated Locust worker container with CPU/memory limits
- Server-enforced user, spawn-rate, duration, RPS, and concurrency ceilings
- Separate lifecycle and result states, worker heartbeats, stale-run recovery,
  cancellation, immutable configuration snapshots, and configurable retention
- Aggregate RPS, failure rate, average/min/max, p50/p75/p90/p95/p99, HTTP status,
  endpoint, error, and sampled time-series metrics; raw response bodies are not kept
- Project and server hostname allowlists, DNS/IP/redirect revalidation, secret
  masking, private/metadata address blocking, and production execution controls
- Live polling dashboard, run history, baselines, comparisons, CSV/JSON reports,
  threshold pass/fail results, and editable bugs linked to threshold violations

### Load execution architecture

```text
FastAPI validates policy + target -> Redis run-id queue -> dedicated load-worker
    -> re-resolve environment/secrets + revalidate target -> Locust runner
    -> aggregate samples/endpoints/errors -> Postgres -> polling UI/report/bug
```

The queue contains identifiers only. Secrets remain encrypted in definitions,
are resolved inside the worker immediately before execution, and never appear in
the queue, run snapshot, logs, metrics, or report URLs.

## Phase 3 - API & URL Testing

- Saved collections and requests with GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS
- Enabled/disabled query parameters and headers; JSON, URL-encoded form,
  multipart text fields, raw text, and empty bodies
- No auth, bearer token, basic auth, and header/query API-key authentication
- Project environments with encrypted secret values and masked API/UI output
- Runtime variables with deterministic precedence: runtime > values extracted
  earlier in the run > selected environment
- Reusable assertion engine for status, response time, body, JSON path, headers,
  and JSON values; JSON-path/header extractors support collection chaining
- Single-request, selected-request, and sequential collection runs with persistent
  `API-RUN-001`-style history and response retention controls
- Quick URL health checks, project API analytics, and editable bug suggestions
  linked back to failed API results
- Server-enforced project isolation and role policy: Admin/QA manage and execute,
  Developer executes/views, and Project Manager views results/reports

### Execution architecture

```text
Saved request -> VariableResolver -> outbound URL validator/DNS pinning
              -> async HTTP client -> captured response -> AssertionEngine
              -> extractors -> persisted test run/result -> optional linked bug
```

Request definitions, execution outcomes, assertions, and bugs remain separate
models. Collection execution is deliberately sequential in Phase 3, which keeps
functional behavior deterministic and leaves the execution service reusable by
future queue workers.

### Outbound-request security

Arbitrary targets are treated as hostile input. Only HTTP(S) is accepted;
embedded credentials, localhost/local names, private/reserved/non-global IPs,
and mixed public/private DNS answers are rejected by default. The validated IP
is pinned for the connection, the peer is checked when the transport exposes
it, and every redirect is re-resolved and revalidated. Proxy environment
variables are ignored. TLS verification is on by default and can only be
disabled when server policy explicitly permits it.

Execution endpoints also enforce authentication, project authorization, a
configurable per-user rate limit, a bounded timeout and redirect count, and a
streaming maximum response size. Only a configurable response-body prefix is
retained. Authentication/header/environment secrets are encrypted at rest and
masked on reads; errors, analytics, audit records, and persisted resolved URLs
exclude authentication and query values. Response content is rendered only as
text in React, never injected as HTML.

`API_ALLOW_PRIVATE_NETWORKS=true` and `API_ALLOW_INSECURE_SSL=true` are escape
hatches for a trusted local development deployment only. Do not enable them on
an internet-facing instance.

## Phase 2 Features

- Human-readable, concurrency-safe project bug keys such as `ECOM-001`
- Bug creation/editing, soft archiving, assignment to project members, and a
  validated status workflow from `NEW` through `CLOSED`, including reopening
- Independent severity (`CRITICAL`–`TRIVIAL`) and priority (`URGENT`–`LOW`)
- Server-side search, combined filters, sorting, and pagination
- Plain-text comments with author/admin moderation
- Screenshots, images, text/log files, and small-video evidence with content
  signature, extension, filename, and size validation
- Immutable audit timeline for status, assignment, field, comment, attachment,
  and archive events
- Project/global statistics, charts, created-over-time trends, and CSV reports
- Backend role and project-membership authorization for every operation

## 1. Project Overview

A user can register, log in, create a project, add teammates, create and assign
bugs, progress them through developer and QA verification, attach evidence,
comment, reopen failures, close verified fixes, and inspect the full history.
Everything else in the codebase (the module layout, the role system, the
membership model) exists to make the next phases additive instead of requiring
a rewrite of auth/users/projects.

## 2. Architecture

```
                    QAHub
                      |
       +--------------+--------------+
       |              |              |
     Auth           Users        Projects
  (JWT, bcrypt)   (directory)   (CRUD + membership)
                                     |
                              Bug Management
                    (workflow, evidence, audit, analytics)
                                     |
                          [Later phases: test runs,
                           API/load testing, automation]
```

- **Backend**: FastAPI + SQLAlchemy 2.0 ORM (sync) + Alembic migrations, organized
  by feature module (`auth`, `users`, `projects`, `bugs`, `system`) rather than
  by layer, so later modules can be added without rewriting existing ones.
- **Frontend**: React + TypeScript SPA (Vite), talking to the API over Axios with
  a JWT bearer token.
- **Database**: PostgreSQL in production/Docker. Automated tests run against an
  in-memory SQLite database instead (see "Testing" below) — this is a deliberate
  choice, not a limitation of the schema.
- **Redis**: wired into configuration and Docker Compose (`REDIS_URL`) but not
  used by any business logic yet. It's there so a future module (e.g. rate
  limiting, background job queues for load testing) doesn't need new
  infrastructure wiring.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the module layout and the specific
decisions made to keep Phase 2+ additive.

## 3. Technology Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Auth | JWT (PyJWT), bcrypt via Passlib |
| Database | PostgreSQL (production), SQLite (automated tests only) |
| Cache/queue-ready | Redis |
| Frontend | React 18, TypeScript, Vite, React Router, Axios |
| Infra | Docker, Docker Compose |
| Testing | pytest, httpx (FastAPI TestClient) |

## 4. Folder Structure

```
qahub/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, middleware, exception handlers
│   │   ├── core/                  # config, security (JWT/bcrypt), dependencies, logging
│   │   ├── database/
│   │   │   ├── database.py        # engine/session
│   │   │   └── models/            # SQLAlchemy models (User, Project, ProjectMember)
│   │   ├── auth/                  # register/login/me
│   │   ├── users/                 # user directory endpoints
│   │   ├── projects/              # project CRUD + membership endpoints
│   │   ├── system/                # /health
│   │   ├── common/exceptions.py   # domain exceptions -> consistent HTTP responses
│   │   └── seed.py                # development seed data
│   ├── alembic/                   # migrations
│   ├── tests/                     # pytest suite (SQLite-backed)
│   ├── requirements.txt           # production deps
│   ├── requirements-dev.txt       # + pytest/httpx
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                   # axios client + one file per resource
│   │   ├── context/                # AuthContext, ToastContext
│   │   ├── components/            # layout (Sidebar/Topbar) + ui (Button/Modal/...)
│   │   ├── pages/                 # Login, Register, Dashboard, Projects, ProjectDetail, Profile
│   │   └── types/                 # shared TS types mirroring the API schemas
│   └── Dockerfile                 # multi-stage build -> nginx
├── docker-compose.yml
├── .env.example
└── README.md / ARCHITECTURE.md
```

## 5. Prerequisites

- Docker Desktop (or Docker Engine + Compose v2) — the only requirement to run
  the whole stack.
- For local (non-Docker) development: Python 3.12+, Node.js 20+, and a local
  PostgreSQL instance.

## 6. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` and set a real `JWT_SECRET_KEY` (the example value is a placeholder
and must never be used outside local development). All variables are documented
inline in `.env.example`.

## 7. Docker Setup (recommended)

```bash
docker compose up --build
```

This starts five containers: `db` (Postgres), `redis`, `backend` (runs
`alembic upgrade head` then Uvicorn on port 8000), `load-worker` (the isolated
Locust consumer), and `frontend` (Vite build served by nginx on port 5173).
Once healthy:

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs (Swagger) and http://localhost:8000/redoc
- Health check: http://localhost:8000/health

To seed development accounts into the Dockerized database:

```bash
docker compose exec backend python -m app.seed
```

## 8. Database Setup (migrations)

Migrations are managed with Alembic and are required — the app does not rely
on `create_all()` in production.

```bash
cd backend
alembic upgrade head      # apply all migrations
alembic downgrade base    # roll back everything (dev only)
```

The Docker backend image runs `alembic upgrade head` automatically on
container start.

## 9. Running the Backend (without Docker)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# Point at a local Postgres (see backend/.env.example), then:
alembic upgrade head
python -m app.seed          # optional: creates dev accounts, see below
uvicorn app.main:app --reload
```

In another terminal, start the dedicated load worker (Redis must be available):

```bash
cd backend
python -m workers.load_testing.worker
```

> **Note on Python 3.14 / Windows**: if you're on a very new Python and hit a
> `link.exe failed` error installing `pydantic-core`, or an `OSError` on
> `psycopg_binary...dll` mentioning long paths, see "Development Workflow"
> below — both are environment quirks unrelated to the application code.

## 10. Running the Frontend (without Docker)

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000/api/v1
npm install
npm run dev             # http://localhost:5173
```

`npm run build` type-checks (`tsc --noEmit`) and produces a production build in
`dist/`.

## 11. Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

The pytest suite covers Phases 1/2 plus API definition CRUD, collection runs,
chaining, persistence, analytics, bug linking, permissions, secret masking,
HTTP construction, every supported method, assertions, SSRF rejection,
redirect validation, timeouts, response-size limits, load thresholds, target
allowlists, queue/concurrency behavior, cancellation, run history, reports,
baselines, and an isolated real Locust execution. Vitest covers the bug
workflow and the API builder's methods, parameters, body, authentication,
assertions, execution response, collection tree, load form, production warning,
threshold editor, and time-series presentation.

```bash
cd frontend
npm test
npm run build
```

**Test database strategy**: tests run against an isolated **in-memory SQLite**
database (see `tests/conftest.py`), created fresh and torn down for every test
function. This was a deliberate choice so `pytest` never touches a developer's
real Postgres database — there is nothing to configure and nothing to
accidentally wipe. The same SQLAlchemy models and Alembic migrations also run
against SQLite (verified manually during development) via a portable `GUID`
column type, so this isn't testing a different schema than production uses.

## 12. API Documentation

Interactive docs are auto-generated by FastAPI:

- Swagger UI: `/docs`
- ReDoc: `/redoc`

Routes are tagged by authentication/project/bug concern and by **API
Collections**, **API Requests**, **API Environments**, **API Execution**, and
**API Test Runs**.

### API testing endpoints

```http
POST/GET    /api/v1/projects/{project_id}/api/collections
GET/PUT/DELETE /api/v1/api/collections/{collection_id}
POST/GET    /api/v1/api/collections/{collection_id}/requests
GET/PUT/DELETE /api/v1/api/requests/{request_id}
POST        /api/v1/api/requests/{request_id}/execute
POST        /api/v1/api/collections/{collection_id}/execute
POST        /api/v1/projects/{project_id}/api/health-check
GET/POST    /api/v1/projects/{project_id}/api/environments
GET         /api/v1/projects/{project_id}/api/analytics
GET         /api/v1/api/runs?project_id={project_id}
GET         /api/v1/api/runs/{run_id}
GET         /api/v1/api/results/{result_id}/bug-suggestion
POST        /api/v1/api/results/{result_id}/bugs
```

### Load-testing endpoints

```http
POST/GET    /api/v1/projects/{project_id}/load-tests
GET/PUT     /api/v1/projects/{project_id}/load-tests/settings
GET         /api/v1/projects/{project_id}/load-tests/runs
GET         /api/v1/projects/{project_id}/load-tests/runs/compare
GET/PATCH/DELETE /api/v1/load-tests/{test_id}
POST        /api/v1/load-tests/{test_id}/run
GET         /api/v1/load-tests/runs/{run_id}
POST        /api/v1/load-tests/runs/{run_id}/stop
POST        /api/v1/load-tests/runs/{run_id}/baseline
GET         /api/v1/load-tests/runs/{run_id}/metrics
GET         /api/v1/load-tests/runs/{run_id}/endpoints
GET         /api/v1/load-tests/runs/{run_id}/errors
GET         /api/v1/load-tests/runs/{run_id}/report.json
GET         /api/v1/load-tests/runs/{run_id}/report.csv
GET/POST    /api/v1/load-tests/runs/{run_id}/bug-suggestion|bugs
```

To run tests from the UI, open a project, select **API Testing**, create a
collection/request, optionally select an environment, add assertions in the
Tests tab, then choose **Send** or run the collection. Seeded example URLs use
the non-routable `api.example.test` placeholder and must be edited before use;
the product does not depend on a third-party test API.

### Bug API examples

```http
POST /api/v1/projects/{project_id}/bugs
GET  /api/v1/projects/{project_id}/bugs?page=1&page_size=20&status=REOPENED&severity=HIGH&search=checkout
GET  /api/v1/bugs/{bug_id}
PATCH /api/v1/bugs/{bug_id}
PATCH /api/v1/bugs/{bug_id}/assignee
PATCH /api/v1/bugs/{bug_id}/status
POST /api/v1/bugs/{bug_id}/comments
POST /api/v1/bugs/{bug_id}/attachments
GET  /api/v1/projects/{project_id}/bugs/analytics
GET  /api/v1/projects/{project_id}/bugs/report.csv
```

```json
{
  "title": "Goal notes are not visible to employee",
  "description": "Manager notes do not appear for the employee.",
  "steps_to_reproduce": ["Login as manager", "Add a note", "Login as employee"],
  "expected_result": "The note is visible.",
  "actual_result": "The note is missing.",
  "severity": "HIGH",
  "priority": "HIGH",
  "environment": "QA"
}
```

## 13. Environment Variables

See [`.env.example`](.env.example) (used by Docker Compose) and
[`backend/.env.example`](backend/.env.example) / [`frontend/.env.example`](frontend/.env.example)
for local, non-Docker development. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string (Postgres in prod/Docker) |
| `REDIS_URL` | Redis queues for load testing and automation; scheduler coordination |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `VITE_API_BASE_URL` | Frontend → backend base URL |
| `ATTACHMENT_STORAGE_DIR` | Configurable local bug-evidence directory |
| `MAX_ATTACHMENT_SIZE_MB` | Per-file evidence limit (default 10 MB) |
| `SECRET_ENCRYPTION_KEY` | Optional Fernet key material for API secrets; falls back to a key derived from the JWT secret |
| `API_REQUEST_TIMEOUT_SECONDS` / `API_MAX_TIMEOUT_SECONDS` | Default and maximum execution timeout |
| `API_MAX_RESPONSE_SIZE_MB` | Maximum streamed response size before execution fails |
| `API_RESPONSE_BODY_RETENTION_BYTES` | Maximum response-body prefix persisted per result |
| `API_MAX_REDIRECTS` | Redirect cap; every destination is independently validated |
| `API_EXECUTIONS_PER_MINUTE` | Per-user execution/health-check rate limit per backend process |
| `API_ALLOW_PRIVATE_NETWORKS` | Trusted-development override for private destinations (default false) |
| `API_ALLOW_INSECURE_SSL` | Trusted-development override allowing TLS verification off (default false) |

## 14. Development Workflow

- Business logic lives in `service.py` files, not in routers — routers only
  handle request/response shapes and call a service function.
- Domain errors are raised as typed exceptions (`app/common/exceptions.py`) and
  translated to HTTP responses in one place (`app/main.py`), so every endpoint
  returns errors in the same `{"detail": ...}` shape.
- New Phase 2+ modules (`bugs/`, `api_testing/`, `load_testing/`, ...) should
  follow the same `router.py` / `schemas.py` / `service.py` pattern as
  `projects/`, and depend on `app.core.dependencies.get_current_user` for auth
  — never re-implement token parsing.

**Architecture decisions worth knowing about:**

1. **Project creation is restricted to `ADMIN` and `QA_ENGINEER` system roles.**
   The creator automatically becomes that project's `OWNER`. This is a Phase 1
   judgment call (not explicitly specified) — it seemed like the safer default
   for a QA tool versus letting any role spin up projects.
2. **`GET /api/v1/users` is open to any authenticated user**, not just `ADMIN`.
   It's needed so a project `OWNER` who isn't a system `ADMIN` can still look up
   teammates to add as project members. The `require_admin` dependency still
   exists in `app/core/dependencies.py` for a future admin-only action (e.g.
   deactivating a user) — Phase 1 just doesn't have one yet.
3. **Project keys are auto-uppercased, not rejected, when lowercase.** `ecom` →
   `ECOM`. They must still match `^[A-Z][A-Z0-9]{1,9}$` after uppercasing.
4. **Deleting a project archives it (`status=ARCHIVED`)** instead of removing
   the row, per the spec's "prefer archiving" guidance. There is currently no
   "unarchive" endpoint — restoring uses the same `PUT` update endpoint.
5. **A project can't lose its last `OWNER`** — removing the sole owner is
   rejected with 409, to avoid orphaning a project.
6. **A non-member gets 404, not 403, when reading a project they don't belong
   to** — this avoids confirming a project key/ID exists to someone who isn't
   supposed to see it.
7. **Environment quirks hit while building this** (Python 3.14 was very new at
   the time): `pydantic-core`/`sqlalchemy` needed newer-than-originally-pinned
   versions to ship `cp314` wheels (older pins tried to compile from source via
   Rust/maturin and failed without MSVC build tools); `bcrypt` is pinned to
   `4.0.1` specifically because Passlib 1.7.4 reads an internal
   `bcrypt.__about__.__version__` attribute that 4.1+ removed — pinning avoids
   a harmless-but-noisy warning on every password hash. On Windows, installing
   `psycopg[binary]` from a very deeply nested folder can hit `MAX_PATH`; if you
   see an `OSError` naming `psycopg_binary...dll`, install the venv somewhere
   with a shorter path, or enable Windows long-path support.

## 15. Phase 2 Permissions and Storage

- `ADMIN`: full access, arbitrary status recovery, moderation, and archiving.
- `QA_ENGINEER`: create/triage/edit/assign, verify/reopen, comment, and upload.
- `DEVELOPER`: view assigned bugs, edit technical fields, advance assigned work,
  comment, and upload technical evidence.
- `PROJECT_MANAGER`: view project bugs, analytics/reports, and comment.

Assignment always requires an active project member. Non-members receive a
not-found response, and user-entered descriptions/comments render as plain text.

`LocalStorage` in `backend/app/bugs/storage.py` is the initial evidence storage
boundary. Metadata lives in PostgreSQL; bytes live in the configurable directory
(a persistent Compose volume by default). It can later be replaced with an
S3-compatible implementation without changing the API schemas.

API-generated bugs use the nullable
`bugs.discovered_from_test_result_id` foreign key. Bug creation remains an
explicit, editable QA action; the source result is preserved without folding
test-result fields into the bug model.

## 16. Future Roadmap

- `test_cases/` — test case management
- Browser/mobile engines behind the automation engine interface
- `reports/` — aggregating results from the above
- `notifications/` — using the membership model already in place to know who to
  notify about what project

None of these require changing `auth`, `users`, `projects`, or the database
session/dependency setup — that's the point of Phase 1.

## Phase 4 operational limits

- Rate limiting is intentionally process-local in Phase 3. A multi-replica
  deployment should move counters to Redis.
- Collection runs execute sequentially in the request worker and are intended
  for short functional suites. Long suites should become queued Redis jobs.
- JSON path uses the documented deterministic subset (`$.field`, nested fields,
  and numeric array indexes), not the full JSONPath language.
- Multipart bodies currently support text fields, not arbitrary file upload
  from the API builder.
- Stored response bodies are truncated; full large bodies are not archival data.
- DNS, time-to-first-byte, and total timing are reported where practical.
  Connection and TLS phase timings are not claimed because HTTPX does not expose
  them reliably through the current transport API.

Load generation is intentionally single-worker and polling-based in this phase.
Distributed generators, multi-region orchestration, Kubernetes autoscaling,
cloud execution, browser performance testing, AI recommendations, and automated
production scheduling are explicitly outside the current scope.
