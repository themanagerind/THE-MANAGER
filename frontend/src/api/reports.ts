import { apiClient } from "@/api/client";
import type { BalanceSummary } from "@/api/accountEntries";
import type { ComplaintStatus } from "@/types/enums";

/** Admin: society-wide. Sub-admin: their assigned Wing/Row scope only.
 * Resident: their own linked propert(y/ies) only. */
export interface MaintenanceSummaryOut {
  properties_count: number;
  total_billed: number;
  total_collected: number;
  total_pending: number;
  overdue_count: number;
  total_overdue_amount: number;
  collection_rate_percent: number;
}

/** Same society-wide view for every role — a Manager isn't scoped to a
 * Wing/Row the way a Sub-admin is, so there's no narrower cut of this. */
export interface ManagerPerformanceOut {
  manager_id: string;
  manager_name: string;
  tasks_total: number;
  tasks_completed: number;
  complaints_assigned: number;
  complaints_resolved: number;
  average_rating: number | null;
  ratings_count: number;
}

/** Resident: only their own resolved complaints. Sub-admin: any
 * resolved complaint within their assigned Wing/Row scope, plus any
 * they raised themselves (a Sub-admin is a promoted Resident and
 * keeps that dual identity) — resident_id/resident_name is who raised
 * it, which may not be the caller. */
export interface ComplaintForRatingOut {
  complaint_id: string;
  title: string;
  category: string;
  status: ComplaintStatus;
  created_at: string;
  resident_id: string;
  resident_name: string;
  resolved_manager_id: string | null;
  resolved_manager_name: string | null;
  rating: number | null;
  rated_at: string | null;
}

/** Platform Owner's per-society headcount — a society has exactly one
 * active Admin, so admin_name/admin_mobile is a single identity. */
export interface SocietyPeopleOverviewOut {
  admin_name: string | null;
  admin_mobile: string | null;
  sub_admin_count: number;
  manager_count: number;
  security_guard_count: number;
  resident_count: number;
}

export const reportsApi = {
  maintenanceSummary: () => apiClient.get<MaintenanceSummaryOut>("/reports/maintenance-summary"),
  managerPerformance: () => apiClient.get<ManagerPerformanceOut[]>("/reports/manager-performance"),
  rateableComplaints: () => apiClient.get<ComplaintForRatingOut[]>("/reports/rateable-complaints"),

  // --- Platform Owner: any one society, picked by id ---
  platformOverview: (societyId: string) =>
    apiClient.get<SocietyPeopleOverviewOut>(`/reports/platform/${societyId}/overview`),
  platformMaintenanceSummary: (societyId: string) =>
    apiClient.get<MaintenanceSummaryOut>(`/reports/platform/${societyId}/maintenance-summary`),
  platformManagerPerformance: (societyId: string) =>
    apiClient.get<ManagerPerformanceOut[]>(`/reports/platform/${societyId}/manager-performance`),
  platformBalance: (societyId: string) =>
    apiClient.get<BalanceSummary>(`/reports/platform/${societyId}/balance`),
};
