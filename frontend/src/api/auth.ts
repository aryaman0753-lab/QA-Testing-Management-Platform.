import { apiClient } from "./client";
import type { AuthResponse, User } from "../types";

export function login(email: string, password: string) {
  return apiClient.post<AuthResponse>("/auth/login", { email, password });
}

export function register(full_name: string, email: string, password: string) {
  return apiClient.post<AuthResponse>("/auth/register", { full_name, email, password });
}

export function fetchCurrentUser() {
  return apiClient.get<User>("/auth/me");
}
