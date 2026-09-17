import { useState, type FormEvent } from "react";
import type { ApiRequest, ApiRequestPayload, HttpMethod } from "../../types/apiTesting";
import type { AutomationCondition, StepConfig, StepPayload, StepType } from "../../types/automation";
import { extractErrorMessage } from "../../api/client";
import { AuthEditor } from "../api-testing/AuthEditor";
import { BodyEditor } from "../api-testing/BodyEditor";
import { KeyValueEditor } from "../api-testing/KeyValueEditor";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { AutomationAssertionEditor, ConditionEditor, DEFAULT_CONDITION } from "./AssertionEditor";
import { AutomationError } from "./AutomationShared";

const EMPTY_REQUEST: ApiRequestPayload = {
  name: "Automation request", method: "GET", url: "https://", headers: [], query_parameters: [],
  body: "", body_type: "NONE", authentication_type: "NONE", authentication_config: {},
  assertions: [], extractors: [], position: 0,
};

export const STEP_LABELS: Record<StepType, string> = {
  HTTP_REQUEST: "HTTP request", ASSERTION: "Assert response", EXTRACT_VARIABLE: "Extract variable",
  SET_VARIABLE: "Assign variable", DELAY: "Delay", CONDITION: "Condition",
};

export function newStep(type: StepType = "HTTP_REQUEST", index = 0): StepPayload {
  const configs: Record<StepType, StepConfig> = {
    HTTP_REQUEST: { request: { ...EMPTY_REQUEST } },
    ASSERTION: { assertions: [{ source: "STATUS_CODE", operator: "EQUALS", expected: "200" }] },
    EXTRACT_VARIABLE: { source: "JSON_PATH", path: "$.data.id", variable_name: "user_id", is_secret: false },
    SET_VARIABLE: { variable_name: "base_url", value: "", is_secret: false },
    DELAY: { seconds: 1 },
    CONDITION: { ...DEFAULT_CONDITION },
  };
  return { name: STEP_LABELS[type], step_type: type, order_index: index, enabled: true, api_request_id: null, config: configs[type], condition: null };
}

export function StepEditor({ initial, requests, onSave, onClose }: {
  initial: StepPayload;
  requests: ApiRequest[];
  onSave: (payload: StepPayload) => Promise<void>;
  onClose: () => void;
}) {
  const [form, setForm] = useState<StepPayload>(structuredClone(initial));
  const [tab, setTab] = useState("headers");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const config = form.config;
  const request = config.request ?? EMPTY_REQUEST;
  const setConfig = (patch: Partial<StepConfig>) => setForm({ ...form, config: { ...config, ...patch } });
  const setRequest = (patch: Partial<ApiRequestPayload>) => setConfig({ request: { ...request, ...patch } });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!form.name.trim()) return setError("Enter a step name.");
    if (form.step_type === "ASSERTION" && !config.assertions?.length) return setError("Add at least one assertion.");
    if (form.step_type === "HTTP_REQUEST" && !form.api_request_id && !request.url.trim()) return setError("Enter a request URL.");
    setBusy(true);
    try { await onSave(form); } catch (reason) { setError(extractErrorMessage(reason)); } finally { setBusy(false); }
  }

  return <Modal wide title="Configure workflow step" onClose={() => !busy && onClose()}>
    <form onSubmit={submit} className="automation-step-editor">
      {error && <AutomationError message={error} />}
      <div className="form-grid">
        <label className="field">Step name<input required maxLength={255} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field">Step type<select value={form.step_type} onChange={(e) => setForm({ ...newStep(e.target.value as StepType, form.order_index), name: form.name, enabled: form.enabled, condition: form.condition })}>{Object.entries(STEP_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>

      {form.step_type === "HTTP_REQUEST" && <>
        <label className="field">Request source<select value={form.api_request_id ? "saved" : "standalone"} onChange={(e) => setForm({ ...form, api_request_id: e.target.value === "saved" ? requests[0]?.id ?? "" : null, config: e.target.value === "saved" ? {} : { request: { ...EMPTY_REQUEST } } })}><option value="standalone">Standalone request</option><option value="saved" disabled={!requests.length}>Saved API request{!requests.length ? " (create one in API Testing)" : ""}</option></select></label>
        {form.api_request_id ? <>
          <label className="field">Saved request<select value={form.api_request_id} onChange={(e) => setForm({ ...form, api_request_id: e.target.value })}>{requests.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.method} {item.url}</option>)}</select></label>
          <p className="muted">The saved request, authentication, assertions, and extractors are reused when this suite runs.</p>
        </> : <>
          <div className="form-grid">
            <label className="field">HTTP method<select value={request.method} onChange={(e) => setRequest({ method: e.target.value as HttpMethod })}>{["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].map((method) => <option key={method}>{method}</option>)}</select></label>
            <label className="field">Request URL<input required value={request.url} onChange={(e) => setRequest({ url: e.target.value })} placeholder="${base_url}/users/${user_id}" /></label>
          </div>
          <div className="api-tabs">{["headers", "params", "auth", "body"].map((item) => <button type="button" key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item === "auth" ? "Authorization" : item}</button>)}</div>
          <div className="request-editor-panel">
            {tab === "headers" && <KeyValueEditor items={request.headers} onChange={(headers) => setRequest({ headers })} />}
            {tab === "params" && <KeyValueEditor items={request.query_parameters} onChange={(query_parameters) => setRequest({ query_parameters })} />}
            {tab === "auth" && <AuthEditor type={request.authentication_type} config={request.authentication_config} onType={(authentication_type) => setRequest({ authentication_type })} onConfig={(authentication_config) => setRequest({ authentication_config })} />}
            {tab === "body" && <BodyEditor type={request.body_type} body={request.body ?? ""} onType={(body_type) => setRequest({ body_type })} onBody={(body) => setRequest({ body })} />}
          </div>
        </>}
      </>}

      {form.step_type === "ASSERTION" && <AutomationAssertionEditor value={config.assertions ?? []} onChange={(assertions) => setConfig({ assertions })} />}
      {form.step_type === "EXTRACT_VARIABLE" && <>
        <div className="form-grid">
          <label className="field">Extract from<select value={config.source} onChange={(e) => setConfig({ source: e.target.value as "JSON_PATH" | "HEADER" })}><option value="JSON_PATH">JSON path</option><option value="HEADER">Response header</option></select></label>
          <label className="field">{config.source === "HEADER" ? "Header name" : "JSON path"}<input required value={config.path ?? ""} onChange={(e) => setConfig({ path: e.target.value })} placeholder={config.source === "HEADER" ? "Authorization" : "$.data.id"} /></label>
        </div>
        {config.source === "HEADER" && <label className="field">Strip prefix (optional)<input value={config.strip_prefix ?? ""} onChange={(e) => setConfig({ strip_prefix: e.target.value })} placeholder="Bearer " /></label>}
      </>}
      {["EXTRACT_VARIABLE", "SET_VARIABLE"].includes(form.step_type) && <>
        <label className="field">Variable name<input required pattern="[A-Za-z_][A-Za-z0-9_]*" value={config.variable_name ?? ""} onChange={(e) => setConfig({ variable_name: e.target.value })} /></label>
        {form.step_type === "SET_VARIABLE" && <label className="field">Variable value<input type={config.is_secret ? "password" : "text"} value={config.value ?? ""} onChange={(e) => setConfig({ value: e.target.value })} /></label>}
        <label className="checkbox-field"><input type="checkbox" checked={config.is_secret ?? false} onChange={(e) => setConfig({ is_secret: e.target.checked })} />Treat as secret</label>
      </>}
      {form.step_type === "DELAY" && <label className="field">Delay (seconds)<input type="number" min={0} max={60} step="0.1" required value={config.seconds ?? 1} onChange={(e) => setConfig({ seconds: Number(e.target.value) })} /></label>}
      {form.step_type === "CONDITION" && <><p className="muted">When this condition is false, the next step is skipped.</p><ConditionEditor value={config as AutomationCondition} onChange={(condition) => setForm({ ...form, config: condition })} /></>}
      <p className="muted automation-variable-help">Use <code>{"${token}"}</code> or <code>{"{{user_id}}"}</code> to reference environment or workflow variables.</p>
      <label className="checkbox-field"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />Step enabled</label>
      <label className="checkbox-field"><input type="checkbox" checked={!!form.condition} onChange={(e) => setForm({ ...form, condition: e.target.checked ? { ...DEFAULT_CONDITION } : null })} />Only run this step when a condition is true</label>
      {form.condition && <ConditionEditor value={form.condition} onChange={(condition) => setForm({ ...form, condition })} />}
      <div className="modal-actions"><Button type="button" variant="secondary" disabled={busy} onClick={onClose}>Cancel</Button><Button type="submit" isLoading={busy}>Save step</Button></div>
    </form>
  </Modal>;
}
