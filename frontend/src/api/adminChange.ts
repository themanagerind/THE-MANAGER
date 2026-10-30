import { apiClient } from "@/api/client";
import type { Role, RoleRequestStatus } from "@/types/enums";

export interface AdminChangeRequestOut {
  id: string;
  society_id: string;
  old_admin_id: string;
  new_admin_full_name: string;
  new_admin_mobile: string;
  new_admin_email: string | null;
  new_admin_user_id: string | null;
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

export interface ResignationCandidateOut {
  id: string;
  full_name: string;
  mobile: string;
  role_label: "RESIDENT" | "SUB_ADMIN";
  house_number: string | null;
  floor_number: number | null;
  location_id: string | null;
  location_name: string | null;
}

export interface RoleHistoryOut {
  id: string;
  full_name: string;
  mobile: string;
  role: Role;
  assigned_at: string;
  revoked_at: string | null;
}

export const adminChangeApi = {
  /** Platform Owner-only — replaces a society's Admin, either with an
   * existing Resident/Sub-admin (pass newAdminUserId — the normal path,
   * picked from candidates() below) or a brand-new outside person (pass
   * fullName/mobile/email instead; leave newAdminUserId undefined).
   * Finalizes immediately if the society has no Sub-admin; otherwise
   * stays PENDING until every Sub-admin has approved (a single reject
   * cancels the whole request). */
  create: (
    societyId: string,
    opts: { newAdminUserId: string } | { fullName: string; mobile: string; email?: string }
  ) =>
    apiClient.post<AdminChangeRequestOut>("/admin-change-requests", {
      society_id: societyId,
      ...("newAdminUserId" in opts
        ? { new_admin_user_id: opts.newAdminUserId }
        : { new_admin_full_name: opts.fullName, new_admin_mobile: opts.mobile, new_admin_email: opts.email }),
    }),
  /** Platform Owner-only — every request across every society, newest
   * first, so they can track progress after creating one. */
  list: () => apiClient.get<AdminChangeRequestOut[]>("/admin-change-requests"),
  /** Sub-admin-only — requests awaiting THIS Sub-admin's own decision. */
  pendingForMe: () => apiClient.get<PendingAdminChangeApprovalOut[]>("/admin-change-requests/pending-for-me"),
  decide: (requestId: string, approve: boolean) =>
    apiClient.post<AdminChangeRequestOut>(`/admin-change-requests/${requestId}/decision`, { approve }),
  /** Admin-only — every active Resident/Sub-admin in their own society
   * they could hand the role to (self excluded), optionally narrowed to
   * one Wing/Row. */
  resignationCandidates: (locationId?: string) =>
    apiClient.get<ResignationCandidateOut[]>("/admin-change-requests/resignation-candidates", {
      params: { location_id: locationId },
    }),
  /** Platform Owner-only — every active Resident/Sub-admin in the chosen
   * society, optionally narrowed to one Wing/Row — the Change Admin
   * picker, instead of typing a new person's details by hand. */
  candidates: (societyId: string, locationId?: string) =>
    apiClient.get<ResignationCandidateOut[]>("/admin-change-requests/candidates", {
      params: { society_id: societyId, location_id: locationId },
    }),
  /** Admin-only — resigns and picks an existing Resident/Sub-admin as
   * their successor. Same unanimous-Sub-admin-approval rule as create()
   * above; society_id/old_admin_id are inferred from the caller. */
  resign: (newAdminUserId: string) =>
    apiClient.post<AdminChangeRequestOut>("/admin-change-requests/resign", { new_admin_user_id: newAdminUserId }),
  /** Every ADMIN/SUB_ADMIN role period this society has ever had, newest
   * first — Admin/Sub-admin see their own society automatically; Platform
   * Owner must pass societyId. */
  history: (societyId?: string) =>
    apiClient.get<RoleHistoryOut[]>("/admin-change-requests/history", { params: { society_id: societyId } }),
};
