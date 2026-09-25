import { apiClient } from "@/api/client";
import type { EntryType } from "@/types/enums";

/** Platform-global catalog of Income/Expense headings (v1.7) — Admin
 * picks one instead of free-typing a title when adding a manual entry.
 * Seeded with headings universal to Indian housing-society bookkeeping;
 * Admin can add more from the "Add entry" screen. */
export interface AccountHeadingOut {
  id: string;
  entry_type: EntryType;
  title: string;
  created_by: string | null;
  created_at: string;
}

export interface AccountEntryOut {
  id: string;
  society_id: string;
  entry_type: EntryType;
  source: string;
  heading_id: string | null;
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
  headings: (entryType?: EntryType) =>
    apiClient.get<AccountHeadingOut[]>("/account-entries/headings", { params: entryType ? { entry_type: entryType } : {} }),
  /** Add-only, platform-global — adding one already in the catalog just
   * returns the existing row instead of erroring. */
  addHeading: (entryType: EntryType, title: string) =>
    apiClient.post<AccountHeadingOut>("/account-entries/headings", { entry_type: entryType, title }),
  create: (input: { entry_type: EntryType; heading_id: string; description?: string; amount: number; entry_date: string }) =>
    apiClient.post<AccountEntryOut>("/account-entries", input),
  edit: (id: string, input: Partial<{ heading_id: string; description: string; amount: number; entry_date: string }>) =>
    apiClient.patch<AccountEntryOut>(`/account-entries/${id}`, input),
};
