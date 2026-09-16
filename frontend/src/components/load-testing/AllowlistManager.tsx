import { useEffect, useState } from "react";
import { extractErrorMessage } from "../../api/client";
import { getLoadSettings, updateLoadSettings } from "../../api/loadTesting";
import { useToast } from "../../context/ToastContext";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

export function AllowlistManager({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [enabled, setEnabled] = useState(true); const [hosts, setHosts] = useState(""); const [busy, setBusy] = useState(false); const { showToast } = useToast();
  useEffect(() => { getLoadSettings(projectId).then(({ data }) => { setEnabled(data.enabled); setHosts(data.allowed_hosts.join("\n")); }).catch((error) => showToast(extractErrorMessage(error), "error")); }, [projectId, showToast]);
  async function save() { setBusy(true); try { await updateLoadSettings(projectId, { enabled, allowed_hosts: hosts.split(/[\n,]/).map((host) => host.trim()).filter(Boolean) }); showToast("Load-test security settings saved.", "success"); onClose(); } catch (error) { showToast(extractErrorMessage(error), "error"); } finally { setBusy(false); } }
  return <Modal title="Load target allowlist" onClose={onClose}><p className="muted">Only exact hosts and their subdomains are accepted. URLs are also checked for private, loopback, and metadata addresses before every run.</p><label className="field checkbox-field"><span><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Require project allowlist</span></label><label className="field"><span>Allowed hosts</span><textarea rows={7} value={hosts} onChange={(event) => setHosts(event.target.value)} placeholder={"qa.example.com\napi.staging.example.com"} /><small>One hostname per line. Do not include a scheme or path.</small></label><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button isLoading={busy} onClick={save}>Save</Button></div></Modal>;
}
