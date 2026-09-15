import { Link } from "react-router-dom";
import type { BugListItem } from "../../types";
import { BugStatusBadge, PriorityBadge, SeverityBadge } from "./BugBadges";

export function BugTable({ bugs, projectId }: { bugs: BugListItem[]; projectId: string }) {
  return (
    <div className="table-scroll">
      <table className="table bug-table">
        <thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Priority</th><th>Status</th><th>Assignee</th><th>Updated</th></tr></thead>
        <tbody>{bugs.map((bug) => (
          <tr key={bug.id}>
            <td><Link to={`/projects/${projectId}/bugs/${bug.id}`}><code>{bug.bug_key}</code></Link></td>
            <td><Link to={`/projects/${projectId}/bugs/${bug.id}`}>{bug.title}</Link></td>
            <td><SeverityBadge severity={bug.severity} /></td>
            <td><PriorityBadge priority={bug.priority} /></td>
            <td><BugStatusBadge status={bug.status} /></td>
            <td>{bug.assignee?.full_name ?? <span className="muted">Unassigned</span>}</td>
            <td>{new Date(bug.updated_at).toLocaleDateString()}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
