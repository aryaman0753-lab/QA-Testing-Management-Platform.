# Reporting and comparisons

Project QA reports use a 30-day window by default and accept optional environment/start/end filters. JSON, CSV, and PDF exports contain project/date context, execution summaries, API failures and latency, automation trends/flaky candidates, load percentiles and threshold violations, plus authorized bug links. Export sanitization recursively excludes credential-like fields; raw request authentication and response bodies are not included.

Automation comparison reports totals, pass/fail counts, duration, average step response time, new failures, and resolved failures. Load comparison retains RPS, P50/P90/P95/P99, failure rate, peak users, and endpoint differences. Values are factual deltas, not a synthetic quality score.

Flaky candidates require at least five recent final executions, both passes and failures, and at least two pass/fail alternations. The label is computed at read time and never disables or permanently mutates a test. Each candidate includes execution/pass/fail counts, failure percentage, and links to underlying run IDs.

Load-test thresholds (`max_p95_ms`, `max_failure_rate`, and `min_rps`) are the enforceable baseline criteria. Completed runs can also be marked as comparison baselines. Violations retain expected/actual/operator/unit data, emit failure notifications, and can be explicitly converted into linked bugs from the run screen.
