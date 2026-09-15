import type { BugStatus } from "../../types";

export function BugStatusControl({ allowed, onChange }: { allowed: BugStatus[]; onChange: (status: BugStatus) => void }) {
  return <select aria-label="Change status" value="" onChange={(event) => onChange(event.target.value as BugStatus)}>
    <option value="">Select next status</option>
    {allowed.map((status) => <option key={status}>{status}</option>)}
  </select>;
}
