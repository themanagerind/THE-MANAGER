import { apiClient } from "@/api/client";
import type { Decision, ExpenseBillStatus } from "@/types/enums";

export interface ExpenseBillOut {
  id: string;
  society_id: string;
  title: string;
  description: string | null;
  amount: number;
  category: string | null;
  status: ExpenseBillStatus;
  created_by: string;
  finalized_by: string | null;
  finalized_at: string | null;
  created_at: string;
}

export interface ExpenseBillStatusDetail {
  bill: ExpenseBillOut;
  approve_count: number;
  active_subadmin_count: number;
  approvals_needed: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const expenseBillsApi = {
  list: (skip = 0, limit = 20) => apiClient.get<Page<ExpenseBillOut>>("/expense-bills", { params: { skip, limit } }),
  detail: (id: string) => apiClient.get<ExpenseBillStatusDetail>(`/expense-bills/${id}`),
  createDraft: (input: { title: string; description?: string; amount: number; category?: string }) =>
    apiClient.post<ExpenseBillOut>("/expense-bills/draft", input),
  createAndFinalize: (input: { title: string; description?: string; amount: number; category?: string }) =>
    apiClient.post<ExpenseBillOut>("/expense-bills", input),
  finalize: (id: string) => apiClient.post<ExpenseBillOut>(`/expense-bills/${id}/finalize`),
  decide: (id: string, decision: Decision, reason?: string) =>
    apiClient.post(`/expense-bills/${id}/decision`, { decision, reason }),
};
