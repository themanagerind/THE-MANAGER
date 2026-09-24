import { apiClient } from "@/api/client";
import type { RoleRequestStatus } from "@/types/enums";

export interface AdminChangeRequestOut {
  id: string;
  society_id: string;
  old_admin_id: string;
  new_admin_full_name: string;
  new_admin_mobile: string;
  new_admin_email: string | null;
  status: RoleRequestStatus;
  initiated_by: string;
  new_admin_id: string | null;
  created_at: string;
  decided_at: string | null;
  approvals_total: number;
  approvals_done: number;
}

export interface PendingAdminChangeApprovalOut {
  approval_id: string;
  request_id: string;
  society_id: string;
  new_admin_full_name: string;
  new_admin_mobile: string;
  created_at: string;
}

export const adminChangeApi = {
  /** Platform Owner-only — replaces a society's Admin (Section: at most
   * one active Admin per society). Finalizes immediately if the society
   * has no Sub-admin; otherwise stays PENDING until every Sub-admin has
   * approved (a single reject cancels the whole request). */
  create: (societyId: string, fullName: string, mobile: string, email?: string) =>
    apiClient.post<AdminChangeRequestOut>("/admin-change-requests", {
      society_id: societyId, new_admin_full_name: fullName, new_admin_mobile: mobile, new_admin_email: email,
    }),
  /** Platform Owner-only — every request across every society, newest
   * first, so they can track progress after creating one. */
  list: () => apiClient.get<AdminChangeRequestOut[]>("/admin-change-requests"),
  /** Sub-admin-only — requests awaiting THIS Sub-admin's own decision. */
  pendingForMe: () => apiClient.get<PendingAdminChangeApprovalOut[]>("/admin-change-requests/pending-for-me"),
  decide: (requestId: string, approve: boolean) =>
    apiClient.post<AdminChangeRequestOut>(`/admin-change-requests/${requestId}/decision`, { approve }),
};
