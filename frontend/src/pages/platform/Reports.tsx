import { useState } from "react";
import { societiesApi, type SocietyReportOut } from "@/api/societies";
import { reportsApi, type ManagerPerformanceOut } from "@/api/reports";
import { useQuery } from "@tanstack/react-query";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-line rounded p-4 bg-white">
      <p className="text-2xl font-semibold text-navy">{value}</p>
      <p className="text-sm text-navy-muted mt-1">{label}</p>
    </div>
  );
}

/**
 * Platform Owner reporting dashboard — the existing per-society summary
 * table (flats/houses, Residents, Admin contact), plus a pick-a-society
 * drill-down: people headcount across every role, Monthly Maintenance,
 * Manager Performance, and Income/Expense balance for that one society.
 * Reuses the exact same report endpoints Admin/Sub-admin/Resident use
 * (see pages/shared/Reports.tsx) — just parameterized by an explicit
 * society_id since a Platform Owner has none of their own.
 */
export function PlatformReports() {
  const [selectedSocietyId, setSelectedSocietyId] = useState("");

  const reportsQuery = useQuery({
    queryKey: ["platform", "societies", "reports"],
    queryFn: () => societiesApi.reports().then((r) => r.data),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-navy">Society reports</h1>

        {reportsQuery.isLoading && <Loader />}
        {reportsQuery.isError && (
          <ErrorState message="Couldn't load reports." onRetry={() => reportsQuery.refetch()} />
        )}
        {reportsQuery.data && reportsQuery.data.length === 0 && (
          <EmptyState title="No societies yet" description="Create a society first to see its report here." />
        )}
        {reportsQuery.data && reportsQuery.data.length > 0 && (
          <Table<SocietyReportOut>
            keyFor={(r) => r.society_id}
            columns={[
              { header: "Society", render: (r) => <span className="font-medium">{r.name}</span> },
              { header: "City", render: (r) => r.city ?? "—" },
              { header: "Status", render: (r) => <Badge status={r.status}>{r.status}</Badge> },
              { header: "Flats", render: (r) => r.total_flats },
              { header: "Houses", render: (r) => r.total_houses },
              { header: "Total units", render: (r) => r.total_properties },
              { header: "Residents", render: (r) => r.total_residents },
              { header: "Admin", render: (r) => r.admin_name ?? "—" },
              { header: "Admin mobile", render: (r) => r.admin_mobile ?? "—" },
            ]}
            rows={reportsQuery.data}
          />
        )}
      </div>

      {reportsQuery.data && reportsQuery.data.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-navy">Society detail report</h2>
          <div className="max-w-xs">
            <label className="block text-sm text-navy-muted mb-1">Society</label>
            <select
              value={selectedSocietyId}
              onChange={(e) => setSelectedSocietyId(e.target.value)}
              className="w-full border border-line rounded px-3 py-2 text-sm"
            >
              <option value="">Select a society</option>
              {reportsQuery.data.map((r) => (
                <option key={r.society_id} value={r.society_id}>{r.name}</option>
              ))}
            </select>
          </div>

          {selectedSocietyId && <SocietyDetailReport societyId={selectedSocietyId} />}
        </div>
      )}
    </div>
  );
}

function SocietyDetailReport({ societyId }: { societyId: string }) {
  const overviewQuery = useQuery({
    queryKey: ["platform", "society-detail", societyId, "overview"],
    queryFn: () => reportsApi.platformOverview(societyId).then((r) => r.data),
  });
  const maintenanceQuery = useQuery({
    queryKey: ["platform", "society-detail", societyId, "maintenance-summary"],
    queryFn: () => reportsApi.platformMaintenanceSummary(societyId).then((r) => r.data),
  });
  const managerQuery = useQuery({
    queryKey: ["platform", "society-detail", societyId, "manager-performance"],
    queryFn: () => reportsApi.platformManagerPerformance(societyId).then((r) => r.data),
  });
  const balanceQuery = useQuery({
    queryKey: ["platform", "society-detail", societyId, "balance"],
    queryFn: () => reportsApi.platformBalance(societyId).then((r) => r.data),
  });

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-navy-muted">People</h3>
        {overviewQuery.isLoading && <Loader />}
        {overviewQuery.isError && (
          <ErrorState message="Couldn't load people overview." onRetry={() => overviewQuery.refetch()} />
        )}
        {overviewQuery.data && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatTile label="Admin" value={overviewQuery.data.admin_name ?? "—"} />
            <StatTile label="Sub-admins" value={overviewQuery.data.sub_admin_count} />
            <StatTile label="Managers" value={overviewQuery.data.manager_count} />
            <StatTile label="Security Guards" value={overviewQuery.data.security_guard_count} />
            <StatTile label="Residents" value={overviewQuery.data.resident_count} />
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-navy-muted">Monthly Maintenance</h3>
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
        <h3 className="text-sm font-medium text-navy-muted">Income &amp; Expenses</h3>
        {balanceQuery.isLoading && <Loader />}
        {balanceQuery.isError && (
          <ErrorState message="Couldn't load the account balance." onRetry={() => balanceQuery.refetch()} />
        )}
        {balanceQuery.data && (
          <div className="grid grid-cols-3 gap-3">
            <StatTile label="Income" value={`₹${balanceQuery.data.total_income.toLocaleString("en-IN")}`} />
            <StatTile label="Expense" value={`₹${balanceQuery.data.total_expense.toLocaleString("en-IN")}`} />
            <StatTile label="Balance" value={`₹${balanceQuery.data.balance.toLocaleString("en-IN")}`} />
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-navy-muted">Manager Performance</h3>
        {managerQuery.isLoading && <Loader />}
        {managerQuery.isError && (
          <ErrorState message="Couldn't load Manager performance." onRetry={() => managerQuery.refetch()} />
        )}
        {managerQuery.data && managerQuery.data.length === 0 && <EmptyState title="No Managers in this society yet" />}
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
    </div>
  );
}
