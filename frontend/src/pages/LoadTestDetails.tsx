import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getApiCollection, listApiCollections, listApiEnvironments } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { getLoadTest, startLoadTest, updateLoadTest } from "../api/loadTesting";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadTestForm } from "../components/load-testing/LoadTestForm";
import { RunConfirmationModal } from "../components/load-testing/RunConfirmationModal";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useToast } from "../context/ToastContext";
import type { ApiEnvironment, ApiRequest } from "../types/apiTesting";
import type { LoadTest, LoadTestPayload } from "../types/loadTesting";

export function LoadTestDetails() {
  const { projectId = "", testId = "" } = useParams(); const navigate = useNavigate(); const { showToast } = useToast(); const [test, setTest] = useState<LoadTest | null>(null); const [environments, setEnvironments] = useState<ApiEnvironment[]>([]); const [requests, setRequests] = useState<ApiRequest[]>([]); const [editing, setEditing] = useState(false); const [confirming, setConfirming] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => { Promise.all([getLoadTest(testId), listApiEnvironments(projectId), listApiCollections(projectId)]).then(async ([testResponse, envResponse, collectionResponse]) => { const details = await Promise.all(collectionResponse.data.map((item) => getApiCollection(item.id).then(({ data }) => data))); setTest(testResponse.data); setEnvironments(envResponse.data); setRequests(details.flatMap((item) => item.requests ?? [])); }).catch((error) => showToast(extractErrorMessage(error), "error")); }, [projectId, showToast, testId]);
  if (!test) return <AppLayout><LoadingSpinner /></AppLayout>;
  const currentTest = test;
  async function save(payload: LoadTestPayload) { setBusy(true); try { const { data } = await updateLoadTest(currentTest.id, payload); setTest(data); setEditing(false); showToast("Load test updated.", "success"); } catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setBusy(false); } }
  async function start(production: boolean) { setBusy(true); try { const { data } = await startLoadTest(currentTest.id, production); navigate(`/projects/${projectId}/load-testing/runs/${data.id}`); } catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setBusy(false); setConfirming(false); } }
  return <AppLayout><div className="bug-breadcrumb"><button className="inline-link" onClick={() => navigate(`/projects/${projectId}/load-testing`)}>Load testing</button> / {test.name}</div><div className="page-header"><div><h1>{test.name}</h1><p className="muted">{test.description || "No description"}</p></div><div className="page-actions"><Button variant="secondary" onClick={() => setEditing((value) => !value)}>{editing ? "Close editor" : "Edit"}</Button><Button onClick={() => setConfirming(true)}>Run test</Button></div></div>
    {editing ? <section className="panel load-form-panel"><LoadTestForm initial={test} environments={environments} requests={requests} busy={busy} onSubmit={save} onCancel={() => setEditing(false)} /></section> : <><section className="panel"><h2>Scenario</h2><dl className="load-definition-grid"><div><dt>Target</dt><dd><code>{test.request_method} {test.target_url}</code></dd></div><div><dt>Environment</dt><dd>{test.environment_name} ({test.environment_classification})</dd></div><div><dt>Profile</dt><dd>{test.profile}</dd></div><div><dt>Source</dt><dd>{test.api_request_id ? "Saved API request" : "Standalone request"}</dd></div><div><dt>Virtual users</dt><dd>{test.virtual_users}</dd></div><div><dt>Spawn rate</dt><dd>{test.spawn_rate}/s</dd></div><div><dt>Duration</dt><dd>{test.duration_seconds}s</dd></div><div><dt>Target RPS</dt><dd>{test.target_rps ?? "Uncapped"}</dd></div></dl></section><section className="panel"><h2>Thresholds</h2><div className="threshold-summary">{Object.entries(test.thresholds).map(([name, threshold]) => threshold === null ? null : <span key={name}><strong>{name.replaceAll("_", " ")}</strong> {threshold}</span>)}</div></section></>}
    {confirming && <RunConfirmationModal test={test} busy={busy} onCancel={() => setConfirming(false)} onConfirm={start} />}
  </AppLayout>;
}
