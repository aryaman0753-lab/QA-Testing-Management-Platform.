export type UserRole = "ADMIN" | "QA_ENGINEER" | "DEVELOPER" | "PROJECT_MANAGER";

export type ProjectStatus = "ACTIVE" | "ARCHIVED";

export type ProjectRole = "OWNER" | "MEMBER" | "VIEWER";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: string;
  name: string;
  key: string;
  description: string | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  project_role: ProjectRole;
  created_at: string;
  user: User;
}

export interface ApiErrorBody {
  detail: string | { msg: string; loc: (string | number)[] }[];
}

export type BugSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "TRIVIAL";
export type BugPriority = "URGENT" | "HIGH" | "MEDIUM" | "LOW";
export type BugStatus =
  | "NEW" | "ASSIGNED" | "IN_PROGRESS" | "FIXED" | "QA_VERIFICATION"
  | "VERIFIED" | "CLOSED" | "REOPENED" | "DUPLICATE" | "WONT_FIX";

export interface UserSummary {
  id: string;
  full_name: string;
  email: string;
}

export interface BugListItem {
  id: string;
  project_id: string;
  bug_number: number;
  bug_key: string;
  title: string;
  severity: BugSeverity;
  priority: BugPriority;
  status: BugStatus;
  environment: string | null;
  reported_by: string;
  assigned_to: string | null;
  reporter: UserSummary;
  assignee: UserSummary | null;
  created_at: string;
  updated_at: string;
}

export interface BugComment {
  id: string;
  bug_id: string;
  user_id: string;
  comment: string;
  created_at: string;
  updated_at: string;
  user: UserSummary;
}

export interface BugHistoryEntry {
  id: string;
  bug_id: string;
  user_id: string;
  action: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
  user: UserSummary;
}

export interface BugAttachment {
  id: string;
  bug_id: string;
  uploaded_by: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  created_at: string;
  uploader: UserSummary;
  download_url: string;
}

export interface BugDetail extends BugListItem {
  description: string;
  steps_to_reproduce: string[];
  expected_result: string | null;
  actual_result: string | null;
  browser: string | null;
  operating_system: string | null;
  device: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  project: Pick<Project, "id" | "name" | "key">;
  comments: BugComment[];
  attachments: BugAttachment[];
  history: BugHistoryEntry[];
}

export interface BugPayload {
  title: string;
  description: string;
  steps_to_reproduce: string[];
  expected_result?: string | null;
  actual_result?: string | null;
  severity: BugSeverity;
  priority: BugPriority;
  environment?: string | null;
  browser?: string | null;
  operating_system?: string | null;
  device?: string | null;
  assigned_to?: string | null;
}

export interface PaginatedBugs {
  items: BugListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface BugAnalytics {
  total: number;
  open: number;
  critical: number;
  high_priority: number;
  by_status: Record<BugStatus, number>;
  by_severity: Record<BugSeverity, number>;
  by_priority: Record<BugPriority, number>;
  created_over_time: { date: string; count: number }[];
}
