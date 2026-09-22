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

export const visitorsApi = {
  preApprove: (input: VisitorPreApproveInput) => apiClient.post<VisitorOut>("/visitors", input),
  mine: (skip = 0, limit = 20) =>
    apiClient.get<Page<VisitorOut>>("/visitors/mine", { params: { skip, limit } }),
  updateStatus: (id: string, status: Extract<VisitorStatus, "EXPECTED" | "CANCELLED">) =>
    apiClient.patch<VisitorOut>(`/visitors/${id}/status`, null, { params: { new_status: status } }),
};
