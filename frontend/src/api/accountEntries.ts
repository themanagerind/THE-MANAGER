import { apiClient } from "@/api/client";
import type { EntryType } from "@/types/enums";

export interface AccountEntryOut {
  id: string;
  society_id: string;
  entry_type: EntryType;
  source: string;
  title: string;
  description: string | null;
  amount: number;
  entry_date: string;
  is_edited: boolean;
  last_edited_at: string | null;
  created_by: string;
  created_at: string;
}

export interface BalanceSummary {
  total_income: number;
  total_expense: number;
  balance: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const accountEntriesApi = {
  list: (skip = 0, limit = 20) => apiClient.get<Page<AccountEntryOut>>("/account-entries", { params: { skip, limit } }),
  balance: () => apiClient.get<BalanceSummary>("/account-entries/balance"),
  create: (input: { entry_type: EntryType; title: string; description?: string; amount: number; entry_date: string }) =>
    apiClient.post<AccountEntryOut>("/account-entries", input),
  edit: (id: string, input: Partial<{ title: string; description: string; amount: number; entry_date: string }>) =>
    apiClient.patch<AccountEntryOut>(`/account-entries/${id}`, input),
};
