import { DuesPage } from "@/pages/shared/Dues";

/** Monthly bill generation is Admin-only (Section 13.2) — everything else
 * on this page (approve/reject/correct) is open to Sub-admin, scoped to
 * their Wing/Row by the API. */
export function SubAdminDues() {
  return <DuesPage canGenerateBills={false} />;
}
