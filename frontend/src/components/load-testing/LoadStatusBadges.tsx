import type { LoadTestResultStatus, LoadTestStatus } from "../../types/loadTesting";

export function LoadStatusBadge({ status }: { status: LoadTestStatus }) {
  return <span className={`load-badge load-status-${status.toLowerCase()}`}>{status.replaceAll("_", " ")}</span>;
}

export function LoadResultBadge({ status }: { status: LoadTestResultStatus | null }) {
  if (!status) return <span className="muted">Pending</span>;
  return <span className={`load-badge load-result-${status.toLowerCase()}`}>{status.replaceAll("_", " ")}</span>;
}
