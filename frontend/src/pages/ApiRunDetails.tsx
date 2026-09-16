import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getApiRun } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { ExecutionBadge, ResponseViewer } from "../components/api-testing/ResponseViewer";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import type { ApiRun } from "../types/apiTesting";

export function ApiRunDetails() {
  const { projectId = "", runId = "" } = useParams(); const [run, setRun] = useState<ApiRun | null>(null); const [selected, setSelected] = useState(0); const [error, setError] = useState<string | null>(null);
  useEffect(() => { getApiRun(runId).then((response) => { setRun(response.data); setError(null); }).catch((reason) => setError(extractErrorMessage(reason))); }, [runId]);
  if (error) return <AppLayout><EmptyState title="Unable to load run" description={error} /></AppLayout>;
  if (!run) return <AppLayout><LoadingSpinner /></AppLayout>;
  const result = run.results?.[selected] ?? null;
  return <AppLayout><div className="bug-breadcrumb"><Link to={`/projects/${projectId}/api-testing`}>API Testing</Link> / <Link to={`/projects/${projectId}/api-testing/runs`}>Runs</Link> / {run.run_key}</div><div className="page-header"><div><h1>{run.run_key}</h1><p className="muted">{run.collection_name ?? run.request_name} · {new Date(run.created_at).toLocaleString()}</p></div><ExecutionBadge status={run.status} /></div><div className="api-stats"><div><span>Requests</span><strong>{run.requests_total}</strong></div><div><span>Passed</span><strong>{run.requests_passed}</strong></div><div><span>Failed</span><strong>{run.requests_failed}</strong></div><div><span>Duration</span><strong>{run.duration_ms.toFixed(0)} ms</strong></div></div><section className="panel run-detail-layout"><aside className="run-results-list">{run.results?.map((item, index) => <button className={selected === index ? "active" : ""} onClick={() => setSelected(index)} key={item.id}><span className={`method-text method-${item.method.toLowerCase()}`}>{item.method}</span><span>{item.request_name}</span><ExecutionBadge status={item.status} /></button>)}</aside><main>{result && <><div className="result-title"><div><h2>{result.request_name}</h2><code>{result.resolved_url}</code></div>{result.status !== "PASS" && <Link to={`/projects/${projectId}/bugs/new?source_result=${result.id}`}><Button>Create Bug</Button></Link>}</div><ResponseViewer result={result} /></>}</main></section></AppLayout>;
}
