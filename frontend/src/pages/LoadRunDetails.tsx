import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { downloadLoadReport, getLoadRun, markLoadBaseline, stopLoadRun } from "../api/loadTesting";
import { extractErrorMessage } from "../api/client";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadResultBadge, LoadStatusBadge } from "../components/load-testing/LoadStatusBadges";
import { MetricCards } from "../components/load-testing/MetricCards";
import { TimeSeriesChart } from "../components/load-testing/TimeSeriesChart";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";
import type { LoadRunDetail } from "../types/loadTesting";

const active = new Set(["QUEUED", "STARTING", "RUNNING", "STOPPING"]);

export function LoadRunDetails() {
  const { projectId = "", runId = "" } = useParams(); const { showToast } = useToast(); const [run, setRun] = useState<LoadRunDetail | null>(null); const [tab, setTab] = useState<"overview" | "endpoints" | "errors" | "thresholds">("overview"); const [busy, setBusy] = useState(false);
  const load = useCallback(() => getLoadRun(runId).then(({ data }) => setRun(data)).catch((error) => showToast(extractErrorMessage(error), "error")), [runId, showToast]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!run || !active.has(run.status)) return; const timer = window.setInterval(() => void load(), 2000); return () => window.clearInterval(timer); }, [load, run]);
  if (!run) return <AppLayout><LoadingSpinner /></AppLayout>;
  const currentRun = run;
  async function stop() { if (!window.confirm("Stop this load test? The worker will finish in-flight requests and preserve collected metrics.")) return; setBusy(true); try { await stopLoadRun(currentRun.id); showToast("Stop requested.", "success"); await load(); } catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setBusy(false); } }
  async function baseline() { try { const { data } = await markLoadBaseline(currentRun.id); setRun((current) => current ? { ...current, is_baseline: data.is_baseline } : current); showToast("Baseline selected.", "success"); } catch (error) { showToast(extractErrorMessage(error), "error"); } }
  async function report(format: "json" | "csv") { try { const { data } = await downloadLoadReport(currentRun.id, format); const href = URL.createObjectURL(data); const anchor = document.createElement("a"); anchor.href = href; anchor.download = `${currentRun.run_key}.${format}`; anchor.click(); URL.revokeObjectURL(href); } catch (error) { showToast(extractErrorMessage(error), "error"); } }
  return <AppLayout><div className="bug-breadcrumb"><Link to={`/projects/${projectId}/load-testing/runs`}>Load-test runs</Link> / {run.run_key}</div><div className="page-header"><div><h1>{run.run_key}: {run.load_test_name}</h1><div className="result-heading"><LoadStatusBadge status={run.status} /><LoadResultBadge status={run.result_status} />{run.is_baseline && <span className="load-badge baseline-badge">BASELINE</span>}</div></div><div className="page-actions">{active.has(run.status) && <Button variant="danger" isLoading={busy} onClick={stop}>Stop run</Button>}<Button variant="secondary" disabled={run.is_baseline || run.status !== "COMPLETED"} onClick={baseline}>{run.is_baseline ? "Current baseline" : "Set baseline"}</Button><Button variant="secondary" onClick={() => report("csv")}>CSV</Button><Button variant="secondary" onClick={() => report("json")}>JSON</Button><Link className="btn btn-primary link-button" to={`/projects/${projectId}/bugs/new?source_load_run=${run.id}`}>Create bug</Link></div></div>
    {run.error_message && <div className="alert alert-error">{run.error_message}</div>}{active.has(run.status) && <div className="live-indicator"><i /> Live metrics refresh every 2 seconds</div>}<MetricCards run={run} />
    <section className="panel load-results"><div className="api-tabs">{(["overview", "endpoints", "errors", "thresholds"] as const).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div>
      {tab === "overview" && <div className="load-tab"><div className="load-chart-grid"><div><h2>p95 response time</h2><TimeSeriesChart metrics={run.metrics} /></div><div><h2>Requests / second</h2><TimeSeriesChart metrics={run.metrics} metric="requests_per_second" /></div><div><h2>Active users</h2><TimeSeriesChart metrics={run.metrics} metric="active_users" /></div><div><h2>Failure rate</h2><TimeSeriesChart metrics={run.metrics} metric="failure_rate" /></div></div><h3>Response percentiles</h3><div className="percentile-grid">{[["p50", run.p50_response_time], ["p75", run.p75_response_time], ["p90", run.p90_response_time], ["p95", run.p95_response_time], ["p99", run.p99_response_time]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{Number(value).toFixed(1)} ms</strong></div>)}</div><h3>Status distribution</h3><div className="threshold-summary">{Object.entries(run.status_distribution).map(([status, count]) => <span key={status}><strong>{status}</strong> {count}</span>)}</div></div>}
      {tab === "endpoints" && <div className="load-tab table-wrap"><table className="data-table"><thead><tr><th>Endpoint</th><th>Requests</th><th>Failures</th><th>RPS</th><th>Average</th><th>p95</th><th>p99</th></tr></thead><tbody>{run.endpoints.map((item) => <tr key={item.id}><td><code>{item.method} {item.path}</code></td><td>{item.request_count}</td><td>{item.failure_count}</td><td>{item.rps.toFixed(2)}</td><td>{item.avg_response_time.toFixed(1)} ms</td><td>{item.p95.toFixed(1)} ms</td><td>{item.p99.toFixed(1)} ms</td></tr>)}</tbody></table>{!run.endpoints.length && <p className="muted">No endpoint metrics yet.</p>}</div>}
      {tab === "errors" && <div className="load-tab table-wrap"><table className="data-table"><thead><tr><th>Type</th><th>Endpoint</th><th>Status</th><th>Message</th><th>Count</th></tr></thead><tbody>{run.errors.map((item) => <tr key={item.id}><td>{item.error_type}</td><td><code>{item.method} {item.path}</code></td><td>{item.status_code ?? "—"}</td><td>{item.message}</td><td>{item.count}</td></tr>)}</tbody></table>{!run.errors.length && <p className="muted">No errors recorded.</p>}</div>}
      {tab === "thresholds" && <div className="load-tab threshold-results">{run.threshold_results.length ? run.threshold_results.map((item) => <div className={item.passed ? "threshold-pass" : "threshold-fail"} key={item.key}><strong>{item.passed ? "PASS" : "FAIL"}</strong><span>{item.label}</span><code>{item.measured.toFixed(2)} {item.unit} {item.operator} {item.threshold} {item.unit}</code></div>) : <p className="muted">No thresholds configured.</p>}</div>}
    </section>
  </AppLayout>;
}
