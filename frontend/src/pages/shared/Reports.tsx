import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reportsApi, type ManagerPerformanceOut, type MyComplaintForRatingOut } from "@/api/reports";
import { complaintsApi } from "@/api/complaints";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-line rounded p-4 bg-white">
      <p className="text-2xl font-semibold text-navy">{value}</p>
      <p className="text-sm text-navy-muted mt-1">{label}</p>
    </div>
  );
}

/**
 * Shared by Admin, Sub-admin and Resident — Monthly Maintenance and
 * Manager Performance are scoped correctly per role server-side
 * (Admin: society-wide, Sub-admin: their Wing/Row, Resident: their own
 * property), so this page just renders whatever comes back. Only a
 * Resident can rate a Manager (showRatingSection), since only they can
 * have raised the complaint being rated. More report sections get added
 * here as they come up — this is meant to stay the one place they live.
 */
export function ReportsPage({ showRatingSection }: { showRatingSection: boolean }) {
  const maintenanceQuery = useQuery({
    queryKey: ["reports", "maintenance-summary"],
    queryFn: () => reportsApi.maintenanceSummary().then((r) => r.data),
  });
  const managerQuery = useQuery({
    queryKey: ["reports", "manager-performance"],
    queryFn: () => reportsApi.managerPerformance().then((r) => r.data),
  });

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-navy">Reports</h1>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-navy-muted">Monthly Maintenance</h2>
        {maintenanceQuery.isLoading && <Loader />}
        {maintenanceQuery.isError && (
          <ErrorState message="Couldn't load the maintenance report." onRetry={() => maintenanceQuery.refetch()} />
        )}
        {maintenanceQuery.data && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <StatTile label="Total billed" value={`₹${maintenanceQuery.data.total_billed.toLocaleString("en-IN")}`} />
            <StatTile label="Collected" value={`₹${maintenanceQuery.data.total_collected.toLocaleString("en-IN")}`} />
            <StatTile label="Pending" value={`₹${maintenanceQuery.data.total_pending.toLocaleString("en-IN")}`} />
            <StatTile
              label="Overdue (with penalty)"
              value={`₹${maintenanceQuery.data.total_overdue_amount.toLocaleString("en-IN")} (${maintenanceQuery.data.overdue_count})`}
            />
            <StatTile label="Collection rate" value={`${maintenanceQuery.data.collection_rate_percent}%`} />
            <StatTile label="Properties billed" value={maintenanceQuery.data.properties_count} />
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-navy-muted">Manager Performance</h2>
        {managerQuery.isLoading && <Loader />}
        {managerQuery.isError && (
          <ErrorState message="Couldn't load Manager performance." onRetry={() => managerQuery.refetch()} />
        )}
        {managerQuery.data && managerQuery.data.length === 0 && <EmptyState title="No Managers yet" />}
        {managerQuery.data && managerQuery.data.length > 0 && (
          <Table<ManagerPerformanceOut>
            keyFor={(m) => m.manager_id}
            columns={[
              { header: "Manager", render: (m) => m.manager_name },
              { header: "Daily tasks done", render: (m) => `${m.tasks_completed} / ${m.tasks_total}` },
              { header: "Complaints resolved", render: (m) => `${m.complaints_resolved} / ${m.complaints_assigned}` },
              {
                header: "Rating",
                render: (m) =>
                  m.average_rating != null ? `★ ${m.average_rating.toFixed(1)} (${m.ratings_count})` : "Not rated yet",
              },
            ]}
            rows={managerQuery.data}
          />
        )}
      </section>

      {showRatingSection && <MyComplaintRatings />}
    </div>
  );
}

function StarPicker({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          className={`text-xl leading-none ${n <= value ? "text-amber-500" : "text-line"}`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function MyComplaintRatings() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["reports", "my-complaint-ratings"],
    queryFn: () => reportsApi.myComplaintRatings().then((r) => r.data),
  });

  const submit = useMutation({
    mutationFn: ({ complaintId, rating }: { complaintId: string; rating: number }) =>
      complaintsApi.rate(complaintId, rating),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["reports", "my-complaint-ratings"] });
      void queryClient.invalidateQueries({ queryKey: ["reports", "manager-performance"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't submit your rating.")),
  });

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-navy-muted">Rate your resolved complaints</h2>
      <p className="text-xs text-navy-muted">
        Once you submit a rating for a complaint it's final and can't be changed — it feeds the Manager's
        performance record above.
      </p>
      {error && <p className="text-sm text-danger">{error}</p>}
      {query.isLoading && <Loader />}
      {query.isError && <ErrorState message="Couldn't load your complaints." onRetry={() => query.refetch()} />}
      {query.data && query.data.length === 0 && (
        <EmptyState title="Nothing to rate yet" description="Once a complaint you raised is resolved, it'll show up here." />
      )}
      {query.data && query.data.length > 0 && (
        <Table<MyComplaintForRatingOut>
          keyFor={(c) => c.complaint_id}
          columns={[
            { header: "Complaint", render: (c) => c.title },
            { header: "Manager", render: (c) => c.resolved_manager_name ?? "—" },
            {
              header: "Your rating",
              render: (c) => {
                if (c.rating != null) return <span className="text-amber-500">{"★".repeat(c.rating)}</span>;
                if (!c.resolved_manager_id) return <span className="text-xs text-navy-muted">Not assigned to a Manager</span>;
                const draft = drafts[c.complaint_id] ?? 0;
                return (
                  <div className="flex items-center gap-3">
                    <StarPicker value={draft} onChange={(n) => setDrafts((prev) => ({ ...prev, [c.complaint_id]: n }))} />
                    <Button
                      variant="secondary"
                      loading={submit.isPending && submit.variables?.complaintId === c.complaint_id}
                      disabled={!draft}
                      onClick={() => submit.mutate({ complaintId: c.complaint_id, rating: draft })}
                    >
                      Submit
                    </Button>
                  </div>
                );
              },
            },
          ]}
          rows={query.data}
        />
      )}
    </section>
  );
}
