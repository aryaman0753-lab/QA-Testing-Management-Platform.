import type { BugPriority, BugSeverity, BugStatus } from "../../types";

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function BugStatusBadge({ status }: { status: BugStatus }) {
  return <span className={`bug-badge bug-status-${status.toLowerCase()}`}>{label(status)}</span>;
}

export function SeverityBadge({ severity }: { severity: BugSeverity }) {
  return <span className={`bug-badge bug-severity-${severity.toLowerCase()}`}>{label(severity)}</span>;
}

export function PriorityBadge({ priority }: { priority: BugPriority }) {
  return <span className={`bug-badge bug-priority-${priority.toLowerCase()}`}>{label(priority)}</span>;
}
