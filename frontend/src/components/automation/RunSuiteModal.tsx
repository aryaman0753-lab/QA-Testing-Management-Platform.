import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startAutomationRun } from "../../api/automation";
import { extractErrorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import type { ApiEnvironment } from "../../types/apiTesting";
import type { AutomationSuite } from "../../types/automation";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { AutomationError } from "./AutomationShared";

export function RunSuiteModal({ suite, environments, onClose }: { suite: AutomationSuite; environments: ApiEnvironment[]; onClose: () => void }) {
  const [environmentId, setEnvironmentId] = useState(suite.environment_id ?? ""); const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const { user } = useAuth(); const { showToast } = useToast(); const navigate = useNavigate();
  const production = environments.find((item) => item.id === environmentId)?.classification === "PRODUCTION";
  async function start() { setBusy(true); setError(""); try { const { data } = await startAutomationRun(suite.id, environmentId || null, production && confirmed); showToast("Automation run queued.", "success"); navigate(`/projects/${suite.project_id}/automation/runs/${data.id}`); } catch (reason) { setError(extractErrorMessage(reason)); } finally { setBusy(false); } }
  return <Modal title={`Run ${suite.name}`} onClose={() => !busy && onClose()}>{error && <AutomationError message={error} />}<label className="field">Execution environment<select value={environmentId} onChange={(e) => { setEnvironmentId(e.target.value); setConfirmed(false); }}><option value="">No environment</option>{environments.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.classification})</option>)}</select></label><p>The workflow will execute its enabled cases in order. Requests may create, modify, or delete data.</p><p className="muted">Allowed hosts: {suite.allowed_hosts.join(", ") || "None configured"}</p>{!suite.allowed_hosts.length && <AutomationError message="Configure the suite's allowed hosts before execution." />}{production && <div className="alert alert-error"><p>Production execution requires an administrator and explicit server configuration.</p><label className="checkbox-field"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />I authorize this workflow to modify the selected production environment.</label></div>}<div className="modal-actions"><Button variant="secondary" disabled={busy} onClick={onClose}>Cancel</Button><Button isLoading={busy} disabled={!suite.allowed_hosts.length || (production && (!confirmed || user?.role !== "ADMIN"))} onClick={start}>Run suite</Button></div></Modal>;
}
