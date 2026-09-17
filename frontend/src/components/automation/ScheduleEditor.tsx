import { useState, type FormEvent } from "react";
import { extractErrorMessage } from "../../api/client";
import type { ApiEnvironment } from "../../types/apiTesting";
import type { AutomationSuite, SchedulePayload } from "../../types/automation";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { AutomationError } from "./AutomationShared";

const PRESETS = [{ label: "Every 5 minutes", value: "*/5 * * * *" }, { label: "Every hour", value: "0 * * * *" }, { label: "Every day at 09:00", value: "0 9 * * *" }, { label: "Every weekday at 09:00", value: "0 9 * * 1-5" }];
export function ScheduleEditor({ initial, suites, environments, onSave, onClose }: { initial?: SchedulePayload; suites: AutomationSuite[]; environments: ApiEnvironment[]; onSave: (payload: SchedulePayload) => Promise<void>; onClose: () => void }) {
  const [form, setForm] = useState<SchedulePayload>(initial ?? { suite_id: suites.find((suite) => suite.status === "ACTIVE")?.id ?? "", environment_id: null, cron_expression: "0 9 * * *", timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", enabled: true });
  const [preset, setPreset] = useState(PRESETS.some((item) => item.value === form.cron_expression) ? form.cron_expression : "custom");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const selected = suites.find((suite) => suite.id === form.suite_id);
  const effectiveEnv = environments.find((environment) => environment.id === (form.environment_id || selected?.environment_id));
  const production = effectiveEnv?.classification === "PRODUCTION";
  async function save(event: FormEvent) {
    event.preventDefault(); setError("");
    if (form.cron_expression.trim().split(/\s+/).length !== 5) { setError("Enter a five-field cron expression: minute hour day month weekday."); return; }
    try { new Intl.DateTimeFormat("en", { timeZone: form.timezone }).format(); } catch { setError("Enter a valid IANA timezone, such as UTC or America/New_York."); return; }
    if (production) { setError("Scheduled runs cannot target production. Select a development, QA, or staging environment."); return; }
    setBusy(true); try { await onSave(form); } catch (reason) { setError(extractErrorMessage(reason)); } finally { setBusy(false); }
  }
  return <Modal wide title={initial ? "Edit schedule" : "Create schedule"} onClose={() => !busy && onClose()}><form onSubmit={save}>{error && <AutomationError message={error} />}<label className="field">Suite<select required value={form.suite_id} disabled={!!initial} onChange={(e) => setForm({ ...form, suite_id: e.target.value })}><option value="">Select an active suite</option>{suites.filter((suite) => suite.status === "ACTIVE" || suite.id === initial?.suite_id).map((suite) => <option key={suite.id} value={suite.id}>{suite.name}</option>)}</select></label><label className="field">Schedule environment<select value={form.environment_id ?? ""} onChange={(e) => setForm({ ...form, environment_id: e.target.value || null })}><option value="">Suite default{selected?.environment_id ? ` (${environments.find((item) => item.id === selected.environment_id)?.name ?? "configured"})` : " (none)"}</option>{environments.filter((item) => item.classification !== "PRODUCTION").map((item) => <option key={item.id} value={item.id}>{item.name} ({item.classification})</option>)}</select></label>{production && <AutomationError message="The suite default targets production. Choose another environment for scheduled runs." />}<div className="form-grid"><label className="field">Frequency<select value={preset} onChange={(e) => { setPreset(e.target.value); if (e.target.value !== "custom") setForm({ ...form, cron_expression: e.target.value }); }}>{PRESETS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}<option value="custom">Custom cron expression</option></select></label><label className="field">Timezone<input required value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} placeholder="America/New_York" /></label></div><label className="field">Cron expression<input required value={form.cron_expression} onChange={(e) => { setPreset("custom"); setForm({ ...form, cron_expression: e.target.value }); }} /><small>Minute · Hour · Day of month · Month · Day of week. Times use the selected timezone.</small></label><label className="checkbox-field"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />Schedule enabled</label><p className="muted">A schedule skips execution while its previous run is still active.</p><div className="modal-actions"><Button type="button" variant="secondary" disabled={busy} onClick={onClose}>Cancel</Button><Button type="submit" isLoading={busy} disabled={production}>Save schedule</Button></div></form></Modal>;
}
