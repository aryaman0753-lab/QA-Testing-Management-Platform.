/**
 * All token persistence goes through this module. Phase 1 uses localStorage
 * for simplicity; swapping to an httpOnly-cookie-based flow later only
 * means rewriting these three functions, not every call site.
 */
const TOKEN_KEY = "qahub_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
