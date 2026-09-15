import type { BugHistoryEntry } from "../../types";

function describe(entry: BugHistoryEntry) {
  if (entry.action === "CREATED") return "created this bug";
  if (entry.action === "ARCHIVED") return "archived this bug";
  if (entry.action === "STATUS_CHANGED") return `changed status: ${entry.old_value} → ${entry.new_value}`;
  if (entry.action === "ASSIGNEE_CHANGED") return "changed the assignee";
  if (entry.action === "FIELD_CHANGED") return `changed ${entry.field_name?.replaceAll("_", " ")}: ${entry.old_value ?? "empty"} → ${entry.new_value ?? "empty"}`;
  return entry.action.toLowerCase().replaceAll("_", " ");
}

export function BugHistory({ history }: { history: BugHistoryEntry[] }) {
  return <section className="panel"><h2>History</h2><div className="history-list">{history.map((entry) => (
    <div className="history-entry" key={entry.id}><span className="history-dot" /><div><strong>{entry.user.full_name}</strong> {describe(entry)}<div className="muted">{new Date(entry.created_at).toLocaleString()}</div></div></div>
  ))}</div></section>;
}
