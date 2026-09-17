# Phase 5 automation guide

## Start and build a suite

Apply `alembic upgrade head` from `backend/`. Migration `0005_automation` adds
automation suites, cases, steps, runs, attempt results, schedules, and failure
deduplication records, plus nullable automation source links on bugs. Existing
Phase 1-4 data and services remain in place.

Open a project's **Automation** workspace. Create a suite, select a Phase 3
environment, and specify the exact hosts you are authorized to test. Add ordered
cases, then steps. Saved HTTP steps reference requests from that same project;
standalone HTTP steps use the existing method, body, header, query, and auth
editors. Reorder, duplicate, or disable steps as needed. Activate the suite before
scheduling it. The development seed includes a non-running DRAFT smoke example
using `api.example.test`; replace that placeholder with your authorized target.

Supported step types:

| Type | Configuration |
| --- | --- |
| `HTTP_REQUEST` | `api_request_id`, or `config.request` using the Phase 3 request schema |
| `ASSERTION` | `config.assertions` with source, operator, target, expected |
| `EXTRACT_VARIABLE` | JSON path/header, destination name, optional `strip_prefix` |
| `SET_VARIABLE` | Variable name, value, and secret flag |
| `DELAY` | Seconds, capped by server policy |
| `CONDITION` | Simple source/operator/target/expected guard for the next step |

Any step can also have its own `condition`. Conditions are declarative: no code
or arbitrary expressions are evaluated. A false condition skips its target.
Variables resolve from runtime values, then values assigned/extracted earlier
in the run, then the selected environment. Both `${token}` and `{{token}}` work;
undefined variables fail explicitly. Values remain within that run.

## API reference

All paths below are relative to `/api/v1` and require a bearer token. Admins and
QA engineers with project write access manage and execute automation; project
viewers can read. Requests for another project's resources return not-found.

| Method | Path | Operation |
| --- | --- | --- |
| GET, POST | `/projects/{project_id}/automation/suites` | List/create suites |
| GET, PATCH, DELETE | `/automation/suites/{id}` | Read/update/archive suite |
| POST | `/automation/suites/{id}/cases` | Create case |
| PATCH, DELETE | `/automation/cases/{id}` | Update/delete case |
| PUT | `/automation/suites/{id}/cases/reorder` | Set case order with `{ "ids": [...] }` |
| POST | `/automation/cases/{id}/steps` | Add step |
| PATCH, DELETE | `/automation/steps/{id}` | Update/delete step |
| PUT | `/automation/cases/{id}/steps/reorder` | Set step order |
| POST | `/automation/suites/{id}/run` | Queue manual run |
| GET | `/automation/runs/{id}` | Run and attempt results |
| GET | `/automation/runs/{id}/results` | Step results |
| POST | `/automation/runs/{id}/stop` | Request cancellation |
| GET | `/projects/{id}/automation/runs` | Paginated history |
| GET, POST | `/projects/{id}/automation/schedules` | List/create schedules |
| PATCH, DELETE | `/automation/schedules/{id}` | Edit, enable/disable, delete |
| GET | `/projects/{id}/automation/statistics` | Counts, rates, duration, recent failures/trends |

Paginated lists accept `page` and `page_size` and return `items`, `total`, `page`,
`page_size`, and `total_pages`. Run filters include `suite_id`, `environment_id`,
`status`, `created_from`, and `created_to` (ISO timestamps). Run details contain
`attempt` and `is_final` for each result, so a failed original attempt remains
visible even when a retry passes. Aggregate counts reflect final attempts.

Create a suite:

```json
{
  "name": "QA account lifecycle",
  "environment_id": "ENVIRONMENT_UUID",
  "status": "ACTIVE",
  "allowed_hosts": ["qa-api.example.test"],
  "max_retries": 2,
  "auto_create_bugs": false
}
```

Create a case with `{ "name": "Login and validate user", "timeout": 60 }`, then
POST each step to `/automation/cases/{case_id}/steps` in order. This login request
uses secret environment variables instead of literal credentials:

```json
{
  "name": "Login",
  "step_type": "HTTP_REQUEST",
  "order_index": 0,
  "config": {
    "request": {
      "name": "Login",
      "method": "POST",
      "url": "${base_url}/login",
      "body_type": "JSON",
      "body": "{\"email\":\"${email}\",\"password\":\"${password}\"}",
      "authentication_type": "NONE"
    }
  }
}
```

Extract the token from the response:

```json
{
  "name": "Extract token",
  "step_type": "EXTRACT_VARIABLE",
  "order_index": 1,
  "config": {
    "source": "JSON_PATH", "path": "$.data.token",
    "variable_name": "token", "is_secret": true
  }
}
```

For a response header use `source: "HEADER"`, `path: "Authorization"`, and
`strip_prefix: "Bearer "`. A later request can use bearer authentication with
`authentication_config: { "token": "${token}" }`, and a created user can be
extracted with `$.data.id` into `user_id` for `${base_url}/users/${user_id}`.

Assert status, JSON path existence, and response time:

```json
{
  "name": "Validate user",
  "step_type": "ASSERTION",
  "order_index": 3,
  "config": {
    "assertions": [
      {"source": "STATUS_CODE", "operator": "EQUALS", "expected": "200"},
      {"source": "JSON_PATH", "operator": "EXISTS", "target": "$.data.id"},
      {"source": "RESPONSE_TIME", "operator": "LESS_THAN", "expected": "1000"}
    ]
  }
}
```

Other operators include `NOT_EQUALS`, `GREATER_THAN`, `CONTAINS`, and
`NOT_CONTAINS`; body and header sources are also supported. Results retain
assertion success/failure and messages while masking response-derived values.

Queue with `POST /automation/suites/{suite_id}/run` and `{}`. Observe
`QUEUED -> RUNNING -> PASSED/FAILED/CANCELLED`; execution is never performed in
the API handler. Add the final DELETE cleanup request explicitly if desired:
failed cases skip later steps, so cleanup is not a guaranteed finally block.

## Schedules

Create with:

```json
{
  "suite_id": "SUITE_UUID",
  "environment_id": "ENVIRONMENT_UUID",
  "cron_expression": "*/5 * * * *",
  "timezone": "America/New_York",
  "enabled": true
}
```

Five-field cron supports `0 * * * *` (hourly), `0 9 * * *` (daily at 09:00), and
`0 9 * * 1-5` (weekdays). Supply an IANA timezone; persisted execution timestamps
are UTC. Invalid cron expressions/timezones are rejected on save. Inspect
`next_run_at`, `last_run_at`, and `last_error`; PATCH `{ "enabled": false }` to
pause. Active runs of the same suite prevent overlap. Scheduling production is
intentionally disallowed. Missed intervals are not replayed as a burst.

## Worker operation and safety

Docker Compose starts PostgreSQL (`db`), Redis, backend, frontend, the existing
load-worker, automation-worker, and scheduler-worker. The backend migrates first;
new workers wait for its health check. To run locally, use the same `backend/.env`
in three terminals:

```sh
uvicorn app.main:app --reload
python -m workers.automation.worker
python -m workers.automation.scheduler
```

Redis holds run UUIDs only. Definitions and immutable snapshots encrypt secrets;
execution decrypts them only in memory. Results do not persist raw response
bodies, cookies, authorization headers, or extracted values. Keep
`SECRET_ENCRYPTION_KEY` and `JWT_SECRET_KEY` consistent across API and workers;
back up the encryption key with the database and do not rotate it without a
secret migration. Worker failures use sanitized error messages.

Both suite and optional server host allowlists are enforced. DNS resolution,
IP pinning, redirect revalidation, timeouts, and bounded streaming reuse Phase 3.
Cross-origin redirects are rejected. Loopback and metadata endpoints remain
blocked even if private QA networks are explicitly enabled. Only test systems
you control or are authorized to test.

Production requires `AUTOMATION_ALLOW_PRODUCTION=true`, an administrator, and
explicit confirmation on a manual run. A production-labelled environment is
essential: the platform cannot infer that an arbitrary host is production.
Do not enable private-network access on a public untrusted deployment.

### Environment variables

Set identical values on the API and both automation workers. Complete examples
are in root `.env.example` and `backend/.env.example`.

| Variable | Default / purpose |
| --- | --- |
| `AUTOMATION_ALLOW_PRODUCTION` | `false`; additional manual admin confirmation required |
| `AUTOMATION_ALLOW_PRIVATE_NETWORKS` | `false`; controlled private QA infrastructure only |
| `AUTOMATION_ALLOWED_HOSTS` | Empty; optional comma-separated server host ceiling |
| `AUTOMATION_MAX_CONCURRENT_RUNS` | `3` admitted active runs |
| `AUTOMATION_MAX_CONCURRENT_PER_PROJECT` | `2` |
| `AUTOMATION_MAX_CONCURRENT_PER_USER` | `1` |
| `AUTOMATION_MAX_CASES` / `AUTOMATION_MAX_STEPS` | `50` / `200` per suite |
| `AUTOMATION_MAX_RUN_SECONDS` | `900` overall deadline |
| `AUTOMATION_MAX_DELAY_SECONDS` | `30` per delay |
| `AUTOMATION_MAX_RETRIES` | `3` ceiling; each suite chooses 0-3 |
| `AUTOMATION_STALE_RUN_SECONDS` | `120` heartbeat timeout |
| `AUTOMATION_QUEUE_TIMEOUT_SECONDS` | `900` queue timeout |
| `AUTOMATION_QUEUE_NAME` | `qahub:automation` |
| `AUTOMATION_SCHEDULER_INTERVAL_SECONDS` | `5` polling interval |
| `API_MAX_TIMEOUT_SECONDS` / `API_REQUEST_TIMEOUT_SECONDS` | `60` / `30`; shared HTTP limits |
| `API_MAX_RESPONSE_SIZE_MB` | `5`; shared streaming response cap |

### Retries, failure bugs, and limitations

HTTP retry attempts are separately persisted. Only GET, HEAD, and OPTIONS may
retry automatically; mutating requests are not replayed. Configuration, URL,
authentication-configuration, and validation failures are not retryable.
Enable `auto_create_bugs` per suite to create bugs for final failures and reuse
the same unresolved failure instead of producing duplicate bugs. Bug source
links lead back to the automation run and failed step; disabling the toggle
stops future automatic creation without deleting existing bugs.

Runs are sequential; there are no parallel branches, loops, arbitrary scripts,
browser/mobile engines, distributed step execution, or guaranteed cleanup
hooks. JSON path supports deterministic dotted fields and numeric indexes,
not the entire JSONPath language. Extracted values are masked even when marked
non-secret, so result inspection cannot be used to recover a token. Stop is
cooperative and cannot undo HTTP side effects already accepted by the target.

## Manual verification

1. Copy `.env.example` to `.env`, set secret keys, and run
   `docker compose up --build -d`. Confirm all seven services with
   `docker compose ps`; inspect worker logs. Do not claim this check passed if
   Docker is unavailable on the development machine.
2. Sign in as Admin or QA, create a project environment for an authorized QA
   API, and store credentials as secret environment values.
3. Create an ACTIVE suite with its host allowlist and a case containing login,
   extraction, authenticated request, and assertions. Run manually and confirm
   counts, timestamps, masked variables, and passing final status.
4. Make an assertion fail, enable automatic bugs, and run twice. Confirm one
   unresolved bug with links to the failing run/step and no leaked credentials.
5. Configure a safe GET request with a transient failure and `max_retries: 2`.
   Confirm original/retry attempts remain visible and final counts are correct.
6. Add a schedule for every minute in your timezone. Confirm `next_run_at`
   advances and one run is queued. Keep a run active across a due time and
   confirm no duplicate overlap; disable the schedule and verify it stops.
7. Stop a run containing a delay. Confirm cancellation, then verify a viewer
   cannot edit/run and a non-member cannot read it. Confirm localhost, metadata,
   an unlisted host, and unapproved production execution are rejected.
8. Recheck Phase 3 API execution and Phase 4 load execution. Run
   `python -m pytest -q` from backend and `npm test -- --run` plus `npm run build`
   from frontend.
