import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { residentsApi } from "@/api/residents";
import { paymentsApi } from "@/api/payments";
import { Loader } from "@/components/States";
import { Button } from "@/components/Button";

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

export function AdminOverview() {
  const navigate = useNavigate();
  const pendingResidents = useQuery({
    queryKey: ["admin", "residents", "pending"],
    queryFn: () => residentsApi.pending().then((r) => r.data),
  });
  const pendingPayments = useQuery({
    queryKey: ["dues", "payments", "pending"],
    queryFn: () => paymentsApi.pending().then((r) => r.data),
  });

  const loading = pendingResidents.isLoading || pendingPayments.isLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-navy">Overview</h1>
        <Button variant="danger" onClick={() => navigate("/admin/resign")}>
          Resign as Admin
        </Button>
      </div>

      {loading ? (
        <Loader />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Pending resident approvals" value={pendingResidents.data?.length ?? 0} to="/admin/residents" />
          <StatCard label="Payments awaiting approval" value={pendingPayments.data?.length ?? 0} to="/admin/dues" />
          <StatCard label="Manage properties" value="→" to="/admin/properties" />
          <StatCard label="Complaints" value="→" to="/admin/complaints" />
          <StatCard label="Notices" value="→" to="/admin/notices" />
          <StatCard label="Amenities" value="→" to="/admin/amenities" />
          <StatCard label="Proposals" value="→" to="/admin/proposals" />
          <StatCard label="Expense bills" value="→" to="/admin/expense-bills" />
          <StatCard label="Accounts" value="→" to="/admin/accounts" />
        </div>
      )}
    </div>
  );
}
