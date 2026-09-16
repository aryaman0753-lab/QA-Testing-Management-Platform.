import type { LoadMetric } from "../../types/loadTesting";

export function TimeSeriesChart({ metrics, metric = "p95" }: { metrics: LoadMetric[]; metric?: "p95" | "requests_per_second" | "active_users" | "failure_rate" }) {
  if (!metrics.length) return <div className="load-chart-empty">Metrics will appear while the worker is running.</div>;
  const values = metrics.map((item) => item[metric]); const max = Math.max(...values, 1); const width = 700; const height = 220;
  const points = values.map((value, index) => `${(index / Math.max(values.length - 1, 1)) * width},${height - (value / max) * (height - 20)}`).join(" ");
  return <div className="load-chart" aria-label={`${metric} time series`}><svg viewBox={`0 0 ${width} ${height}`} role="img"><title>{metric} over time</title><line x1="0" y1={height} x2={width} y2={height} /><polyline points={points} /></svg><div><span>{new Date(metrics[0].timestamp).toLocaleTimeString()}</span><strong>Peak {max.toFixed(2)}</strong><span>{new Date(metrics.at(-1)!.timestamp).toLocaleTimeString()}</span></div></div>;
}
