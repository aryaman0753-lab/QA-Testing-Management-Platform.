import { apiClient } from "./client";
import type { User } from "../types";

export function listUsers() {
  return apiClient.get<User[]>("/users");
}

export function getUser(userId: string) {
  return apiClient.get<User>(`/users/${userId}`);
}
