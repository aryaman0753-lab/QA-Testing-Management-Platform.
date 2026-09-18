# Performance review

Phase 6 keeps high-volume histories indexed by project/time, delivery due-time, status, event, worker heartbeat, CI commit/branch, and notification user/time. Dashboard/report queries are project- and date-bounded; UI history lists are capped or paginated. Automation comparisons load only two runs, flaky detection caps its scan at 5,000 final results and returns at most 500 candidates, and reports cap embedded bug links/trends.

Redis handles distributed rate counters and execution queues. PostgreSQL remains the authority for job state, concurrency, heartbeats, delivery retries, and notification dedupe. Outbound email/webhooks never block API requests.

Measurable production review should record p50/p95/p99 API latency, report query duration by project size, queue wait time, worker throughput, database query plans, frontend bundle size, and webhook retry volume. Add indexes only from observed query plans; do not raise worker concurrency until CPU, database connections, target safety, and queue latency have been measured.

Known scale boundary: QA report generation is synchronous and suited to bounded project/date windows. Very large projects should move report assembly to a queued snapshot job and store immutable artifacts.
