import { apiClient } from "./client";

export const getProjectDashboard = (projectId: string) => apiClient.get(`/projects/${projectId}/qa-dashboard`);
export const getQAReport = (projectId: string) => apiClient.get(`/projects/${projectId}/reports/qa`);
export const exportQAReport = (projectId: string, format: "json" | "csv" | "pdf") => apiClient.get(`/projects/${projectId}/reports/export`, { params: { format }, responseType: "blob" });
export const getAdminSystem = () => apiClient.get("/admin/system");
export const listApiKeys = (projectId: string) => apiClient.get(`/projects/${projectId}/integrations/api-keys`);
export const createApiKey = (projectId: string, name: string) => apiClient.post(`/projects/${projectId}/integrations/api-keys`, { name });
export const revokeApiKey = (projectId: string, keyId: string) => apiClient.delete(`/projects/${projectId}/integrations/api-keys/${keyId}`);
export const listWebhooks = (projectId: string) => apiClient.get(`/projects/${projectId}/integrations/webhooks`);
export const createWebhook = (projectId: string, payload: { name: string; url: string; secret: string; events: string[] }) => apiClient.post(`/projects/${projectId}/integrations/webhooks`, payload);
export const deleteWebhook = (projectId: string, id: string) => apiClient.delete(`/projects/${projectId}/integrations/webhooks/${id}`);
export const listDeliveries = (projectId: string) => apiClient.get(`/projects/${projectId}/integrations/webhook-deliveries`);
export const listNotifications = () => apiClient.get("/notifications");
export const markNotificationRead = (id: string) => apiClient.patch(`/notifications/${id}/read`);
export const getNotificationPreferences = () => apiClient.get("/notifications/preferences");
export const saveNotificationPreferences = (payload: { project_id: string | null; in_app_enabled: boolean; email_enabled: boolean; webhook_enabled: boolean; events: string[] }) => apiClient.put("/notifications/preferences", payload);
