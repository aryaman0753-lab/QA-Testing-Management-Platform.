import { apiClient } from "./client";
import type { AutomationCase, AutomationPage, AutomationRun, AutomationSchedule, AutomationStatistics, AutomationStep, AutomationSuite, CasePayload, RunFilters, SchedulePayload, StepPayload, SuitePayload } from "../types/automation";

export const listAutomationSuites = (projectId: string, page = 1, pageSize = 20) => apiClient.get<AutomationPage<AutomationSuite>>(`/projects/${projectId}/automation/suites`, { params: { page, page_size: pageSize } });
export const getAutomationSuite = (id: string) => apiClient.get<AutomationSuite>(`/automation/suites/${id}`);
export const createAutomationSuite = (projectId: string, payload: SuitePayload) => apiClient.post<AutomationSuite>(`/projects/${projectId}/automation/suites`, payload);
export const updateAutomationSuite = (id: string, payload: Partial<SuitePayload>) => apiClient.patch<AutomationSuite>(`/automation/suites/${id}`, payload);
export const deleteAutomationSuite = (id: string) => apiClient.delete(`/automation/suites/${id}`);
export const createAutomationCase = (suiteId: string, payload: CasePayload) => apiClient.post<AutomationCase>(`/automation/suites/${suiteId}/cases`, payload);
export const updateAutomationCase = (id: string, payload: Partial<CasePayload>) => apiClient.patch<AutomationCase>(`/automation/cases/${id}`, payload);
export const deleteAutomationCase = (id: string) => apiClient.delete(`/automation/cases/${id}`);
export const reorderAutomationCases = (id: string, ids: string[]) => apiClient.put(`/automation/suites/${id}/cases/reorder`, { ids });
export const createAutomationStep = (caseId: string, payload: StepPayload) => apiClient.post<AutomationStep>(`/automation/cases/${caseId}/steps`, payload);
export const updateAutomationStep = (id: string, payload: Partial<StepPayload>) => apiClient.patch<AutomationStep>(`/automation/steps/${id}`, payload);
export const deleteAutomationStep = (id: string) => apiClient.delete(`/automation/steps/${id}`);
export const reorderAutomationSteps = (id: string, ids: string[]) => apiClient.put(`/automation/cases/${id}/steps/reorder`, { ids });
export const startAutomationRun = (id: string, environmentId: string | null, confirmProduction: boolean) => apiClient.post<AutomationRun>(`/automation/suites/${id}/run`, { environment_id: environmentId, confirm_production: confirmProduction });
export const listAutomationRuns = (projectId: string, page = 1, filters: RunFilters = {}) => apiClient.get<AutomationPage<AutomationRun>>(`/projects/${projectId}/automation/runs`, { params: { page, page_size: 20, ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)) } });
export const getAutomationRun = (id: string) => apiClient.get<AutomationRun>(`/automation/runs/${id}`);
export const stopAutomationRun = (id: string) => apiClient.post<AutomationRun>(`/automation/runs/${id}/stop`);
export const listAutomationSchedules = (projectId: string, page = 1) => apiClient.get<AutomationPage<AutomationSchedule>>(`/projects/${projectId}/automation/schedules`, { params: { page, page_size: 20 } });
export const createAutomationSchedule = (projectId: string, payload: SchedulePayload) => apiClient.post<AutomationSchedule>(`/projects/${projectId}/automation/schedules`, payload);
export const updateAutomationSchedule = (id: string, payload: Partial<SchedulePayload>) => apiClient.patch<AutomationSchedule>(`/automation/schedules/${id}`, payload);
export const deleteAutomationSchedule = (id: string) => apiClient.delete(`/automation/schedules/${id}`);
export const getAutomationStatistics = (projectId: string, filters: RunFilters = {}) => apiClient.get<AutomationStatistics>(`/projects/${projectId}/automation/statistics`, { params: Object.fromEntries(Object.entries(filters).filter(([, value]) => value)) });
export const compareAutomationRuns = (projectId: string, runA: string, runB: string) => apiClient.get(`/projects/${projectId}/automation/compare`, { params: { run_a: runA, run_b: runB } });

// Selectors must include suites beyond the first page.
export async function allAutomationSuites(projectId: string) {
  const first = (await listAutomationSuites(projectId, 1, 100)).data;
  const pages = await Promise.all(Array.from({ length: Math.max(0, first.total_pages - 1) }, (_, i) => listAutomationSuites(projectId, i + 2, 100)));
  return [...first.items, ...pages.flatMap((page) => page.data.items)];
}
