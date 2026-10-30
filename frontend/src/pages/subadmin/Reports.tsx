import { ReportsPage } from "@/pages/shared/Reports";

export function SubAdminReports() {
  // A Sub-admin can rate any resolved complaint within their assigned
  // Wing/Row scope, or one they raised themselves — the backend enforces
  // which (complaint_service.rate_complaint).
  return <ReportsPage showRatingSection />;
}
