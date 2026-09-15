import { apiClient } from "./client";
import type {
  BugAnalytics, BugAttachment, BugComment, BugDetail, BugPayload,
  BugPriority, BugSeverity, BugStatus, PaginatedBugs,
} from "../types";

export interface BugQuery {
  page?: number;
  page_size?: number;
  status?: BugStatus[];
  severity?: BugSeverity[];
  priority?: BugPriority[];
  assigned_to?: string;
  reported_by?: string;
  environment?: string;
  search?: string;
  created_from?: string;
  created_to?: string;
  updated_from?: string;
  updated_to?: string;
  sort_by?: "created_at" | "updated_at" | "priority" | "severity" | "status" | "bug_number";
  sort_order?: "asc" | "desc";
}

export function listBugs(projectId: string, params: BugQuery) {
  return apiClient.get<PaginatedBugs>(`/projects/${projectId}/bugs`, {
    params,
    paramsSerializer: { indexes: null },
  });
}

export function createBug(projectId: string, payload: BugPayload) {
  return apiClient.post<BugDetail>(`/projects/${projectId}/bugs`, payload);
}

export function getBug(bugId: string) {
  return apiClient.get<BugDetail>(`/bugs/${bugId}`);
}

export function updateBug(bugId: string, payload: Partial<BugPayload>) {
  return apiClient.patch<BugDetail>(`/bugs/${bugId}`, payload);
}

export function assignBug(bugId: string, assignedTo: string | null) {
  return apiClient.patch<BugDetail>(`/bugs/${bugId}/assignee`, { assigned_to: assignedTo });
}

export function changeBugStatus(bugId: string, status: BugStatus) {
  return apiClient.patch<BugDetail>(`/bugs/${bugId}/status`, { status });
}

export function addBugComment(bugId: string, comment: string) {
  return apiClient.post<BugComment>(`/bugs/${bugId}/comments`, { comment });
}

export function updateBugComment(bugId: string, commentId: string, comment: string) {
  return apiClient.put<BugComment>(`/bugs/${bugId}/comments/${commentId}`, { comment });
}

export function deleteBugComment(bugId: string, commentId: string) {
  return apiClient.delete(`/bugs/${bugId}/comments/${commentId}`);
}

export function uploadBugAttachment(bugId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post<BugAttachment>(`/bugs/${bugId}/attachments`, form);
}

export function downloadAttachment(attachmentId: string) {
  return apiClient.get<Blob>(`/bug-attachments/${attachmentId}/download`, { responseType: "blob" });
}

export function deleteAttachment(attachmentId: string) {
  return apiClient.delete(`/bug-attachments/${attachmentId}`);
}

export function getProjectBugAnalytics(projectId: string) {
  return apiClient.get<BugAnalytics>(`/projects/${projectId}/bugs/analytics`);
}

export function getDashboardBugAnalytics() {
  return apiClient.get<BugAnalytics>("/bugs/dashboard");
}

export function downloadBugReport(projectId: string) {
  return apiClient.get<Blob>(`/projects/${projectId}/bugs/report.csv`, { responseType: "blob" });
}
