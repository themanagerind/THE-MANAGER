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

export const apiClient = axios.create({
  baseURL: "/api/v1",
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

async function performRefresh(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token");

  const { data } = await axios.post("/api/v1/auth/token/refresh", { refresh_token: refreshToken });
  tokenStorage.setTokens(data.access_token, data.refresh_token, data.active_role as Role, data.available_roles as Role[]);
  return data.access_token as string;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

    if (error.response?.status === 401 && !originalRequest._retried && !originalRequest.url?.includes("/auth/")) {
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
