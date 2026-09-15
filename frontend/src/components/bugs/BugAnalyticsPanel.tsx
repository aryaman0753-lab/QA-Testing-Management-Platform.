import type { BugAnalytics } from "../../types";

function Bars({ values }: { values: Record<string, number> }) {
  const max = Math.max(...Object.values(values), 1);
  return <div className="chart-bars">{Object.entries(values).map(([name, value]) => <div className="chart-row" key={name}><span>{name.replaceAll("_", " ")}</span><div><i style={{ width: `${(value / max) * 100}%` }} /></div><strong>{value}</strong></div>)}</div>;
}

function TimeChart({ points }: { points: BugAnalytics["created_over_time"] }) {
  if (!points.length) return <p className="muted">No creation data yet.</p>;
  const width = 500, height = 120, padding = 14, max = Math.max(...points.map((point) => point.count), 1);
  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : padding + index * ((width - padding * 2) / (points.length - 1));
    const y = height - padding - (point.count / max) * (height - padding * 2);
    return `${x},${y}`;
  }).join(" ");
  return <div><svg className="time-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Bugs created over time"><polyline points={coordinates} fill="none" stroke="currentColor" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />{coordinates.split(" ").map((pair) => { const [cx, cy] = pair.split(","); return <circle key={pair} cx={cx} cy={cy} r="4" fill="currentColor" />; })}</svg><div className="time-chart-labels"><span>{points[0].date}</span><span>{points.at(-1)?.date}</span></div></div>;
}

export function BugAnalyticsPanel({ analytics }: { analytics: BugAnalytics }) {
  return <><div className="card-grid bug-stats"><div className="stat-card"><span className="stat-value">{analytics.total}</span><span className="stat-label">Total Bugs</span></div><div className="stat-card"><span className="stat-value">{analytics.open}</span><span className="stat-label">Open Bugs</span></div><div className="stat-card"><span className="stat-value">{analytics.critical}</span><span className="stat-label">Critical</span></div><div className="stat-card"><span className="stat-value">{analytics.high_priority}</span><span className="stat-label">High Priority</span></div></div>
    <details className="panel analytics-panel"><summary>Bug analytics</summary><div className="analytics-grid"><div><h3>By Status</h3><Bars values={analytics.by_status} /></div><div><h3>By Severity</h3><Bars values={analytics.by_severity} /></div><div><h3>By Priority</h3><Bars values={analytics.by_priority} /></div><div className="time-chart-panel"><h3>Bugs Created Over Time</h3><TimeChart points={analytics.created_over_time} /></div></div></details></>;
}
