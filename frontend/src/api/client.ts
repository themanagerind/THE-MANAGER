/**
 * API client — base URL /api/v1 (docs/API_CONTRACT.md), Bearer auth,
 * single-flight refresh on 401 (the backend's refresh token is single-use
 * via atomic GETDEL rotation — if two requests 401 at once, only ONE
 * refresh call may fire, or the second consumes a token the first already
 * used and fails).
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { tokenStorage } from "@/auth/tokenStorage";
import type { Role } from "@/types/enums";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Audit finding: the old check (`!url?.includes("/auth/")`) excluded every
// auth-prefixed URL from the retry-on-401 path, including /auth/me — an
// authenticated, protected endpoint that the bootstrap effect (AuthContext.tsx)
// calls on every app load/reload and genuinely needs refreshed on a merely-
// expired (not revoked) access token, same as any other protected endpoint.
// Its own comment said "401 -> the axios interceptor tries a refresh", which
// the blanket exclusion silently made untrue — every reload more than
// ~30 minutes after login was forcing a full re-login despite a perfectly
// valid 30-day refresh token. Only exclude endpoints retry would be wrong
// for: unauthenticated calls where 401 means "wrong OTP/session", not
// "expired token" (otp/request, otp/verify, select-account), and logout
// (if it 401s because the token's already revoked, the user is logging out
// anyway — retrying serves nothing).
export const NO_REFRESH_RETRY_PATHS = new Set([
  "/auth/token/refresh",
  "/auth/otp/request",
  "/auth/otp/verify",
  "/auth/select-account",
  "/auth/logout",
]);

/** Pure helper (exported for testing): /auth/switch-role carries a
 * single-use refresh_token in its own body (so the backend can revoke the
 * pre-switch token instead of orphaning it) — the one captured in a
 * retried request is stale/already-consumed by the refresh call that
 * preceded the retry, so it must be swapped for the freshly-rotated one
 * before replay, or the retry always fails with "refresh token already
 * used" (the same token can't be consumed twice). Returns `data`
 * unchanged for anything that isn't a JSON object with that key. */
export function patchRefreshTokenInBody(data: unknown, newRefreshToken: string | null): unknown {
  if (typeof data !== "string") return data;
  try {
    const parsed = JSON.parse(data) as Record<string, unknown>;
    if (parsed && typeof parsed === "object" && "refresh_token" in parsed) {
      parsed.refresh_token = newRefreshToken;
      return JSON.stringify(parsed);
    }
  } catch {
    // Body wasn't JSON — nothing to patch.
  }
  return data;
}

let refreshPromise: Promise<string> | null = null;

async function performRefresh(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token");

  const { data } = await axios.post(`${API_BASE_URL}/auth/token/refresh`, { refresh_token: refreshToken });
  tokenStorage.setTokens(data.access_token, data.refresh_token, data.active_role as Role, data.available_roles as Role[]);
  return data.access_token as string;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

    if (
      error.response?.status === 401 &&
      !originalRequest._retried &&
      !NO_REFRESH_RETRY_PATHS.has(originalRequest.url ?? "")
    ) {
      originalRequest._retried = true;
      try {
        // Single-flight: concurrent 401s all await the SAME in-flight
        // refresh call instead of each trying (and racing against) their
        // own — the backend would only let one of several simultaneous
        // refresh calls succeed anyway.
        if (!refreshPromise) {
          refreshPromise = performRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const newAccessToken = await refreshPromise;
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        originalRequest.data = patchRefreshTokenInBody(originalRequest.data, tokenStorage.getRefreshToken());
        return apiClient(originalRequest);
      } catch {
        tokenStorage.clear();
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);
