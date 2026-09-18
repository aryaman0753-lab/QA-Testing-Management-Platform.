import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { exportQAReport, getQAReport } from "../api/operations";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";

export function Reports() {
  const { projectId = "" } = useParams(); const { showToast } = useToast();
  const [report, setReport] = useState<any>(null);
  useEffect(() => { getQAReport(projectId).then(r => setReport(r.data)).catch(() => showToast("Could not load report.", "error")); }, [projectId, showToast]);
  async function download(format: "json" | "csv" | "pdf") { try { const r = await exportQAReport(projectId, format); const url = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = url; a.download = `qahub-report.${format}`; a.click(); URL.revokeObjectURL(url); } catch { showToast("Report export failed.", "error"); } }
  return <AppLayout><div className="page-header"><div><h1>QA Report</h1><p className="muted">A rolling 30-day project quality summary.</p></div><div className="button-row">{(["json", "csv", "pdf"] as const).map(f => <Button key={f} variant="secondary" onClick={() => download(f)}>Export {f.toUpperCase()}</Button>)}</div></div>
    {!report ? <LoadingSpinner /> : <><div className="card-grid"><div className="stat-card"><span className="stat-value">{report.test_execution.pass_rate}%</span><span className="stat-label">Automation pass rate</span></div><div className="stat-card"><span className="stat-value">{report.api_testing.failures}</span><span className="stat-label">API failures</span></div><div className="stat-card"><span className="stat-value">{report.load_testing.p95_ms} ms</span><span className="stat-label">Peak P95</span></div><div className="stat-card"><span className="stat-value">{report.bugs.open}</span><span className="stat-label">Open bugs</span></div></div><section className="panel"><h2>Flaky candidates</h2>{report.automation.flaky_tests.length ? <table className="table"><thead><tr><th>Test</th><th>Executions</th><th>Pass</th><th>Fail</th><th>Failure %</th></tr></thead><tbody>{report.automation.flaky_tests.map((row: any) => <tr key={row.step_id}><td>{row.case_name} / {row.step_name}</td><td>{row.executions}</td><td>{row.pass_count}</td><td>{row.fail_count}</td><td>{row.failure_percentage}%</td></tr>)}</tbody></table> : <p className="muted">No flaky candidates in recent history.</p>}</section></>}
  </AppLayout>;
}
