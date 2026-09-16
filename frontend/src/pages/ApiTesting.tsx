import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createApiCollection, executeApiCollection, getApiAnalytics, getApiCollection, getApiRequest, listApiCollections, listApiEnvironments } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { getProject } from "../api/projects";
import { ApiRequestBuilder } from "../components/api-testing/ApiRequestBuilder";
import { CollectionTree } from "../components/api-testing/CollectionTree";
import { EnvironmentManager } from "../components/api-testing/EnvironmentManager";
import { EnvironmentSelector } from "../components/api-testing/EnvironmentSelector";
import { HealthCheckModal } from "../components/api-testing/HealthCheckModal";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Project } from "../types";
import type { ApiAnalytics, ApiCollection, ApiEnvironment, ApiRequest, ApiRun } from "../types/apiTesting";

export function ApiTesting() {
  const { projectId = "", collectionId, requestId } = useParams(); const navigate = useNavigate();
  const { user } = useAuth(); const { showToast } = useToast();
  const [project, setProject] = useState<Project | null>(null); const [collections, setCollections] = useState<ApiCollection[] | null>(null);
  const [environments, setEnvironments] = useState<ApiEnvironment[]>([]); const [environmentId, setEnvironmentId] = useState("");
  const [analytics, setAnalytics] = useState<ApiAnalytics | null>(null); const [selected, setSelected] = useState<ApiRequest | null>(null);
  const [draftCollection, setDraftCollection] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  const [newCollection, setNewCollection] = useState(false); const [collectionName, setCollectionName] = useState("");
  const [environmentManager, setEnvironmentManager] = useState(false); const [healthCheck, setHealthCheck] = useState(false);
  const [runningCollection, setRunningCollection] = useState<string | null>(null);
  const canManage = user?.role === "ADMIN" || user?.role === "QA_ENGINEER";
  const canExecute = canManage || user?.role === "DEVELOPER";

  const load = useCallback(async () => {
    try {
      const [projectResponse, collectionResponse, environmentResponse, analyticsResponse] = await Promise.all([getProject(projectId), listApiCollections(projectId), listApiEnvironments(projectId), getApiAnalytics(projectId)]);
      const details = await Promise.all(collectionResponse.data.map((item) => getApiCollection(item.id).then((response) => response.data)));
      setProject(projectResponse.data); setCollections(details); setEnvironments(environmentResponse.data); setAnalytics(analyticsResponse.data); setError(null);
    } catch (reason) { setError(extractErrorMessage(reason)); }
  }, [projectId]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!requestId) { setSelected(null); return; }
    getApiRequest(requestId).then((response) => { setSelected(response.data); setDraftCollection(null); }).catch((reason) => setError(extractErrorMessage(reason)));
  }, [requestId]);
  useEffect(() => {
    if (requestId || !collectionId || !collections) return;
    const first = collections.find((item) => item.id === collectionId)?.requests?.[0];
    if (first) navigate(`/projects/${projectId}/api-testing/requests/${first.id}`, { replace: true });
  }, [collectionId, collections, navigate, projectId, requestId]);

  async function addCollection() {
    if (!collectionName.trim()) return;
    try { const response = await createApiCollection(projectId, { name: collectionName.trim() }); setNewCollection(false); setCollectionName(""); await load(); navigate(`/projects/${projectId}/api-testing/collections/${response.data.id}`); showToast("Collection created.", "success"); }
    catch (reason) { showToast(extractErrorMessage(reason), "error"); }
  }
  function addRequest(id: string) { setSelected(null); setDraftCollection(id); navigate(`/projects/${projectId}/api-testing/collections/${id}`); }
  async function runCollection(id: string) {
    setRunningCollection(id);
    try { const response = await executeApiCollection(id, environmentId); await load(); showToast(`Run ${response.data.run_key} finished with ${response.data.status}.`, response.data.status === "PASS" ? "success" : "error"); navigate(`/projects/${projectId}/api-testing/runs/${response.data.id}`); }
    catch (reason) { showToast(extractErrorMessage(reason), "error"); } finally { setRunningCollection(null); }
  }
  function saved(request: ApiRequest, run?: ApiRun) { setSelected(request); setDraftCollection(null); void load(); if (!requestId) navigate(`/projects/${projectId}/api-testing/requests/${request.id}`); if (run) setAnalytics((current) => current ? { ...current, total_runs: current.total_runs + 1 } : current); }
  if (error) return <AppLayout><EmptyState title="Unable to load API testing" description={error} action={<Button onClick={load}>Try again</Button>} /></AppLayout>;
  if (!project || !collections) return <AppLayout><LoadingSpinner /></AppLayout>;
  return <AppLayout><div className="page-header api-page-header"><div><div className="bug-breadcrumb"><Link to={`/projects/${projectId}`}>{project.key}</Link> / API Testing</div><h1>API Testing</h1><p className="muted">Build requests, validate responses, and keep every run traceable.</p></div><div className="page-actions"><Button variant="secondary" onClick={() => setHealthCheck(true)}>Health Check</Button><Link className="btn btn-secondary link-button" to={`/projects/${projectId}/api-testing/runs`}>Run History</Link><EnvironmentSelector environments={environments} value={environmentId} onChange={setEnvironmentId} onManage={() => setEnvironmentManager(true)} /></div></div>
    <div className="api-stats"><div><span>Saved requests</span><strong>{analytics?.total_api_requests ?? 0}</strong></div><div><span>Total runs</span><strong>{analytics?.total_runs ?? 0}</strong></div><div><span>Pass rate</span><strong>{(analytics?.pass_rate ?? 0).toFixed(1)}%</strong></div><div><span>Failure rate</span><strong>{(analytics?.failure_rate ?? 0).toFixed(1)}%</strong></div><div><span>Average response</span><strong>{(analytics?.average_response_time_ms ?? 0).toFixed(0)} ms</strong></div><div><span>Slowest endpoint</span><strong className="endpoint-stat">{analytics?.slowest_endpoint ?? "—"}</strong></div></div>
    <section className="panel api-workspace"><CollectionTree collections={collections} selectedRequestId={selected?.id} onRequest={(_, id) => navigate(`/projects/${projectId}/api-testing/requests/${id}`)} onNewCollection={() => canManage && setNewCollection(true)} onNewRequest={(id) => canManage && addRequest(id)} onRun={(id) => canExecute && void runCollection(id)} running={runningCollection ? { id: runningCollection, status: "RUNNING" } : null} /><main className="api-builder-pane"><ApiRequestBuilder request={selected} draftCollectionId={draftCollection} environmentId={environmentId} canManage={Boolean(canManage)} canExecute={Boolean(canExecute)} onSaved={saved} onDeleted={() => { setSelected(null); void load(); navigate(`/projects/${projectId}/api-testing`); }} /></main></section>
    {newCollection && <Modal title="New collection" onClose={() => setNewCollection(false)}><label className="field"><span>Name</span><input autoFocus value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="Authentication API" /></label><div className="modal-actions"><Button variant="secondary" onClick={() => setNewCollection(false)}>Cancel</Button><Button onClick={addCollection}>Create</Button></div></Modal>}
    {environmentManager && <EnvironmentManager projectId={projectId} environments={environments} onClose={() => setEnvironmentManager(false)} onChanged={() => { void load(); setEnvironmentManager(false); }} />}
    {healthCheck && <HealthCheckModal projectId={projectId} onClose={() => setHealthCheck(false)} />}
  </AppLayout>;
}
