import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { BugAnalyticsPanel } from "../components/bugs/BugAnalyticsPanel";
import { BugFilters } from "../components/bugs/BugFilters";
import { BugTable } from "../components/bugs/BugTable";
import { Pagination } from "../components/bugs/Pagination";
import { downloadBugReport, getProjectBugAnalytics, listBugs, type BugQuery } from "../api/bugs";
import { getProject, listMembers } from "../api/projects";
import { extractErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import type { BugAnalytics, PaginatedBugs, Project, ProjectMember } from "../types";

export function ProjectBugs() {
  const { projectId = "" } = useParams(); const { user } = useAuth(); const { showToast } = useToast();
  const [project, setProject] = useState<Project | null>(null); const [members, setMembers] = useState<ProjectMember[]>([]);
  const [result, setResult] = useState<PaginatedBugs | null>(null); const [analytics, setAnalytics] = useState<BugAnalytics | null>(null);
  const [query, setQuery] = useState<BugQuery>({ page: 1, page_size: 20, sort_by: "created_at", sort_order: "desc" });
  const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!projectId) return; setLoading(true); setError(null);
    try {
      const [bugsResponse, projectResponse, memberResponse, analyticsResponse] = await Promise.all([listBugs(projectId, query), getProject(projectId), listMembers(projectId), getProjectBugAnalytics(projectId)]);
      setResult(bugsResponse.data); setProject(projectResponse.data); setMembers(memberResponse.data); setAnalytics(analyticsResponse.data);
    } catch (reason) { setError(extractErrorMessage(reason)); } finally { setLoading(false); }
  }, [projectId, query]);
  useEffect(() => { load(); }, [load]);
  async function report() { try { const response = await downloadBugReport(projectId); const url = URL.createObjectURL(response.data); const link = document.createElement("a"); link.href = url; link.download = `${project?.key ?? "project"}-bugs.csv`; link.click(); URL.revokeObjectURL(url); } catch (reason) { showToast(extractErrorMessage(reason), "error"); } }
  const canCreate = user?.role === "ADMIN" || user?.role === "QA_ENGINEER";
  return <AppLayout>
    <div className="page-header"><div><h1>{project?.key ?? "Project"} — Bugs</h1><p className="muted">Search, triage, and track every issue through verification.</p></div><div className="button-row"><Button variant="secondary" onClick={report}>Export CSV</Button>{canCreate && <Link className="btn btn-primary link-button" to={`/projects/${projectId}/bugs/new`}>+ Create Bug</Link>}</div></div>
    {analytics && <BugAnalyticsPanel analytics={analytics} />}
    <section className="panel"><BugFilters members={members} value={query} onApply={setQuery} />
      {loading ? <LoadingSpinner /> : error ? <EmptyState title="Unable to load bugs" description={error} action={<Button onClick={load}>Try again</Button>} /> : !result?.items.length ? <EmptyState title="No bugs found" description={query.search ? "Try changing the filters or search." : "Create your first bug."} action={canCreate && <Link className="btn btn-primary link-button" to={`/projects/${projectId}/bugs/new`}>Create Bug</Link>} /> : <><BugTable bugs={result.items} projectId={projectId} /><Pagination page={result.page} totalPages={result.total_pages} total={result.total} onChange={(page) => setQuery((current) => ({ ...current, page }))} /></>}
    </section>
  </AppLayout>;
}
