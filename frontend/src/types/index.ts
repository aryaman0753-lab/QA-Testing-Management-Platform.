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
