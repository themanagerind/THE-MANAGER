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
}

export const usersApi = {
  /** Self-service profile, same for every role — mobile is read-only
   * here (OTP login identity, uniqueness-constrained). */
  me: () => apiClient.get<UserProfileOut>("/users/me"),
  updateProfile: (fullName: string, email?: string) =>
    apiClient.patch<UserProfileOut>("/users/me", { full_name: fullName, email }),
};
