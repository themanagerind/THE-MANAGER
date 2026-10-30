import { apiClient } from "@/api/client";
import type { Role, UserStatus } from "@/types/enums";

/** Manager/Security Guard accounts — Admin creates them directly (no
 * property link, no approval wait, unlike Admin/Resident signup), since
 * both are third-party hired staff, not flat owners/tenants. */
export interface StaffOut {
  id: string;
  society_id: string;
  full_name: string;
  mobile: string;
  email: string | null;
  role: Extract<Role, "MANAGER" | "SECURITY_GUARD">;
  status: UserStatus;
  assigned_at: string;
}

export const staffApi = {
  list: () => apiClient.get<StaffOut[]>("/staff"),
  create: (input: { full_name: string; mobile: string; email?: string; role: "MANAGER" | "SECURITY_GUARD" }) =>
    apiClient.post<StaffOut>("/staff", input),
  remove: (userId: string) => apiClient.delete(`/staff/${userId}`),
};
