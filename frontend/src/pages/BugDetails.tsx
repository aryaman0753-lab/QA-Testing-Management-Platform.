import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { AttachmentList } from "../components/bugs/AttachmentList";
import { BugStatusBadge, PriorityBadge, SeverityBadge } from "../components/bugs/BugBadges";
import { BugComments } from "../components/bugs/BugComments";
import { BugForm } from "../components/bugs/BugForm";
import { BugHistory } from "../components/bugs/BugHistory";
import { BugStatusControl } from "../components/bugs/BugStatusControl";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { Modal } from "../components/ui/Modal";
import { assignBug, changeBugStatus, getBug, updateBug } from "../api/bugs";
import { extractErrorMessage } from "../api/client";
import { listMembers } from "../api/projects";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { BugDetail, BugPayload, BugStatus, ProjectMember } from "../types";

const NEXT: Record<BugStatus, BugStatus[]> = { NEW: ["ASSIGNED", "DUPLICATE", "WONT_FIX"], ASSIGNED: ["IN_PROGRESS", "DUPLICATE", "WONT_FIX"], IN_PROGRESS: ["FIXED", "DUPLICATE", "WONT_FIX"], FIXED: ["QA_VERIFICATION", "REOPENED"], QA_VERIFICATION: ["VERIFIED", "REOPENED"], VERIFIED: ["CLOSED", "REOPENED"], CLOSED: ["REOPENED"], REOPENED: ["IN_PROGRESS", "WONT_FIX"], DUPLICATE: ["REOPENED"], WONT_FIX: ["REOPENED"] };

export function BugDetails() {
  const { projectId = "", bugId = "" } = useParams(); const { user } = useAuth(); const { showToast } = useToast();
  const [bug, setBug] = useState<BugDetail | null>(null); const [members, setMembers] = useState<ProjectMember[]>([]); const [error, setError] = useState<string | null>(null); const [editing, setEditing] = useState(false);
  const load = useCallback(async () => { try { const [bugResponse, memberResponse] = await Promise.all([getBug(bugId), listMembers(projectId)]); setBug(bugResponse.data); setMembers(memberResponse.data); setError(null); } catch (reason) { setError(extractErrorMessage(reason)); } }, [bugId, projectId]);
  useEffect(() => { load(); }, [load]);
  if (error) return <AppLayout><EmptyState title="Unable to load bug" description={error} action={<Button onClick={load}>Try again</Button>} /></AppLayout>;
  if (!bug || !user) return <AppLayout><LoadingSpinner /></AppLayout>;
  const currentBug = bug;
  const canTriage = user.role === "ADMIN" || user.role === "QA_ENGINEER"; const canEdit = canTriage || (user.role === "DEVELOPER" && bug.assigned_to === user.id); const canUpload = canEdit;
  const developerNext: Partial<Record<BugStatus, BugStatus[]>> = { ASSIGNED: ["IN_PROGRESS"], REOPENED: ["IN_PROGRESS"], IN_PROGRESS: ["FIXED"], FIXED: ["QA_VERIFICATION"] };
  const allowedStatuses = user.role === "ADMIN" ? (["NEW", "ASSIGNED", "IN_PROGRESS", "FIXED", "QA_VERIFICATION", "VERIFIED", "CLOSED", "REOPENED", "DUPLICATE", "WONT_FIX"] as BugStatus[]) : user.role === "DEVELOPER" ? developerNext[bug.status] ?? [] : user.role === "QA_ENGINEER" ? NEXT[bug.status] : [];
  async function status(status: BugStatus) { try { const response = await changeBugStatus(currentBug.id, status); setBug(response.data); showToast("Status updated successfully.", "success"); } catch (reason) { showToast(extractErrorMessage(reason), "error"); } }
  async function assign(value: string) { try { const response = await assignBug(currentBug.id, value || null); setBug(response.data); showToast("Bug assigned successfully.", "success"); } catch (reason) { showToast(extractErrorMessage(reason), "error"); } }
  async function save(payload: BugPayload) { try { const fields = { ...payload }; delete fields.assigned_to; const response = await updateBug(currentBug.id, fields); setBug(response.data); setEditing(false); showToast("Bug updated successfully.", "success"); } catch (reason) { throw new Error(extractErrorMessage(reason)); } }
  const initial: BugPayload = { title: bug.title, description: bug.description, steps_to_reproduce: bug.steps_to_reproduce, expected_result: bug.expected_result, actual_result: bug.actual_result, severity: bug.severity, priority: bug.priority, environment: bug.environment, browser: bug.browser, operating_system: bug.operating_system, device: bug.device, assigned_to: bug.assigned_to };
  return <AppLayout>
    <div className="bug-breadcrumb"><Link to={`/projects/${projectId}/bugs`}>{bug.project.key} Bugs</Link> / {bug.bug_key}</div>
    <div className="page-header"><div><code>{bug.bug_key}</code><h1>{bug.title}</h1></div>{canEdit && <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>}</div>
    <section className="panel bug-summary"><div><span>Status</span><BugStatusBadge status={bug.status} /></div><div><span>Severity</span><SeverityBadge severity={bug.severity} /></div><div><span>Priority</span><PriorityBadge priority={bug.priority} /></div><div><span>Assigned to</span>{canTriage ? <select value={bug.assigned_to ?? ""} onChange={(e) => assign(e.target.value)}><option value="">Unassigned</option>{members.map((m) => <option value={m.user_id} key={m.user_id}>{m.user.full_name}</option>)}</select> : <strong>{bug.assignee?.full_name ?? "Unassigned"}</strong>}</div><div><span>Reported by</span><strong>{bug.reporter.full_name}</strong></div><div><span>Change status</span>{allowedStatuses.length ? <BugStatusControl allowed={allowedStatuses} onChange={status} /> : <span className="muted">No actions available</span>}</div></section>
    <section className="panel bug-content"><h2>Description</h2><p className="preserve-lines">{bug.description}</p><h2>Steps to Reproduce</h2>{bug.steps_to_reproduce.length ? <ol>{bug.steps_to_reproduce.map((step, i) => <li key={i}>{step}</li>)}</ol> : <p className="muted">No steps provided.</p>}<div className="form-grid"><div><h2>Expected Result</h2><p className="preserve-lines">{bug.expected_result || "—"}</p></div><div><h2>Actual Result</h2><p className="preserve-lines">{bug.actual_result || "—"}</p></div></div><h2>Environment</h2><p>{[bug.environment, bug.browser, bug.operating_system, bug.device].filter(Boolean).join(" · ") || "—"}</p></section>
    {bug.discovered_from_test_result && <section className="panel"><h2>API Test Source</h2><p><strong>{bug.discovered_from_test_result.request_name}</strong> · {bug.discovered_from_test_result.method} <code>{bug.discovered_from_test_result.resolved_url}</code></p><Link to={`/projects/${projectId}/api-testing/runs/${bug.discovered_from_test_result.test_run_id}`}>View source run</Link></section>}
    <AttachmentList bugId={bug.id} attachments={bug.attachments} currentUser={user} canUpload={canUpload} onChanged={load} />
    <BugComments bugId={bug.id} comments={bug.comments} currentUser={user} onChanged={load} />
    <BugHistory history={bug.history} />
    {editing && <Modal wide title={`Edit ${bug.bug_key}`} onClose={() => setEditing(false)}><BugForm members={members} initial={initial} isEdit limitedFields={user.role === "DEVELOPER"} submitLabel="Save Changes" onSubmit={save} onCancel={() => setEditing(false)} /></Modal>}
  </AppLayout>;
}
