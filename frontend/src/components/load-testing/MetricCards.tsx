import type { LoadRun, LoadRunDetail } from "../../types/loadTesting";

export function MetricCards({ run }: { run: LoadRun }) {
  const metrics = (run as Partial<LoadRunDetail>).metrics ?? [];
  const cards = [
    ["Users", `${metrics.length ? metrics.at(-1)!.active_users : 0} / ${run.virtual_users}`],
    ["Requests", run.total_requests.toLocaleString()], ["Success", run.successful_requests.toLocaleString()],
    ["Failed", run.failed_requests.toLocaleString()], ["RPS", run.requests_per_second.toFixed(2)],
    ["Failure rate", `${run.failure_rate.toFixed(2)}%`], ["Average", `${run.avg_response_time.toFixed(1)} ms`],
    ["p95", `${run.p95_response_time.toFixed(1)} ms`], ["p99", `${run.p99_response_time.toFixed(1)} ms`],
  ];
  return <div className="load-metric-cards">{cards.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}
