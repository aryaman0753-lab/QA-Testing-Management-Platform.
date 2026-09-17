import type { ApiRequestPayload } from "./apiTesting";

export type SuiteStatus = "DRAFT" | "ACTIVE" | "DISABLED" | "ARCHIVED";
export type AutomationRunStatus = "QUEUED" | "RUNNING" | "PASSED" | "FAILED" | "CANCELLED";
export type StepType = "HTTP_REQUEST" | "ASSERTION" | "EXTRACT_VARIABLE" | "SET_VARIABLE" | "DELAY" | "CONDITION";
export interface AutomationCondition {
  source: "STATUS_CODE" | "VARIABLE" | "JSON_PATH" | "HEADER";
  operator: "EQUALS" | "NOT_EQUALS" | "CONTAINS" | "EXISTS";
  target?: string; expected?: string;
}
export interface AutomationAssertion {
  source: "STATUS_CODE" | "BODY" | "JSON_PATH" | "HEADER" | "RESPONSE_TIME";
  operator: "EQUALS" | "NOT_EQUALS" | "GREATER_THAN" | "LESS_THAN" | "CONTAINS" | "NOT_CONTAINS" | "EXISTS";
  target?: string; expected?: string;
}
export interface StepConfig {
  request?: ApiRequestPayload; assertions?: AutomationAssertion[];
  source?: "JSON_PATH" | "HEADER" | "STATUS_CODE" | "VARIABLE";
  operator?: AutomationCondition["operator"]; target?: string; expected?: string;
  path?: string; variable_name?: string; is_secret?: boolean;
  strip_prefix?: string; value?: string; seconds?: number;
}
export interface StepPayload { name: string; step_type: StepType; order_index: number; enabled: boolean; api_request_id: string | null; config: StepConfig; condition: AutomationCondition | null; }
export interface AutomationStep extends StepPayload { id: string; case_id: string; created_at: string; updated_at: string; }
export interface CasePayload { name: string; description: string; order_index: number; enabled: boolean; timeout: number; }
export interface AutomationCase extends CasePayload { id: string; suite_id: string; project_id: string; steps: AutomationStep[]; }
export interface SuitePayload { name: string; description: string; environment_id: string | null; status: SuiteStatus; auto_create_bugs: boolean; max_retries: number; allowed_hosts: string[]; }
export interface AutomationSuite extends SuitePayload { id: string; project_id: string; created_by: string; created_at: string; updated_at: string; cases?: AutomationCase[]; }
export interface AutomationStepResult {
  id: string; run_id: string; case_id: string; step_id: string; case_name: string; step_name: string; step_type: StepType;
  order_index: number; status: "PASSED" | "FAILED" | "SKIPPED" | "CANCELLED"; attempt: number; is_final: boolean;
  request_method: string | null; resolved_url: string | null; status_code: number | null; response_time_ms: number | null;
  assertions: { source?: string; description?: string; passed?: boolean; result?: boolean | string; expected?: unknown; actual?: unknown; failure_message?: string; message?: string }[];
  extracted_variables: Record<string, unknown>; error_message: string | null; error_kind: string | null;
  started_at: string; completed_at: string | null;
}
export interface AutomationRun {
  id: string; project_id: string; suite_id: string; suite_name?: string; environment_id: string | null; environment_name?: string;
  status: AutomationRunStatus; triggered_by: string; trigger_type: "MANUAL" | "SCHEDULED"; schedule_id: string | null;
  started_at: string | null; completed_at: string | null; duration_ms: number;
  total_cases: number; passed_cases: number; failed_cases: number; skipped_cases: number;
  total_steps: number; passed_steps: number; failed_steps: number; skipped_steps: number;
  created_at: string; heartbeat_at: string | null; stop_requested: boolean; error_message: string | null;
  config_snapshot: Record<string, unknown>; results?: AutomationStepResult[];
  linked_bugs?: { id: string; bug_key: string; title: string; status: string }[];
}
export interface SchedulePayload { suite_id: string; environment_id: string | null; cron_expression: string; timezone: string; enabled: boolean; }
export interface AutomationSchedule extends SchedulePayload { id: string; project_id: string; next_run_at: string | null; last_run_at: string | null; last_error: string | null; created_by: string; created_at: string; updated_at: string; }
export interface AutomationStatistics { total_suites: number; active_schedules: number; total_runs: number; pass_rate: number; failure_rate: number; average_duration_ms: number; recent_runs: AutomationRun[]; recent_failures: AutomationRun[]; failed_trends: { date: string; count: number }[]; }
export interface AutomationPage<T> { items: T[]; total: number; page: number; page_size: number; total_pages: number; }
export interface RunFilters { suite_id?: string; environment_id?: string; status?: string; created_from?: string; created_to?: string; }
