export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD" | "OPTIONS";
export type BodyType = "NONE" | "JSON" | "FORM_URLENCODED" | "MULTIPART_FORM_DATA" | "RAW";
export type AuthenticationType = "NONE" | "BEARER" | "BASIC" | "API_KEY";
export type ExecutionStatus = "RUNNING" | "PASS" | "FAIL" | "TIMEOUT" | "ERROR";
export type AssertionType = "STATUS_CODE" | "RESPONSE_TIME" | "BODY_CONTAINS" | "JSON_PATH" | "HEADER_EXISTS" | "HEADER_EQUALS" | "JSON_VALUE_EQUALS" | "JSON_VALUE_CONTAINS";
export type AssertionOperator = "EQUALS" | "NOT_EQUALS" | "LESS_THAN" | "GREATER_THAN" | "CONTAINS" | "NOT_CONTAINS" | "EXISTS" | "NOT_EXISTS";

export interface KeyValueItem { key: string; value: string; enabled: boolean; }
export interface ApiAssertion { id?: string; assertion_type: AssertionType; operator: AssertionOperator; target?: string | null; expected_value?: string | null; enabled: boolean; position?: number; }
export interface ApiExtractor { id?: string; source: "JSON_PATH" | "RESPONSE_HEADER"; path: string; variable_name: string; enabled: boolean; position?: number; }
export interface ApiRequestPayload {
  name: string; description?: string | null; method: HttpMethod; url: string;
  headers: KeyValueItem[]; query_parameters: KeyValueItem[]; body?: string | null;
  body_type: BodyType; authentication_type: AuthenticationType;
  authentication_config: Record<string, string>; assertions: ApiAssertion[];
  extractors: ApiExtractor[]; position: number;
}
export interface ApiRequest extends ApiRequestPayload { id: string; project_id: string; collection_id: string; created_by: string; created_at: string; updated_at: string; }
export interface ApiCollection { id: string; project_id: string; name: string; description: string | null; created_by: string; created_at: string; updated_at: string; request_count: number; requests?: ApiRequest[]; }
export interface EnvironmentVariable { name: string; value: string; is_secret: boolean; }
export interface ApiEnvironment { id: string; project_id: string; name: string; classification: "DEVELOPMENT" | "TEST" | "QA" | "STAGING" | "PRODUCTION"; variables: EnvironmentVariable[]; created_by: string; created_at: string; updated_at: string; }
export interface AssertionResult { assertion_type: string; passed: boolean; description: string; expected: string | null; actual: string | null; }
export interface ApiTestResult {
  id: string; test_run_id: string; request_id: string; request_name: string; method: string;
  resolved_url: string; status: ExecutionStatus; status_code: number | null;
  response_time_ms: number; response_size: number; redirects: number; content_type: string | null;
  response_headers: Record<string, string>; response_body: string | null; response_truncated: boolean;
  timing: Record<string, number>; assertion_results: AssertionResult[]; assertions_total: number;
  assertions_passed: number; assertions_failed: number; extracted_variable_names: string[];
  error_message: string | null; executed_at: string;
}
export interface ApiRun {
  id: string; project_id: string; run_number: number; run_key: string; collection_id: string | null;
  request_id: string | null; collection_name: string | null; request_name: string | null;
  status: ExecutionStatus; requests_total: number; requests_passed: number; requests_failed: number;
  duration_ms: number; created_by: string; created_at: string; completed_at: string | null;
  results?: ApiTestResult[];
}
export interface PaginatedRuns { items: ApiRun[]; page: number; page_size: number; total: number; total_pages: number; }
export interface ApiAnalytics { total_api_requests: number; total_runs: number; pass_rate: number; failure_rate: number; average_response_time_ms: number; slowest_endpoint: string | null; }
export interface HealthCheckResult { status: ExecutionStatus; status_code: number | null; response_time_ms: number; response_size: number; redirects: number; content_type: string | null; error_message: string | null; assertions: AssertionResult[]; }
