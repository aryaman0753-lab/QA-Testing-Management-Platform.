import { Link, NavLink } from "react-router-dom";
import type { AutomationPage, AutomationRun, AutomationSuite } from "../../types/automation";
import { Button } from "../ui/Button";

export function AutomationNav({ projectId }: { projectId: string }) {
  const base = `/projects/${projectId}/automation`;
  return <nav className="automation-nav" aria-label="Automation"><NavLink end to={base}>Overview & suites</NavLink><NavLink to={`${base}/runs`}>Run history</NavLink><NavLink to={`${base}/schedules`}>Schedules</NavLink></nav>;
}
export function AutomationBadge({ status }: { status: string }) { return <span className={`automation-badge automation-${status.toLowerCase()}`}>{status.replaceAll("_", " ")}</span>; }
export function AutomationPagination({ data, onChange }: { data: AutomationPage<unknown>; onChange: (page: number) => void }) {
  if (!data.total) return null;
  return <div className="pagination"><span className="muted">{data.total} items · Page {data.page} of {Math.max(1, data.total_pages)}</span><div className="button-row"><Button variant="secondary" disabled={data.page <= 1} onClick={() => onChange(data.page - 1)}>Previous</Button><Button variant="secondary" disabled={data.page >= data.total_pages} onClick={() => onChange(data.page + 1)}>Next</Button></div></div>;
}
export function AutomationRunTable({ runs, projectId, suites = [] }: { runs: AutomationRun[]; projectId: string; suites?: AutomationSuite[] }) {
  return runs.length === 0 ? <p className="empty-state">No runs match this view.</p> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Run</th><th>Suite</th><th>Status</th><th>Steps</th><th>Duration</th><th>Trigger</th><th>Created</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id}><td><Link to={`/projects/${projectId}/automation/runs/${run.id}`}>{run.id.slice(0, 8)}</Link></td><td>{run.suite_name ?? suites.find((item) => item.id === run.suite_id)?.name ?? run.suite_id.slice(0, 8)}</td><td><AutomationBadge status={run.status} /></td><td>{run.passed_steps}/{run.total_steps} passed</td><td>{((run.duration_ms ?? 0) / 1000).toFixed(1)}s</td><td>{run.trigger_type === "SCHEDULED" ? "Scheduled" : "Manual"}</td><td>{new Date(run.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>;
}
export function AutomationError({ message, retry }: { message: string; retry?: () => void }) { return <div role="alert" className="alert alert-error">{message}{retry && <> <button type="button" className="inline-link" onClick={retry}>Try again</button></>}</div>; }
