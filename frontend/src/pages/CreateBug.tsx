import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { BugForm } from "../components/bugs/BugForm";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { createBug, uploadBugAttachment } from "../api/bugs";
import { createBugFromResult, getBugSuggestion } from "../api/apiTesting";
import { extractErrorMessage } from "../api/client";
import { getProject, listMembers } from "../api/projects";
import { useToast } from "../context/ToastContext";
import type { BugPayload, Project, ProjectMember } from "../types";

export function CreateBug() {
  const { projectId = "" } = useParams(); const navigate = useNavigate(); const { showToast } = useToast();
  const [searchParams] = useSearchParams(); const sourceResult = searchParams.get("source_result");
  const [project, setProject] = useState<Project | null>(null); const [members, setMembers] = useState<ProjectMember[] | null>(null);
  const [suggestion, setSuggestion] = useState<BugPayload | null>(null);
  useEffect(() => { Promise.all([getProject(projectId), listMembers(projectId), sourceResult ? getBugSuggestion(sourceResult) : Promise.resolve(null)]).then(([p, m, s]) => { setProject(p.data); setMembers(m.data); setSuggestion(s?.data ?? null); }).catch((error) => { showToast(extractErrorMessage(error), "error"); navigate(`/projects/${projectId}/bugs`); }); }, [navigate, projectId, showToast, sourceResult]);
  async function submit(payload: BugPayload, files: File[]) {
    try {
      const response = sourceResult ? await createBugFromResult(sourceResult, payload) : await createBug(projectId, payload);
      try {
        for (const file of files) await uploadBugAttachment(response.data.id, file);
      } catch (error) {
        showToast(`Bug created, but evidence upload failed: ${extractErrorMessage(error)}`, "error");
        navigate(`/projects/${projectId}/bugs/${response.data.id}`);
        return;
      }
      showToast("Bug created successfully.", "success"); navigate(`/projects/${projectId}/bugs/${response.data.id}`);
    } catch (error) { throw new Error(extractErrorMessage(error)); }
  }
  const ready = members && (!sourceResult || suggestion);
  return <AppLayout><div className="page-header"><div><h1>Create Bug</h1><p className="muted">{project ? `${project.name} (${project.key})` : "Loading project..."}</p>{sourceResult && <p className="source-note">Pre-populated from a failed API test result. Review and edit before creating.</p>}</div></div><section className="panel bug-form-panel">{ready ? <BugForm members={members} initial={suggestion ?? undefined} onSubmit={submit} onCancel={() => navigate(sourceResult ? `/projects/${projectId}/api-testing/runs` : `/projects/${projectId}/bugs`)} /> : <LoadingSpinner />}</section></AppLayout>;
}
