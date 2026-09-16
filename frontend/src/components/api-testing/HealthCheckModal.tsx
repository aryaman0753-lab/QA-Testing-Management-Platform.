import { useState } from "react";
import { runHealthCheck } from "../../api/apiTesting";
import { extractErrorMessage } from "../../api/client";
import type { HealthCheckResult } from "../../types/apiTesting";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { ExecutionBadge } from "./ResponseViewer";

export function HealthCheckModal({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [url, setUrl] = useState("https://"); const [expected, setExpected] = useState(200);
  const [maximum, setMaximum] = useState(2000); const [result, setResult] = useState<HealthCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null); const [running, setRunning] = useState(false);
  async function run() { setRunning(true); setError(null); try { const response = await runHealthCheck(projectId, { url, expected_status: expected, max_response_time_ms: maximum }); setResult(response.data); } catch (reason) { setError(extractErrorMessage(reason)); } finally { setRunning(false); } }
  return <Modal title="Quick health check" onClose={onClose}><p className="muted">Run an unsaved status and response-time check. Private network targets are blocked.</p><label className="field"><span>URL</span><input value={url} onChange={(e) => setUrl(e.target.value)} /></label><div className="form-grid"><label className="field"><span>Expected status</span><input type="number" value={expected} onChange={(e) => setExpected(Number(e.target.value))} /></label><label className="field"><span>Max time (ms)</span><input type="number" value={maximum} onChange={(e) => setMaximum(Number(e.target.value))} /></label></div>{error && <div className="alert alert-error">{error}</div>}{result && <div className="health-result"><ExecutionBadge status={result.status} /><strong>{result.status_code ?? "No response"}</strong><span>{result.response_time_ms.toFixed(0)} ms</span>{result.error_message && <small>{result.error_message}</small>}</div>}<div className="modal-actions"><Button variant="secondary" onClick={onClose}>Close</Button><Button isLoading={running} onClick={run}>Run check</Button></div></Modal>;
}
