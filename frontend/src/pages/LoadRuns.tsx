import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listLoadRuns } from "../api/loadTesting";
import { extractErrorMessage } from "../api/client";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadResultBadge, LoadStatusBadge } from "../components/load-testing/LoadStatusBadges";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";
import type { PaginatedLoadRuns } from "../types/loadTesting";

export function LoadRuns() {
  const { projectId = "" } = useParams(); const { showToast } = useToast(); const [page, setPage] = useState(1); const [data, setData] = useState<PaginatedLoadRuns | null>(null);
  const load = useCallback(() => listLoadRuns(projectId, page).then((response) => setData(response.data)).catch((error) => showToast(extractErrorMessage(error), "error")), [page, projectId, showToast]); useEffect(() => { void load(); }, [load]);
  return <AppLayout><div className="page-header"><div><h1>Load-test runs</h1><p className="muted">Immutable execution history and performance results.</p></div><Link className="btn btn-secondary link-button" to={`/projects/${projectId}/load-testing/compare`}>Compare</Link></div><section className="panel">{!data ? <LoadingSpinner /> : <><div className="table-wrap"><table className="data-table"><thead><tr><th>Run</th><th>Definition</th><th>Status</th><th>Result</th><th>Users</th><th>Requests</th><th>Failure</th><th>p95</th><th>Created</th></tr></thead><tbody>{data.items.map((run) => <tr key={run.id}><td><Link to={`/projects/${projectId}/load-testing/runs/${run.id}`}>{run.run_key}{run.is_baseline ? " ★" : ""}</Link></td><td>{run.load_test_name}</td><td><LoadStatusBadge status={run.status} /></td><td><LoadResultBadge status={run.result_status} /></td><td>{run.virtual_users}</td><td>{run.total_requests}</td><td>{run.failure_rate.toFixed(2)}%</td><td>{run.p95_response_time.toFixed(1)} ms</td><td>{new Date(run.created_at).toLocaleString()}</td></tr>)}</tbody></table></div><div className="pagination"><Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {data.page} of {Math.max(data.total_pages, 1)}</span><Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>Next</Button></div></>}</section></AppLayout>;
}
