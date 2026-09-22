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

export const complaintsApi = {
  create: (input: ComplaintCreateInput) => apiClient.post<ComplaintOut>("/complaints", input),
  list: () => apiClient.get<ComplaintOut[]>("/complaints"),
  updateStatus: (id: string, status: ComplaintStatus) =>
    apiClient.patch<ComplaintOut>(`/complaints/${id}/status`, { status }),
  assign: (id: string, assignedTo: string) =>
    apiClient.post(`/complaints/${id}/assign`, { assigned_to: assignedTo }),
};
