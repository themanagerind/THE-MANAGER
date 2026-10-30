import { apiClient } from "@/api/client";
import type { Role, UserStatus } from "@/types/enums";

export interface UserProfileOut {
  id: string;
  society_id: string | null;
  full_name: string;
  mobile: string;
  email: string | null;
  status: UserStatus;
  roles: Role[];
  created_at: string;
  has_avatar: boolean;
}

export const usersApi = {
  /** Self-service profile, same for every role — mobile is read-only
   * here (OTP login identity, uniqueness-constrained). */
  me: () => apiClient.get<UserProfileOut>("/users/me"),
  updateProfile: (fullName: string, email?: string) =>
    apiClient.patch<UserProfileOut>("/users/me", { full_name: fullName, email }),
  /** Resident/Admin/Sub-admin only (backend 403s everyone else) — replaces
   * the sidebar's default logo with this photo. Fetch the bytes back via
   * AuthenticatedImage pointed at "/users/me/avatar". */
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<UserProfileOut>("/users/me/avatar", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  removeAvatar: () => apiClient.delete<UserProfileOut>("/users/me/avatar"),
};
