import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "@/api/payments";
import { complaintsApi } from "@/api/complaints";
import { adminChangeApi, type PendingAdminChangeApprovalOut } from "@/api/adminChange";
import { Loader, apiErrorMessage } from "@/components/States";
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

/** Same stat-card layout as AdminOverview, scoped to what a Sub-admin
 * actually has: Dues, Complaints, Proposals, Expenses — no Residents,
 * Properties, Notices, Amenities, Visitors or Accounts (Admin-only). */
export function SubAdminOverview() {
  const queryClient = useQueryClient();
  const pendingPayments = useQuery({
    queryKey: ["dues", "payments", "pending"],
    queryFn: () => paymentsApi.pending().then((r) => r.data),
  });
  const complaints = useQuery({
    queryKey: ["subadmin", "complaints"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });
  const adminChangeQueryKey = ["subadmin", "admin-change-requests", "pending-for-me"];
  const adminChangeApprovals = useQuery({
    queryKey: adminChangeQueryKey,
    queryFn: () => adminChangeApi.pendingForMe().then((r) => r.data),
  });

  const decide = useMutation({
    mutationFn: ({ requestId, approve }: { requestId: string; approve: boolean }) =>
      adminChangeApi.decide(requestId, approve),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: adminChangeQueryKey }),
  });

  const loading = pendingPayments.isLoading || complaints.isLoading;
  const openComplaints = complaints.data?.filter((c) => c.status === "OPEN").length ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Overview</h1>

      {adminChangeApprovals.data && adminChangeApprovals.data.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-navy-muted">Admin change approvals</h2>
          <ul className="space-y-2">
            {adminChangeApprovals.data.map((a: PendingAdminChangeApprovalOut) => (
              <li key={a.approval_id} className="border border-line rounded p-4 bg-white space-y-2">
                <p className="text-sm text-ink">
                  The Platform Owner wants to make <span className="font-medium">{a.new_admin_full_name}</span> (
                  {a.new_admin_mobile}) the new Admin of your society.
                </p>
                {decide.isError && decide.variables?.requestId === a.request_id && (
                  <p className="text-xs text-danger">
                    {apiErrorMessage(decide.error, "Could not record your decision.")}
                  </p>
                )}
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="secondary"
                    loading={decide.isPending && decide.variables?.requestId === a.request_id && !decide.variables?.approve}
                    onClick={() => decide.mutate({ requestId: a.request_id, approve: false })}
                  >
                    Reject
                  </Button>
                  <Button
                    loading={decide.isPending && decide.variables?.requestId === a.request_id && decide.variables?.approve}
                    onClick={() => decide.mutate({ requestId: a.request_id, approve: true })}
                  >
                    Approve
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

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
