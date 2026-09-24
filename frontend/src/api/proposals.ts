import { apiClient } from "@/api/client";
import type { ProposalScope, ProposalStatus, Vote } from "@/types/enums";

export interface ProposalOut {
  id: string;
  society_id: string;
  scope_type: ProposalScope;
  scope_location_id: string | null;
  title: string;
  description: string;
  status: ProposalStatus;
  created_by: string;
  withdrawn_at: string | null;
  created_at: string;
}

export interface ProposalStatusDetail {
  proposal: ProposalOut;
  resident_approve_count: number;
  resident_eligible_count: number;
  resident_percent: number;
  subadmin_approve_count: number;
  subadmin_eligible_count: number;
  subadmin_percent: number;
  resident_threshold_met: boolean;
  subadmin_threshold_met: boolean;
  /** The caller's own current vote — null if they haven't voted yet. A
   * vote can be changed until the proposal closes. */
  my_vote: Vote | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const proposalsApi = {
  list: (skip = 0, limit = 20) => apiClient.get<Page<ProposalOut>>("/proposals", { params: { skip, limit } }),
  detail: (id: string) => apiClient.get<ProposalStatusDetail>(`/proposals/${id}`),
  create: (input: { scope_type: ProposalScope; scope_location_id?: string; title: string; description: string }) =>
    apiClient.post<ProposalOut>("/proposals", input),
  vote: (id: string, vote: Vote) => apiClient.post(`/proposals/${id}/vote`, { vote }),
  withdraw: (id: string) => apiClient.post<ProposalOut>(`/proposals/${id}/withdraw`),
};
