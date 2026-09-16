import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { archiveLoadTest, listLoadRuns, listLoadTests, startLoadTest } from "../api/loadTesting";
import { extractErrorMessage } from "../api/client";
import { AppLayout } from "../components/layout/AppLayout";
import { AllowlistManager } from "../components/load-testing/AllowlistManager";
import { LoadResultBadge, LoadStatusBadge } from "../components/load-testing/LoadStatusBadges";
import { RunConfirmationModal } from "../components/load-testing/RunConfirmationModal";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";
import type { LoadRun, LoadTest } from "../types/loadTesting";

export function LoadTesting() {
  const { projectId = "" } = useParams(); const navigate = useNavigate(); const { showToast } = useToast();
  const [tests, setTests] = useState<LoadTest[] | null>(null); const [runs, setRuns] = useState<LoadRun[]>([]); const [selected, setSelected] = useState<LoadTest | null>(null); const [settings, setSettings] = useState(false); const [busy, setBusy] = useState(false);
  const load = useCallback(() => Promise.all([listLoadTests(projectId), listLoadRuns(projectId)]).then(([testResponse, runResponse]) => { setTests(testResponse.data); setRuns(runResponse.data.items); }).catch((error) => showToast(extractErrorMessage(error), "error")), [projectId, showToast]);
  useEffect(() => { void load(); }, [load]);
  async function start(productionConfirmed: boolean) { if (!selected) return; setBusy(true); try { const { data } = await startLoadTest(selected.id, productionConfirmed); showToast("Load test queued for the dedicated worker.", "success"); navigate(`/projects/${projectId}/load-testing/runs/${data.id}`); } catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setBusy(false); setSelected(null); } }
  async function archive(item: LoadTest) { if (!window.confirm(`Archive ${item.name}? Its run history will be retained.`)) return; try { await archiveLoadTest(item.id); showToast("Load test archived.", "success"); void load(); } catch (error) { showToast(extractErrorMessage(error), "error"); } }
  return <AppLayout><div className="page-header api-page-header"><div><h1>Load Testing</h1><p className="muted">Controlled performance tests executed outside the API process.</p></div><div className="page-actions"><Button variant="secondary" onClick={() => setSettings(true)}>Target allowlist</Button><Link className="btn btn-secondary link-button" to={`/projects/${projectId}/load-testing/compare`}>Compare runs</Link><Link className="btn btn-primary link-button" to={`/projects/${projectId}/load-testing/create`}>+ New load test</Link></div></div>
    <section className="panel"><div className="panel-header"><h2>Definitions</h2></div>{tests === null ? <LoadingSpinner /> : tests.length === 0 ? <EmptyState title="No load tests yet" description="Create a safe, repeatable performance scenario from an API request or a standalone target." /> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Name</th><th>Target</th><th>Environment</th><th>Profile</th><th>Load</th><th /></tr></thead><tbody>{tests.map((item) => <tr key={item.id}><td><Link to={`/projects/${projectId}/load-testing/${item.id}`}>{item.name}</Link></td><td><code>{item.request_method} {item.target_url}</code></td><td>{item.environment_name} <span className={`environment-class environment-${item.environment_classification.toLowerCase()}`}>{item.environment_classification}</span></td><td>{item.profile}</td><td>{item.virtual_users} users · {item.duration_seconds}s</td><td><div className="button-row"><Button onClick={() => setSelected(item)}>Run</Button><Button variant="ghost" onClick={() => archive(item)}>Archive</Button></div></td></tr>)}</tbody></table></div>}</section>
    <section className="panel"><div className="panel-header"><h2>Recent runs</h2><Link to={`/projects/${projectId}/load-testing/runs`}>View all</Link></div>{runs.length === 0 ? <p className="muted">No runs recorded.</p> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Run</th><th>Test</th><th>Status</th><th>Result</th><th>Requests</th><th>p95</th><th>Started</th></tr></thead><tbody>{runs.slice(0, 8).map((run) => <tr key={run.id}><td><Link to={`/projects/${projectId}/load-testing/runs/${run.id}`}>{run.run_key}</Link></td><td>{run.load_test_name}</td><td><LoadStatusBadge status={run.status} /></td><td><LoadResultBadge status={run.result_status} /></td><td>{run.total_requests}</td><td>{run.p95_response_time.toFixed(1)} ms</td><td>{new Date(run.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}</section>
    {selected && <RunConfirmationModal test={selected} busy={busy} onCancel={() => setSelected(null)} onConfirm={start} />}{settings && <AllowlistManager projectId={projectId} onClose={() => setSettings(false)} />}
  </AppLayout>;
}
