import { useState, type FormEvent } from "react";
import type { BugPayload, ProjectMember } from "../../types";
import { Button } from "../ui/Button";

const EMPTY: BugPayload = { title: "", description: "", steps_to_reproduce: [], severity: "MEDIUM", priority: "MEDIUM" };

export function BugForm({ members, initial, submitLabel = "Create Bug", onSubmit, onCancel, limitedFields = false, isEdit = false }: {
  members: ProjectMember[]; initial?: BugPayload; submitLabel?: string;
  onSubmit: (payload: BugPayload, files: File[]) => Promise<void>; onCancel: () => void; limitedFields?: boolean; isEdit?: boolean;
}) {
  const [form, setForm] = useState<BugPayload>(initial ?? EMPTY);
  const [steps, setSteps] = useState((initial?.steps_to_reproduce ?? []).join("\n"));
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  function set<K extends keyof BugPayload>(key: K, value: BugPayload[K]) { setForm((current) => ({ ...current, [key]: value })); }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.title.trim() || !form.description.trim()) { setError("Title and description are required."); return; }
    setSaving(true); setError(null);
    try { await onSubmit({ ...form, title: form.title.trim(), description: form.description.trim(), steps_to_reproduce: steps.split("\n").map((s) => s.trim()).filter(Boolean) }, files); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save bug."); }
    finally { setSaving(false); }
  }
  return (
    <form onSubmit={submit}>
      {error && <div className="alert alert-error">{error}</div>}
      <label className="field"><span>Title *</span><input disabled={limitedFields} maxLength={500} required value={form.title} onChange={(e) => set("title", e.target.value)} /></label>
      <label className="field"><span>Description *</span><textarea rows={5} required value={form.description} onChange={(e) => set("description", e.target.value)} /></label>
      <label className="field"><span>Steps to Reproduce</span><textarea rows={5} placeholder="Enter one step per line" value={steps} onChange={(e) => setSteps(e.target.value)} /></label>
      <div className="form-grid">
        <label className="field"><span>Expected Result</span><textarea rows={3} value={form.expected_result ?? ""} onChange={(e) => set("expected_result", e.target.value)} /></label>
        <label className="field"><span>Actual Result</span><textarea rows={3} value={form.actual_result ?? ""} onChange={(e) => set("actual_result", e.target.value)} /></label>
        <label className="field"><span>Severity *</span><select disabled={limitedFields} value={form.severity} onChange={(e) => set("severity", e.target.value as BugPayload["severity"])}>{["CRITICAL", "HIGH", "MEDIUM", "LOW", "TRIVIAL"].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label className="field"><span>Priority *</span><select disabled={limitedFields} value={form.priority} onChange={(e) => set("priority", e.target.value as BugPayload["priority"])}>{["URGENT", "HIGH", "MEDIUM", "LOW"].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label className="field"><span>Environment</span><input value={form.environment ?? ""} onChange={(e) => set("environment", e.target.value)} placeholder="QA" /></label>
        <label className="field"><span>Browser</span><input value={form.browser ?? ""} onChange={(e) => set("browser", e.target.value)} placeholder="Chrome" /></label>
        <label className="field"><span>Operating System</span><input value={form.operating_system ?? ""} onChange={(e) => set("operating_system", e.target.value)} placeholder="Windows 11" /></label>
        <label className="field"><span>Device</span><input value={form.device ?? ""} onChange={(e) => set("device", e.target.value)} placeholder="Desktop" /></label>
        {!isEdit && <label className="field"><span>Assignee</span><select value={form.assigned_to ?? ""} onChange={(e) => set("assigned_to", e.target.value || null)}><option value="">Unassigned</option>{members.map((m) => <option key={m.user_id} value={m.user_id}>{m.user.full_name}</option>)}</select></label>}
        {!isEdit && <label className="field"><span>Attachments</span><input type="file" multiple accept="image/png,image/jpeg,image/gif,image/webp,text/plain,video/mp4,video/webm,.log" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /><small>Images, text/log, MP4 or WebM; max 10 MB each.</small></label>}
      </div>
      <div className="modal-actions"><Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button><Button type="submit" isLoading={saving}>{submitLabel}</Button></div>
    </form>
  );
}
