import { apiClient } from "@/api/client";
import type { ComplaintStatus } from "@/types/enums";

export interface ComplaintOut {
  id: string;
  society_id: string;
  property_id: string;
  resident_id: string;
  category: string;
  title: string;
  description: string;
  status: ComplaintStatus;
  created_at: string;
}

export interface ComplaintCreateInput {
  property_id: string;
  category: string;
  title: string;
  description: string;
}

export interface ComplaintRatingOut {
  id: string;
  complaint_id: string;
  rated_by: string;
  manager_id: string;
  rating: number;
  created_at: string;
}

export const complaintsApi = {
  create: (input: ComplaintCreateInput) => apiClient.post<ComplaintOut>("/complaints", input),
  list: () => apiClient.get<ComplaintOut[]>("/complaints"),
  updateStatus: (id: string, status: ComplaintStatus) =>
    apiClient.patch<ComplaintOut>(`/complaints/${id}/status`, { status }),
  assign: (id: string, assignedTo: string) =>
    apiClient.post(`/complaints/${id}/assign`, { assigned_to: assignedTo }),
  /** One-time — a Resident can only rate their own complaint; a Sub-admin
   * can rate any complaint in their assigned Wing/Row scope or one they
   * raised themselves. Only once it's RESOLVED/CLOSED, and it can never
   * be changed afterward. */
  rate: (id: string, rating: number) => apiClient.post<ComplaintRatingOut>(`/complaints/${id}/rating`, { rating }),
};
