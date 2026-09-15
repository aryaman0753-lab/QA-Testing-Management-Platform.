# QAHub — Phase 1

QAHub is a QA/testing management platform. This is **Phase 1**: a production-ready
foundation covering authentication, users, projects, and project membership.
Bug tracking, API testing, load testing, test case management, reports, and
notifications are intentionally **not** implemented yet — they are placeholders
in the navigation ("Coming Soon") so Phase 1 doesn't have to be reworked to add
them later.

## 1. Project Overview

A user can register, log in, see a dashboard, create a project, view it, add
teammates to it as members, and log out. That's the full Phase 1 golden path.
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
                          [Phase 2+, not built yet]
                          Bugs, Test Management,
                          API Testing, Load Testing,
                          Reports, Workers
```

- **Backend**: FastAPI + SQLAlchemy 2.0 ORM (sync) + Alembic migrations, organized
  by feature module (`auth`, `users`, `projects`, `system`) rather than by layer,
  so a future `bugs/` or `api_testing/` module can be dropped in beside the
  existing ones without touching them.
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

This starts four containers: `db` (Postgres), `redis`, `backend` (runs
`alembic upgrade head` then Uvicorn on port 8000), and `frontend` (Vite build
served by nginx on port 5173). Once healthy:

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

28 tests cover registration, login, current-user, project CRUD, archiving, and
membership (add/list/remove, including permission checks and the "can't remove
the last owner" edge case).

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

Routes are tagged **Authentication**, **Users**, **Projects**, **Project
Members**, and **System**.

## 13. Environment Variables

See [`.env.example`](.env.example) (used by Docker Compose) and
[`backend/.env.example`](backend/.env.example) / [`frontend/.env.example`](frontend/.env.example)
for local, non-Docker development. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string (Postgres in prod/Docker) |
| `REDIS_URL` | Reserved for future modules |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `VITE_API_BASE_URL` | Frontend → backend base URL |

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

## 15. Future Roadmap (not built in Phase 1)

- `bugs/` — bug tracking, linked to a project (`ECOM-101` style IDs using the
  project `key` already in place)
- `test_cases/` — test case management
- `api_testing/` — API/URL test definitions and execution
- `load_testing/` + `workers/` — load test execution, likely via a queue backed
  by the Redis instance already provisioned
- `reports/` — aggregating results from the above
- `notifications/` — using the membership model already in place to know who to
  notify about what project

None of these require changing `auth`, `users`, `projects`, or the database
session/dependency setup — that's the point of Phase 1.
