# QAHub Architecture

This document explains *why* the code is organized the way it is, specifically
so that later modules (API testing, load testing, test cases, reports,
notifications) can be added without modifying auth, users, projects, or the
database/session plumbing.

## Layering inside a module

Every backend module (`auth`, `users`, `projects`) follows the same three-file
shape:

```
module/
├── router.py    # HTTP layer only: parses request, calls service, shapes response
├── schemas.py   # Pydantic request/response models
└── service.py   # business logic, raises app.common.exceptions on failure
```

`router.py` never talks to the database directly and never contains an `if`
statement about permissions — that logic lives in `service.py` so it can be
unit-tested (or reused by a future CLI/worker) without going through FastAPI.

## Cross-cutting concerns live in `app/core` and `app/common`

- `app/core/config.py` — the only place that reads environment variables
  (`Settings`, a `pydantic-settings` model). No module should call
  `os.environ` directly.
- `app/core/security.py` — password hashing and JWT encode/decode. This is
  intentionally separate from `app/auth/` so a future worker or websocket
  handler can verify a token without importing the auth router.
- `app/core/dependencies.py` — `get_current_user`, `require_roles`,
  `require_admin`. Every protected endpoint in every module depends on
  `get_current_user`; there is exactly one implementation of "parse the bearer
  token and load the user."
- `app/common/exceptions.py` — domain exceptions (`NotFoundError`,
  `ConflictError`, `ForbiddenError`, `UnauthorizedError`) that any service can
  raise. `app/main.py` registers one exception handler per type, so every
  endpoint in every module returns the same `{"detail": "..."}` shape without
  each router needing its own try/except.

## Data model

```
User --< ProjectMember >-- Project --< Bug
                                      |--< BugComment
                                      |--< BugAttachment
                                      `--< BugHistory
```

`ProjectMember` is a real entity (with its own `id`, not just a composite key)
specifically so it can grow additional columns later (e.g. notification
preferences, a `joined_via` field) without a schema rewrite — a plain
association table would make that harder.

`Project.key` (e.g. `ECOM`) is unique and already in place so that Phase 2's
bug tracker can mint human-readable IDs like `ECOM-101` (`key` + a
per-project bug counter) without touching the `projects` table.

Both `User.role` (system role: `ADMIN`, `QA_ENGINEER`, `DEVELOPER`,
`PROJECT_MANAGER`) and `ProjectMember.project_role` (`OWNER`, `MEMBER`,
`VIEWER`) are stored as plain strings (`native_enum=False`) rather than
Postgres native enum types. Native enums require an `ALTER TYPE` migration
dance to add a new value; a string column just needs the Python `Enum` class
updated and a comment — which matters once `PROJECT_MANAGER`-specific
permissions or a `QA_LEAD` role show up in a later phase.

## Why UUID primary keys with a portable `GUID` type

`app/database/models/guid.py` defines a `TypeDecorator` that stores a native
`UUID` column on PostgreSQL but falls back to a `CHAR(32)` hex string on
SQLite. This means:

- Production (Docker/Postgres) gets proper native UUIDs, indexes, etc.
- The exact same models and the exact same Alembic migration also run
  against SQLite, which is what makes it possible for the automated test
  suite to run without a live Postgres instance (see README "Testing").

## Authorization model (Phase 1)

Two independent role systems, both already wired into the authorization
dependencies, ready for Phase 2 to layer bug/test permissions on top of:

1. **System role** (`User.role`) — coarse-grained, platform-wide. Phase 1 uses
   it for exactly one rule: only `ADMIN`/`QA_ENGINEER` may create a project.
2. **Project role** (`ProjectMember.project_role`) — scoped to one project.
   `OWNER` can manage the project and its membership; `MEMBER`/`VIEWER` can
   only read. A system `ADMIN` bypasses project-role checks entirely.

The bug module adds a third, orthogonal check: developers only see and advance
bugs assigned to them. QA engineers follow a transition map, while admins can
recover from any state. All checks live in `bugs/service.py` rather than relying
on the frontend.

## Bug numbering and future test results

Each project owns a `next_bug_number` counter. Bug creation locks that project
row, increments it, and stores a unique `(project_id, bug_number)` pair. The
display key combines the project key with the number, preventing duplicates
during concurrent reporting.

Future `TestResult` records can link to bugs through a nullable foreign key or a
many-to-many association table. Test execution is intentionally absent from
Phase 2; stable UUID bug identity keeps that later addition independent of the
human-readable key.

## Frontend structure

```
api/        one file per backend resource (auth.ts, users.ts, projects.ts),
            all going through a single axios instance (client.ts) that injects
            the bearer token and centralizes 401 handling.
context/    AuthContext (current user + token lifecycle) and ToastContext
            (global notifications), both consumed via hooks (useAuth, useToast).
components/
  layout/   Sidebar, Topbar, AppLayout — the authenticated app shell.
  ui/       Presentational, stateless building blocks (Button, Modal,
            EmptyState, LoadingSpinner) with no knowledge of the domain.
pages/      One file per route, composed from api/ + components/.
```

The sidebar's "Coming Soon" items (Bugs, API Tests, Load Tests, Reports,
Settings) are rendered from a static list in `Sidebar.tsx` — adding a real
route for one later means changing that list and adding a page, not
restructuring the shell.

### Token storage

All token persistence goes through `frontend/src/api/tokenStorage.ts`
(currently a thin `localStorage` wrapper). Every other file imports from
there rather than calling `localStorage` directly, so switching to an
httpOnly-cookie-based flow later is a one-file change.

## What Phase 2 should *not* need to touch

- `app/core/*`, `app/database/database.py`, `app/main.py`'s exception
  handlers, `frontend/src/api/client.ts`, `frontend/src/context/AuthContext.tsx`
- The `users` and `projects` tables/models (only additive migrations expected,
  e.g. a new nullable column)

If a Phase 2 change requires touching one of the above, that's a signal the
change is bigger than it looks and worth a design pass first.
