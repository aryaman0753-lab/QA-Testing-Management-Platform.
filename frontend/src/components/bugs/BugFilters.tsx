import { useState, type FormEvent } from "react";
import type { BugPriority, BugSeverity, BugStatus, ProjectMember } from "../../types";
import type { BugQuery } from "../../api/bugs";
import { Button } from "../ui/Button";

const STATUSES: BugStatus[] = ["NEW", "ASSIGNED", "IN_PROGRESS", "FIXED", "QA_VERIFICATION", "VERIFIED", "CLOSED", "REOPENED", "DUPLICATE", "WONT_FIX"];
const SEVERITIES: BugSeverity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "TRIVIAL"];
const PRIORITIES: BugPriority[] = ["URGENT", "HIGH", "MEDIUM", "LOW"];

export function BugFilters({ members, value, onApply }: { members: ProjectMember[]; value: BugQuery; onApply: (query: BugQuery) => void }) {
  const [draft, setDraft] = useState<BugQuery>(value);
  function submit(event: FormEvent) {
    event.preventDefault();
    onApply({ ...draft, page: 1 });
  }
  return (
    <form className="bug-filters" onSubmit={submit}>
      <input aria-label="Search bugs" placeholder="Search bug ID, title or description..." value={draft.search ?? ""} onChange={(e) => setDraft({ ...draft, search: e.target.value || undefined })} />
      <select aria-label="Status" value={draft.status?.[0] ?? ""} onChange={(e) => setDraft({ ...draft, status: e.target.value ? [e.target.value as BugStatus] : undefined })}>
        <option value="">All statuses</option>{STATUSES.map((item) => <option key={item}>{item}</option>)}
      </select>
      <select aria-label="Severity" value={draft.severity?.[0] ?? ""} onChange={(e) => setDraft({ ...draft, severity: e.target.value ? [e.target.value as BugSeverity] : undefined })}>
        <option value="">All severities</option>{SEVERITIES.map((item) => <option key={item}>{item}</option>)}
      </select>
      <select aria-label="Priority" value={draft.priority?.[0] ?? ""} onChange={(e) => setDraft({ ...draft, priority: e.target.value ? [e.target.value as BugPriority] : undefined })}>
        <option value="">All priorities</option>{PRIORITIES.map((item) => <option key={item}>{item}</option>)}
      </select>
      <select aria-label="Assignee" value={draft.assigned_to ?? ""} onChange={(e) => setDraft({ ...draft, assigned_to: e.target.value || undefined })}>
        <option value="">All assignees</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user.full_name}</option>)}
      </select>
      <select aria-label="Reporter" value={draft.reported_by ?? ""} onChange={(e) => setDraft({ ...draft, reported_by: e.target.value || undefined })}>
        <option value="">All reporters</option>{members.map((member) => <option key={member.user_id} value={member.user_id}>{member.user.full_name}</option>)}
      </select>
      <input aria-label="Environment" placeholder="Environment" value={draft.environment ?? ""} onChange={(e) => setDraft({ ...draft, environment: e.target.value || undefined })} />
      <label className="filter-date"><span>Created from</span><input type="date" value={draft.created_from ?? ""} onChange={(e) => setDraft({ ...draft, created_from: e.target.value || undefined })} /></label>
      <label className="filter-date"><span>Created to</span><input type="date" value={draft.created_to ?? ""} onChange={(e) => setDraft({ ...draft, created_to: e.target.value || undefined })} /></label>
      <label className="filter-date"><span>Updated from</span><input type="date" value={draft.updated_from ?? ""} onChange={(e) => setDraft({ ...draft, updated_from: e.target.value || undefined })} /></label>
      <label className="filter-date"><span>Updated to</span><input type="date" value={draft.updated_to ?? ""} onChange={(e) => setDraft({ ...draft, updated_to: e.target.value || undefined })} /></label>
      <select aria-label="Sort bugs" value={`${draft.sort_by ?? "created_at"}:${draft.sort_order ?? "desc"}`} onChange={(e) => {
        const [sort_by, sort_order] = e.target.value.split(":") as [BugQuery["sort_by"], BugQuery["sort_order"]];
        setDraft({ ...draft, sort_by, sort_order });
      }}>
        <option value="created_at:desc">Newest first</option><option value="created_at:asc">Oldest first</option>
        <option value="updated_at:desc">Recently updated</option><option value="priority:desc">Priority</option>
        <option value="severity:desc">Severity</option><option value="status:asc">Status</option><option value="bug_number:asc">Bug ID</option>
      </select>
      <Button type="submit">Apply</Button>
      <Button type="button" variant="ghost" onClick={() => { const clean = { page: 1, page_size: value.page_size ?? 20 } as BugQuery; setDraft(clean); onApply(clean); }}>Clear</Button>
    </form>
  );
}
