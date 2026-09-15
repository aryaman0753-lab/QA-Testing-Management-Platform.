import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { BugForm } from "../components/bugs/BugForm";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { createBug, uploadBugAttachment } from "../api/bugs";
import { extractErrorMessage } from "../api/client";
import { getProject, listMembers } from "../api/projects";
import { useToast } from "../context/ToastContext";
import type { BugPayload, Project, ProjectMember } from "../types";

export function CreateBug() {
  const { projectId = "" } = useParams(); const navigate = useNavigate(); const { showToast } = useToast();
  const [project, setProject] = useState<Project | null>(null); const [members, setMembers] = useState<ProjectMember[] | null>(null);
  useEffect(() => { Promise.all([getProject(projectId), listMembers(projectId)]).then(([p, m]) => { setProject(p.data); setMembers(m.data); }).catch((error) => { showToast(extractErrorMessage(error), "error"); navigate(`/projects/${projectId}/bugs`); }); }, [navigate, projectId, showToast]);
  async function submit(payload: BugPayload, files: File[]) {
    try {
      const response = await createBug(projectId, payload);
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
  return <AppLayout><div className="page-header"><div><h1>Create Bug</h1><p className="muted">{project ? `${project.name} (${project.key})` : "Loading project..."}</p></div></div><section className="panel bug-form-panel">{members ? <BugForm members={members} onSubmit={submit} onCancel={() => navigate(`/projects/${projectId}/bugs`)} /> : <LoadingSpinner />}</section></AppLayout>;
}
