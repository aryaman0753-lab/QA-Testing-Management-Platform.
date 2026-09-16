from dataclasses import dataclass


@dataclass
class Summary:
    total_requests: int = 0
    failed_requests: int = 0
    requests_per_second: float = 0
    failure_rate: float = 0
    avg_response_time: float = 0
    p95_response_time: float = 0
    p99_response_time: float = 0


def evaluate_thresholds(summary: Summary, thresholds: dict) -> list[dict]:
    rules = [
        ("max_p95_ms", "P95 response time", summary.p95_response_time, "<=", lambda measured, limit: measured <= limit, "ms"),
        ("max_p99_ms", "P99 response time", summary.p99_response_time, "<=", lambda measured, limit: measured <= limit, "ms"),
        ("max_failure_rate", "Failure rate", summary.failure_rate, "<=", lambda measured, limit: measured <= limit, "%"),
        ("max_average_ms", "Average response time", summary.avg_response_time, "<=", lambda measured, limit: measured <= limit, "ms"),
        ("min_rps", "Requests per second", summary.requests_per_second, ">=", lambda measured, limit: measured >= limit, "rps"),
        ("max_error_count", "Error count", summary.failed_requests, "<=", lambda measured, limit: measured <= limit, ""),
    ]
    results = []
    for key, label, measured, operator, passes, unit in rules:
        limit = thresholds.get(key)
        if limit is None:
            continue
        results.append({"key": key, "label": label, "measured": round(float(measured), 2), "operator": operator, "threshold": limit, "unit": unit, "passed": passes(measured, limit)})
    return results
