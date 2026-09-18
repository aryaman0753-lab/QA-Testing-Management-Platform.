# Production operations

Use unique high-entropy values for `JWT_SECRET_KEY`, `SECRET_ENCRYPTION_KEY`, database credentials, and every webhook/API key. Rotating the encryption key requires re-saving encrypted API-testing and webhook secrets. Never place secrets in image layers, source control, CI output, report metadata, or URLs.

Collect JSON stdout logs centrally. Every API request includes/returns `X-Request-ID`, status, path, and duration. User/project/job/run identifiers are logged by the service operation that owns them; passwords, cookies, authorization headers, API keys, tokens, and secrets are redacted or never supplied. Production responses use an error code/message/request ID and omit stack traces.

Prometheus can scrape `/metrics` using `monitoring/prometheus.yml`. Grafana may use that Prometheus source without being required locally. Instrumentation boundaries and request IDs are ready for an OpenTelemetry exporter, but no collector is mandatory. Restrict `/metrics` at the ingress or monitoring network.

Worker heartbeat rows become `UNAVAILABLE` after `WORKER_UNAVAILABLE_SECONDS`. Alert on readiness failures, unavailable workers, failed-job growth, nonzero failed webhook deliveries, and sustained queue growth. Queue values are `null` when Redis cannot be queried.

Retention is disabled when the three retention variables are unset. Production Compose requires explicit values for automation results, load results, and webhook deliveries. Baseline load runs are excluded from existing load cleanup. Run cleanup only after backups and policy approval.
