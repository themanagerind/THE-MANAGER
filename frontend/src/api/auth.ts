import { apiClient } from "@/api/client";
import type { Role } from "@/types/enums";

export interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
  active_role: Role;
  available_roles: Role[];
}

export interface AccountChoice {
  user_id: string;
  society_id: string | null;
  society_name: string | null;
  full_name: string;
  roles: Role[];
}

export interface OTPVerifyOut {
  tokens: TokenOut | null;
  accounts: AccountChoice[] | null;
  otp_session_token: string | null;
}

export interface CurrentUserOut {
  user_id: string;
  society_id: string | null;
  active_role: Role;
  /** Re-derived from the DB on every request (see app/core/security.py
   * get_current_user) — never a stale snapshot from token-issue time. */
  available_roles: Role[];
}

export const authApi = {
  requestOtp: (mobile: string) =>
    apiClient.post<{ message: string; dev_otp?: string | null }>("/auth/otp/request", { mobile }),

  verifyOtp: (mobile: string, otp: string) =>
    apiClient.post<OTPVerifyOut>("/auth/otp/verify", { mobile, otp }),

  selectAccount: (otpSessionToken: string, userId: string) =>
    apiClient.post<TokenOut>("/auth/select-account", { otp_session_token: otpSessionToken, user_id: userId }),

  switchRole: (activeRole: Role) => apiClient.post<TokenOut>("/auth/switch-role", { active_role: activeRole }),

  refresh: (refreshToken: string) =>
    apiClient.post<TokenOut>("/auth/token/refresh", { refresh_token: refreshToken }),

  logout: (refreshToken: string) => apiClient.post("/auth/logout", { refresh_token: refreshToken }),

  me: () => apiClient.get<CurrentUserOut>("/auth/me"),
};
