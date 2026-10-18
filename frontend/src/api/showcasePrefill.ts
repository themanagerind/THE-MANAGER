import { apiClient } from "@/api/client";

export interface PrefillTokenOut {
  token: string;
  expires_at: string;
}

export const showcasePrefillApi = {
  /** Issues a short-lived, single-use, opaque token (no personal data
   * inside it — see backend's ShowcasePrefillToken docstring) that
   * Showcase's own backend redeems server-to-server to prefill its signup
   * form. Call only right after the Resident has seen and accepted the
   * consent notice (see ShopNowButton). */
  create: () => apiClient.post<PrefillTokenOut>("/showcase-prefill"),
};
