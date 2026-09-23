import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { managerTodosApi } from "@/api/managerTodos";
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

/** Same stat-card layout as Admin/Sub-admin Overview — To-Do count,
 * Complaint count, and links to the two modules plus Dues. Manager's
 * finance visibility stops at property-level maintenance dues (no
 * account-entries/balance access — see backend/app/api/v1/
 * account_entries.py), so there's no balance stat here. */
export function ManagerOverview() {
  const todosQuery = useQuery({
    queryKey: ["manager", "todos", "overview"],
    queryFn: () => managerTodosApi.list(0, 100).then((r) => r.data),
  });
  const complaintsQuery = useQuery({
    queryKey: ["manager", "complaints"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });

  const loading = todosQuery.isLoading || complaintsQuery.isLoading;
  const openTodos = (todosQuery.data?.items ?? []).filter((t) => t.status !== "DONE").length;
  const openComplaints = (complaintsQuery.data ?? []).filter(
    (c) => c.status === "OPEN" || c.status === "IN_PROGRESS"
  ).length;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Overview</h1>

      {loading ? (
        <Loader />
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="Open to-dos" value={openTodos} to="/manager/todos" />
          <StatCard label="Open complaints" value={openComplaints} to="/manager/complaints" />
          <StatCard label="Maintenance dues" value="→" to="/manager/dues" />
        </div>
      )}
    </div>
  );
}
