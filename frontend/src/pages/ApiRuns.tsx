import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listApiRuns } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { ExecutionBadge } from "../components/api-testing/ResponseViewer";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import type { PaginatedRuns } from "../types/apiTesting";

export function ApiRuns() {
  const { projectId = "" } = useParams(); const [page, setPage] = useState(1); const [data, setData] = useState<PaginatedRuns | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => { listApiRuns(projectId, page).then((response) => { setData(response.data); setError(null); }).catch((reason) => setError(extractErrorMessage(reason))); }, [page, projectId]);
  if (error) return <AppLayout><EmptyState title="Unable to load runs" description={error} /></AppLayout>;
  if (!data) return <AppLayout><LoadingSpinner /></AppLayout>;
  return <AppLayout><div className="bug-breadcrumb"><Link to={`/projects/${projectId}/api-testing`}>API Testing</Link> / Runs</div><div className="page-header"><div><h1>API Run History</h1><p className="muted">Persisted execution results and assertion outcomes.</p></div></div><section className="panel table-wrap">{data.items.length ? <table className="data-table"><thead><tr><th>Run</th><th>Target</th><th>Status</th><th>Passed</th><th>Duration</th><th>Created</th></tr></thead><tbody>{data.items.map((run) => <tr key={run.id}><td><Link to={`/projects/${projectId}/api-testing/runs/${run.id}`}>{run.run_key}</Link></td><td>{run.collection_name ?? run.request_name ?? "Request"}</td><td><ExecutionBadge status={run.status} /></td><td>{run.requests_passed}/{run.requests_total}</td><td>{run.duration_ms.toFixed(0)} ms</td><td>{new Date(run.created_at).toLocaleString()}</td></tr>)}</tbody></table> : <EmptyState title="No API runs yet" description="Send a request or run a collection to create the first result." />}</section><div className="pagination"><Button variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><span>Page {data.page} of {Math.max(data.total_pages, 1)}</span><Button variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage((value) => value + 1)}>Next</Button></div></AppLayout>;
}
