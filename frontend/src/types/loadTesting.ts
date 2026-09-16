import type { AuthenticationType, BodyType, HttpMethod, KeyValueItem } from "./apiTesting";

export type EnvironmentClassification = "DEVELOPMENT" | "TEST" | "QA" | "STAGING" | "PRODUCTION";
export type LoadTestProfile = "CUSTOM" | "SMOKE" | "BASELINE" | "LOAD" | "STRESS" | "SPIKE" | "SOAK";
export type LoadTestStatus = "DRAFT" | "QUEUED" | "STARTING" | "RUNNING" | "STOPPING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type LoadTestResultStatus = "PASS" | "FAIL" | "THRESHOLD_EXCEEDED" | "ERROR" | "CANCELLED";

export interface LoadThresholds {
  max_p95_ms: number | null;
  max_p99_ms: number | null;
  max_failure_rate: number | null;
  max_average_ms: number | null;
  min_rps: number | null;
  max_error_count: number | null;
}

export interface LoadTestPayload {
  name: string;
  description?: string | null;
  api_request_id?: string | null;
  environment_id: string;
  target_url: string;
  request_method: HttpMethod;
  headers: KeyValueItem[];
  query_parameters: KeyValueItem[];
  body?: string | null;
  body_type: BodyType;
  authentication_type: AuthenticationType;
  authentication_config: Record<string, string>;
  profile: LoadTestProfile;
  virtual_users: number;
  spawn_rate: number;
  duration_seconds: number;
  timeout_seconds: number;
  target_rps: number | null;
  thresholds: LoadThresholds;
}

export interface LoadTest extends LoadTestPayload {
  id: string;
  project_id: string;
  target_type: "URL" | "API_REQUEST";
  environment_name: string;
  environment_classification: EnvironmentClassification;
  status: LoadTestStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface LoadMetric {
  id: string; timestamp: string; active_users: number; requests_per_second: number;
  failure_rate: number; avg_response_time: number; p50: number; p90: number;
  p95: number; p99: number; total_requests: number; failed_requests: number;
}

export interface EndpointMetric {
  id: string; method: string; path: string; request_count: number; failure_count: number;
  rps: number; avg_response_time: number; min_response_time: number; max_response_time: number;
  p50: number; p90: number; p95: number; p99: number;
}

export interface LoadErrorMetric {
  id: string; method: string; path: string; error_type: string; status_code: number | null;
  message: string; count: number;
}

export interface ThresholdResult { key: string; label: string; passed: boolean; measured: number; threshold: number; operator: string; unit: string; }

export interface LoadRun {
  id: string; load_test_id: string; project_id: string; run_number: number; run_key: string;
  load_test_name: string; status: LoadTestStatus; result_status: LoadTestResultStatus | null;
  started_at: string | null; completed_at: string | null; virtual_users: number; spawn_rate: number;
  duration_seconds: number; total_requests: number; successful_requests: number; failed_requests: number;
  requests_per_second: number; failure_rate: number; avg_response_time: number; min_response_time: number;
  max_response_time: number; median_response_time: number; p50_response_time: number;
  p75_response_time: number; p90_response_time: number; p95_response_time: number;
  p99_response_time: number; status_distribution: Record<string, number>; error_summary: Record<string, number>;
  threshold_results: ThresholdResult[]; config_snapshot: Record<string, unknown>; is_baseline: boolean;
  error_message: string | null; created_by: string; created_at: string;
}

export interface LoadRunDetail extends LoadRun { metrics: LoadMetric[]; endpoints: EndpointMetric[]; errors: LoadErrorMetric[]; }
export interface PaginatedLoadRuns { items: LoadRun[]; page: number; page_size: number; total: number; total_pages: number; }
export interface AllowlistSettings { enabled: boolean; allowed_hosts: string[]; }
export interface LoadComparison { run_a: LoadRun; run_b: LoadRun; metrics: { metric: string; run_a: number; run_b: number; difference: number; percent_change: number | null }[]; }
