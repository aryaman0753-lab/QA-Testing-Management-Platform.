import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getProjectDashboard } from "../api/operations";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";

export function ProjectQADashboard() {
  const { projectId = "" } = useParams();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { getProjectDashboard(projectId).then((response) => setData(response.data)).catch(() => setError("Could not load project analytics.")); }, [projectId]);

  return <AppLayout>
    <div className="page-header"><div><h1>Project QA Dashboard</h1><p className="muted">Bugs, testing, performance, and CI in one operational view.</p></div><Link className="btn btn-primary link-button" to={`/projects/${projectId}/reports`}>Reports</Link></div>
    {error && <div className="alert alert-error">{error}</div>}
    {!data ? !error && <LoadingSpinner /> : <>
      <div className="card-grid">
        <Link className="stat-card" to={`/projects/${projectId}/bugs`}><span className="stat-value">{data.bugs.open}</span><span className="stat-label">Open bugs</span></Link>
        <Link className="stat-card" to={`/projects/${projectId}/api-testing/runs`}><span className="stat-value">{data.api_tests.pass_rate}%</span><span className="stat-label">API pass rate</span></Link>
        <Link className="stat-card" to={`/projects/${projectId}/automation/runs`}><span className="stat-value">{data.automation.failed_suites}</span><span className="stat-label">Recent failed suites</span></Link>
        <Link className="stat-card" to={`/projects/${projectId}/load-testing/runs`}><span className="stat-value">{data.load_testing.threshold_violations}</span><span className="stat-label">Threshold violations</span></Link>
        <Link className="stat-card" to={`/projects/${projectId}/integrations`}><span className="stat-value">{data.ci_cd.failed_pipelines}</span><span className="stat-label">Failed CI runs</span></Link>
      </div>
      <section className="panel"><h2>Recent CI executions</h2>{data.ci_cd.recent_executions.length === 0 ? <p className="muted">No CI executions yet.</p> : <table className="table"><thead><tr><th>Provider</th><th>Commit / branch</th><th>Build</th><th>Status</th></tr></thead><tbody>{data.ci_cd.recent_executions.map((row: any) => <tr key={row.run_id}><td>{row.provider}</td><td><code>{row.commit_sha?.slice(0, 10) || "-"}</code> {row.branch}</td><td>{row.build_number || "-"}</td><td>{row.status}</td></tr>)}</tbody></table>}</section>
      <section className="panel"><h2>Recent automation</h2>{data.automation.recent_runs.length === 0 ? <p className="muted">No automation runs yet.</p> : <table className="table"><thead><tr><th>Run</th><th>Suite</th><th>Status</th><th>Created</th></tr></thead><tbody>{data.automation.recent_runs.map((row: any) => <tr key={row.id}><td><Link to={`/projects/${projectId}/automation/runs/${row.id}`}>{row.id.slice(0, 8)}</Link></td><td>{row.suite_id.slice(0, 8)}</td><td>{row.status}</td><td>{new Date(row.created_at).toLocaleString()}</td></tr>)}</tbody></table>}</section>
      <section className="panel"><h2>Recent load tests</h2>{data.load_testing.recent_runs.length === 0 ? <p className="muted">No load-test runs yet.</p> : <table className="table"><thead><tr><th>Run</th><th>Status</th><th>RPS</th><th>P95</th></tr></thead><tbody>{data.load_testing.recent_runs.map((row: any) => <tr key={row.id}><td><Link to={`/projects/${projectId}/load-testing/runs/${row.id}`}>{row.id.slice(0, 8)}</Link></td><td>{row.result_status || row.status}</td><td>{Number(row.rps).toFixed(2)}</td><td>{Number(row.p95_ms).toFixed(2)} ms</td></tr>)}</tbody></table>}</section>
    </>}
  </AppLayout>;
}
