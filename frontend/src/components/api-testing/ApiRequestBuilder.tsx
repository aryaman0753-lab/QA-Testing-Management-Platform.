import { useEffect, useState } from "react";
import { createApiRequest, deleteApiRequest, executeApiRequest, updateApiRequest } from "../../api/apiTesting";
import { extractErrorMessage } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import type { ApiRequest, ApiRequestPayload, ApiRun, ApiTestResult, HttpMethod } from "../../types/apiTesting";
import { Button } from "../ui/Button";
import { AssertionEditor } from "./AssertionEditor";
import { AuthEditor } from "./AuthEditor";
import { BodyEditor } from "./BodyEditor";
import { ExtractorEditor } from "./ExtractorEditor";
import { KeyValueEditor } from "./KeyValueEditor";
import { ResponseViewer } from "./ResponseViewer";

const METHODS: HttpMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];
const EMPTY: ApiRequestPayload = {
  name: "Untitled request", method: "GET", url: "https://", description: "", headers: [],
  query_parameters: [], body: "", body_type: "NONE", authentication_type: "NONE",
  authentication_config: {}, assertions: [], extractors: [], position: 0,
};
type Tab = "params" | "auth" | "headers" | "body" | "tests";

export function ApiRequestBuilder({ request, draftCollectionId, environmentId, canManage, canExecute, onSaved, onDeleted }: {
  request: ApiRequest | null; draftCollectionId: string | null; environmentId: string;
  canManage: boolean; canExecute: boolean; onSaved: (request: ApiRequest, run?: ApiRun) => void;
  onDeleted: () => void;
}) {
  const [form, setForm] = useState<ApiRequestPayload>(request ?? EMPTY);
  const [tab, setTab] = useState<Tab>("params");
  const [result, setResult] = useState<ApiTestResult | null>(null);
  const [saving, setSaving] = useState(false); const [sending, setSending] = useState(false);
  const { showToast } = useToast();
  useEffect(() => { setForm(request ? { ...request } : { ...EMPTY, headers: [], query_parameters: [], assertions: [], extractors: [], authentication_config: {} }); setResult(null); }, [request, draftCollectionId]);
  const set = <K extends keyof ApiRequestPayload>(key: K, value: ApiRequestPayload[K]) => setForm((current) => ({ ...current, [key]: value }));

  function validate() {
    if (!form.name.trim()) throw new Error("Request name is required.");
    if (!/^https?:\/\//i.test(form.url)) throw new Error("URL must begin with http:// or https://.");
    if (["JSON", "FORM_URLENCODED", "MULTIPART_FORM_DATA"].includes(form.body_type) && form.body?.trim()) JSON.parse(form.body);
  }
  async function save(showSuccess = true) {
    validate(); setSaving(true);
    try {
      const response = request ? await updateApiRequest(request.id, form) : await createApiRequest(draftCollectionId ?? "", form);
      if (showSuccess) showToast("API request saved.", "success");
      onSaved(response.data); return response.data;
    } catch (error) { showToast(extractErrorMessage(error), "error"); throw error; }
    finally { setSaving(false); }
  }
  async function send() {
    setSending(true);
    try {
      const saved = request ?? (canManage ? await save(false) : null);
      if (!saved) throw new Error("Save the request before running it.");
      const response = await executeApiRequest(saved.id, environmentId);
      setResult(response.data.results?.[0] ?? null); onSaved(saved, response.data);
      showToast(`Run ${response.data.run_key} finished with ${response.data.status}.`, response.data.status === "PASS" ? "success" : "error");
    } catch (error) { showToast(extractErrorMessage(error), "error"); }
    finally { setSending(false); }
  }
  async function remove() {
    if (!request || !window.confirm(`Delete ${request.name}?`)) return;
    try { await deleteApiRequest(request.id); showToast("Request deleted.", "success"); onDeleted(); }
    catch (error) { showToast(extractErrorMessage(error), "error"); }
  }
  if (!request && !draftCollectionId) return <div className="response-empty"><h2>API request builder</h2><p className="muted">Select a request or add one to a collection.</p></div>;
  return <div className="request-builder">
    <div className="request-toolbar"><input aria-label="Request name" className="request-name" value={form.name} onChange={(e) => set("name", e.target.value)} /><div className="request-actions">{request && canManage && <Button variant="danger" onClick={remove}>Delete</Button>}{canManage && <Button variant="secondary" isLoading={saving} onClick={() => void save()}>Save</Button>}{canExecute && <Button isLoading={sending} onClick={send}>Send</Button>}</div></div>
    <div className="request-line"><select aria-label="HTTP method" className={`method-select method-${form.method.toLowerCase()}`} value={form.method} onChange={(e) => set("method", e.target.value as HttpMethod)}>{METHODS.map((method) => <option key={method}>{method}</option>)}</select><input aria-label="Request URL" value={form.url} onChange={(e) => set("url", e.target.value)} placeholder="https://api.example.com/users/{{user_id}}" /></div>
    {!canManage && <p className="muted permission-note">Your role has read-only access to saved definitions.</p>}
    <div className="api-tabs">{(["params", "auth", "headers", "body", "tests"] as Tab[]).map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item === "auth" ? "Authorization" : item}</button>)}</div>
    <div className="request-editor-panel">
      {tab === "params" && <KeyValueEditor items={form.query_parameters} onChange={(items) => set("query_parameters", items)} />}
      {tab === "auth" && <AuthEditor type={form.authentication_type} config={form.authentication_config} onType={(value) => set("authentication_type", value)} onConfig={(value) => set("authentication_config", value)} />}
      {tab === "headers" && <><p className="muted">Sensitive header values are encrypted at rest and returned masked.</p><KeyValueEditor items={form.headers} onChange={(items) => set("headers", items)} /></>}
      {tab === "body" && <BodyEditor type={form.body_type} body={form.body ?? ""} onType={(value) => set("body_type", value)} onBody={(value) => set("body", value)} />}
      {tab === "tests" && <><AssertionEditor assertions={form.assertions} onChange={(items) => set("assertions", items)} /><ExtractorEditor extractors={form.extractors} onChange={(items) => set("extractors", items)} /></>}
    </div>
    <ResponseViewer result={result} />
  </div>;
}
