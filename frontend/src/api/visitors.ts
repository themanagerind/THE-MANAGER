import { apiClient } from "@/api/client";
import type { VisitorStatus } from "@/types/enums";

export interface VisitorOut {
  id: string;
  society_id: string;
  property_id: string;
  resident_id: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visit_date: string;
  status: VisitorStatus;
  purpose: string | null;
  created_at: string;
}

export interface VisitorPreApproveInput {
  property_id: string;
  visitor_name: string;
  visitor_mobile?: string;
  visit_date: string;
  purpose?: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

/** Section 21 data-boundary — Guard's restricted projection of a visitor:
 * no resident/payment/wallet data, just what gate security needs. */
export interface GuardVisitorOut {
  id: string;
  property_house_number: string;
  visitor_name: string;
  visitor_mobile: string | null;
  visit_date: string;
  status: VisitorStatus;
}

export const visitorsApi = {
  preApprove: (input: VisitorPreApproveInput) => apiClient.post<VisitorOut>("/visitors", input),
  mine: (skip = 0, limit = 20) =>
    apiClient.get<Page<VisitorOut>>("/visitors/mine", { params: { skip, limit } }),
  updateStatus: (id: string, status: Extract<VisitorStatus, "EXPECTED" | "CANCELLED">) =>
    apiClient.patch<VisitorOut>(`/visitors/${id}/status`, null, { params: { new_status: status } }),
  /** Admin/Sub-admin — every visitor in the society (Sub-admin scoped
   * server-side to their assigned Wing/Row). */
  list: (skip = 0, limit = 20) => apiClient.get<Page<VisitorOut>>("/visitors", { params: { skip, limit } }),
  /** Guard's gate view — every visitor across the society, restricted
   * projection (Section 21), no pagination (list is small/live). */
  guardView: () => apiClient.get<GuardVisitorOut[]>("/visitors/guard-view"),
  /** Only valid from PRE_APPROVED/EXPECTED — backend 409s otherwise. */
  markEntry: (id: string) => apiClient.post<GuardVisitorOut>(`/visitors/${id}/entry`),
  /** Only valid from ENTERED — backend 409s otherwise. */
  markExit: (id: string) => apiClient.post<GuardVisitorOut>(`/visitors/${id}/exit`),
};
