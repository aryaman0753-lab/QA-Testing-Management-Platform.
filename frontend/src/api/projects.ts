import { apiClient } from "./client";
import type { Project, ProjectMember, ProjectStatus } from "../types";

export function listProjects() {
  return apiClient.get<Project[]>("/projects");
}

export function getProject(projectId: string) {
  return apiClient.get<Project>(`/projects/${projectId}`);
}

export function createProject(payload: { name: string; key: string; description?: string }) {
  return apiClient.post<Project>("/projects", payload);
}

export function updateProject(
  projectId: string,
  payload: Partial<{ name: string; description: string; status: ProjectStatus }>
) {
  return apiClient.put<Project>(`/projects/${projectId}`, payload);
}

export function archiveProject(projectId: string) {
  return apiClient.delete<Project>(`/projects/${projectId}`);
}

export function listMembers(projectId: string) {
  return apiClient.get<ProjectMember[]>(`/projects/${projectId}/members`);
}

export function addMember(projectId: string, userId: string, projectRole: string) {
  return apiClient.post<ProjectMember>(`/projects/${projectId}/members`, {
    user_id: userId,
    project_role: projectRole,
  });
}

export function removeMember(projectId: string, userId: string) {
  return apiClient.delete(`/projects/${projectId}/members/${userId}`);
}
