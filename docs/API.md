# API conventions

Interactive OpenAPI is available at `/docs` and ReDoc at `/redoc`. JWT APIs use `Authorization: Bearer <token>`. CI APIs use `X-QAHub-API-Key`. Project resources return 404 to callers without membership so object existence is not disclosed.

Errors have one envelope:

```json
{"error":{"code":"not_found","message":"Resource not found.","request_id":"..."}}
```

Validation errors additionally contain safe field details. Stack traces and submitted secret values are never returned. Send `X-Request-ID` to correlate a request; QAHub validates and echoes it.

List endpoints that can grow use `page` (1-based) and `page_size` (usually maximum 100) and return `items`, `page`, `page_size`, `total`, and `total_pages`. Operational delivery/notification lists use a bounded `limit` (maximum 500).

Public Phase 6 endpoints:

- `POST/GET /api/v1/ci/test-runs[/{run_id}]`
- `/api/v1/projects/{project_id}/integrations/api-keys`
- `/api/v1/projects/{project_id}/integrations/webhooks`
- `/api/v1/projects/{project_id}/integrations/webhook-deliveries`
- `/api/v1/notifications` and `/preferences`
- `/api/v1/projects/{project_id}/reports/qa` and `/export?format=json|csv|pdf`
- `/api/v1/projects/{project_id}/automation/compare?run_a=...&run_b=...`
- `/api/v1/projects/{project_id}/automation/flaky-tests`
- `/api/v1/projects/{project_id}/qa-dashboard`
- `/health`, `/health/live`, `/health/ready`, `/metrics`, and admin-only `/api/v1/admin/system`

Automation, load, bug, and reporting schemas/examples are also generated from their FastAPI request/response models in OpenAPI. See the dedicated CI, webhook, CLI, and automation guides for end-to-end examples.
