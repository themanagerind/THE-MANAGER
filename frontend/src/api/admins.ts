import { apiClient } from "@/api/client";
import type { UserStatus } from "@/types/enums";

export interface AdminOut {
  id: string;
  society_id: string | null;
  full_name: string;
  mobile: string;
  email: string | null;
  status: UserStatus;
  created_at: string;
}

export const adminsApi = {
  /** Public — no auth required. Targets an EXISTING, ACTIVE society
   * (created by the Platform Owner) and waits for Platform Owner
   * approval — unlike Resident signup, which the society's own Admin
   * approves. */
  signup: (input: { full_name: string; mobile: string; email?: string; society_id: string }) =>
    apiClient.post<AdminOut>("/admins/signup", input),
  pending: () => apiClient.get<AdminOut[]>("/admins/pending"),
  decideApproval: (id: string, approve: boolean) =>
    apiClient.post<AdminOut>(`/admins/${id}/approval`, { approve }),
};
