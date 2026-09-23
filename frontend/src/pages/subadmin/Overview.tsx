import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { paymentsApi } from "@/api/payments";
import { complaintsApi } from "@/api/complaints";
import { Loader } from "@/components/States";

function StatCard({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Link
      to={to}
      className="block border border-line rounded p-4 hover:border-navy transition-colors bg-white"
    >
      <p className="text-2xl font-semibold text-navy">{value}</p>
      <p className="text-sm text-navy-muted mt-1">{label}</p>
    </Link>
  );
}

/** Same stat-card layout as AdminOverview, scoped to what a Sub-admin
 * actually has: Dues, Complaints, Proposals, Expenses — no Residents,
 * Properties, Notices, Amenities, Visitors or Accounts (Admin-only). */
export function SubAdminOverview() {
  const pendingPayments = useQuery({
    queryKey: ["dues", "payments", "pending"],
    queryFn: () => paymentsApi.pending().then((r) => r.data),
  });
  const complaints = useQuery({
    queryKey: ["subadmin", "complaints"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });

  const loading = pendingPayments.isLoading || complaints.isLoading;
  const openComplaints = complaints.data?.filter((c) => c.status === "OPEN").length ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Overview</h1>

      {loading ? (
        <Loader />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Payments awaiting approval" value={pendingPayments.data?.length ?? 0} to="/subadmin/dues" />
          <StatCard label="Open complaints" value={openComplaints} to="/subadmin/complaints" />
          <StatCard label="Proposals" value="→" to="/subadmin/proposals" />
          <StatCard label="Expense bills" value="→" to="/subadmin/expense-bills" />
        </div>
      )}
    </div>
  );
}
