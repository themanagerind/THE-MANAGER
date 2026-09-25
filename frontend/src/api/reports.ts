import { apiClient } from "@/api/client";
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

export interface MyComplaintForRatingOut {
  complaint_id: string;
  title: string;
  category: string;
  status: ComplaintStatus;
  created_at: string;
  resolved_manager_id: string | null;
  resolved_manager_name: string | null;
  rating: number | null;
  rated_at: string | null;
}

export const reportsApi = {
  maintenanceSummary: () => apiClient.get<MaintenanceSummaryOut>("/reports/maintenance-summary"),
  managerPerformance: () => apiClient.get<ManagerPerformanceOut[]>("/reports/manager-performance"),
  myComplaintRatings: () => apiClient.get<MyComplaintForRatingOut[]>("/reports/my-complaint-ratings"),
};
