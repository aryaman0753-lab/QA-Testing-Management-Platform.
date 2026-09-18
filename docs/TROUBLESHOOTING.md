# Troubleshooting

- **`/health/ready` returns 503:** inspect its database/Redis fields, connectivity, credentials, DNS, and container health. `/health/live` distinguishes a live process from a ready service.
- **Worker shows unavailable:** confirm the correct worker container is running, migration `0006` is applied, clocks are synchronized, and `WORKER_UNAVAILABLE_SECONDS` exceeds the heartbeat interval.
- **CI returns 401:** use the one-time `qh_` key, not a JWT; confirm it is not expired/revoked and belongs to the requested project.
- **CI stays queued:** inspect Redis, automation queue size, automation worker heartbeat, host allowlists, and concurrency limits.
- **Webhook retries:** verify public HTTPS/DNS, receiver latency, 2xx responses, raw-body HMAC validation, and delivery history. Redirects/private targets are intentionally rejected.
- **Email is failed:** confirm all SMTP variables in the operations worker and test network/TLS/login outside QAHub. Credentials are intentionally absent from API responses.
- **Report has no data:** the default window is the last 30 days; check project/environment access and explicit date filters.
- **Migration mismatch:** run `alembic current`, `alembic heads`, back up, then `alembic upgrade head`. Do not stamp over an unapplied migration.
- **CLI exit 2:** the run may still be non-terminal, timed out, or configuration/auth/connectivity failed. `qahub test wait` prints each observed status to stderr.
