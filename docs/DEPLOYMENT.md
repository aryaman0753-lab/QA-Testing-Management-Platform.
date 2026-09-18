# Deployment guide

## Development

Copy `.env.example` to `.env`, set independent JWT and encryption keys, then run:

```bash
docker compose up --build
```

The development stack exposes PostgreSQL, Redis, API, UI, automation, scheduler, load, and operations workers.

## Tests

```bash
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend-tests
```

Run the frontend test service separately when a single combined exit result is needed.

## Production

Populate a deployment-only `.env` with all values required by `docker-compose.prod.yml`, including explicit retention days. Validate first:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.prod.yml up -d
```

Terminate TLS at a trusted reverse proxy/load balancer and forward only the frontend/API entry point. Database and Redis have no published host ports. Set exact HTTPS CORS origins and `PUBLIC_BASE_URL`. Scale automation and load workers only after confirming global/project concurrency settings; the database remains the concurrency authority.

Deployment order is database/Redis, migration, API, then workers/UI. Check `/health/live`, `/health/ready`, `/metrics`, and `/api/v1/admin/system`. A readiness failure is expected if Redis or PostgreSQL is unavailable.

Roll back application containers only when the deployed code supports the current schema. Migration `0006` has a downgrade, but destructive downgrades remove Phase 6 operational history; back up and explicitly approve that action first.
