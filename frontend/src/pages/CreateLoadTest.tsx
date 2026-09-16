import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getApiCollection, listApiCollections, listApiEnvironments } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { createLoadTest } from "../api/loadTesting";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadTestForm, newLoadTest } from "../components/load-testing/LoadTestForm";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";
import type { ApiEnvironment, ApiRequest } from "../types/apiTesting";
import type { LoadTestPayload } from "../types/loadTesting";

export function CreateLoadTest() {
  const { projectId = "" } = useParams(); const [search] = useSearchParams(); const navigate = useNavigate(); const { showToast } = useToast(); const [environments, setEnvironments] = useState<ApiEnvironment[] | null>(null); const [requests, setRequests] = useState<ApiRequest[]>([]); const [busy, setBusy] = useState(false);
  useEffect(() => { Promise.all([listApiEnvironments(projectId), listApiCollections(projectId)]).then(async ([envResponse, collectionResponse]) => { const details = await Promise.all(collectionResponse.data.map((item) => getApiCollection(item.id).then(({ data }) => data))); setEnvironments(envResponse.data); setRequests(details.flatMap((item) => item.requests ?? [])); }).catch((error) => showToast(extractErrorMessage(error), "error")); }, [projectId, showToast]);
  if (!environments) return <AppLayout><LoadingSpinner /></AppLayout>;
  const requestedSource = requests.find((item) => item.id === search.get("request_id")); let initial = newLoadTest(environments[0]?.id); if (requestedSource) initial = { ...initial, name: `${requestedSource.name} load test`, api_request_id: requestedSource.id, target_url: requestedSource.url, request_method: requestedSource.method, headers: requestedSource.headers, query_parameters: requestedSource.query_parameters, body: requestedSource.body, body_type: requestedSource.body_type, authentication_type: requestedSource.authentication_type, authentication_config: requestedSource.authentication_config };
  async function save(payload: LoadTestPayload) { setBusy(true); try { const { data } = await createLoadTest(projectId, payload); showToast("Load test created.", "success"); navigate(`/projects/${projectId}/load-testing/${data.id}`); } catch (error) { showToast(extractErrorMessage(error), "error"); setBusy(false); } }
  return <AppLayout><div className="page-header"><div><h1>Create load test</h1><p className="muted">Configure workload, request details, and measurable pass/fail thresholds.</p></div></div><section className="panel load-form-panel">{environments.length ? <LoadTestForm key={requestedSource?.id ?? "new"} initial={initial} environments={environments} requests={requests} busy={busy} onSubmit={save} onCancel={() => navigate(`/projects/${projectId}/load-testing`)} /> : <div className="alert alert-error">Create an API environment before defining a load test.</div>}</section></AppLayout>;
}
