import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { paymentsApi, type MaintenanceDueByLocationOut } from "@/api/payments";
import { locationsApi } from "@/api/societies";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";

/**
 * View-only, property-level — this is the ENTIRE scope of Manager's
 * finance visibility (finalized requirement: no society-wide ledger, no
 * resident identity, no write/approve/reject access). Wing/Row-first
 * instead of a per-property picker: a Manager only ever needs to know
 * who's outstanding, and going property-by-property to find that across
 * a whole Wing was the actual complaint this replaces — one Wing/Row
 * pick now surfaces every still-PENDING due in it at once.
 * MaintenanceDueByLocationOut carries no resident_id/name, so there's
 * nothing to accidentally leak here even by rendering every field.
 */
export function ManagerDues() {
  const [locationId, setLocationId] = useState("");

  const locationsQuery = useQuery({
    queryKey: ["manager", "locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
  });

  const duesQuery = useQuery({
    queryKey: ["manager", "dues", "by-location", locationId],
    queryFn: () => paymentsApi.outstandingDuesByLocation(locationId).then((r) => r.data),
    enabled: !!locationId,
  });

  const sortedLocations = [...(locationsQuery.data ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" })
  );

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">MONTHLY MAINTENANCE</h1>
      <p className="text-sm text-navy-muted">
        Wing/Row-level outstanding dues, view-only — pick a Wing or Row to see every property still pending payment
        in it.
      </p>

      {locationsQuery.isLoading && <Loader />}
      {locationsQuery.isError && (
        <ErrorState message="Couldn't load Wings/Rows." onRetry={() => locationsQuery.refetch()} />
      )}
      {locationsQuery.data && (
        <div>
          <label className="block text-sm text-navy-muted mb-1">Wing / Row</label>
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="w-full max-w-xs px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select a Wing/Row</option>
            {sortedLocations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name} ({l.location_type === "WING" ? "Wing" : "Row"})
              </option>
            ))}
          </select>
        </div>
      )}

      {locationId && duesQuery.isLoading && <Loader />}
      {locationId && duesQuery.isError && (
        <ErrorState message="Couldn't load outstanding dues for this Wing/Row." onRetry={() => duesQuery.refetch()} />
      )}
      {locationId && duesQuery.data && duesQuery.data.length === 0 && (
        <EmptyState title="Nothing outstanding" description="Every property in this Wing/Row is up to date." />
      )}
      {locationId && duesQuery.data && duesQuery.data.length > 0 && (
        <Table<MaintenanceDueByLocationOut>
          keyFor={(d) => d.id}
          columns={[
            { header: "Property", render: (d) => d.property_house_number },
            { header: "Billing month", render: (d) => new Date(d.billing_month).toLocaleDateString("en-IN", { month: "short", year: "numeric" }) },
            { header: "Amount", render: (d) => `₹${d.amount.toLocaleString("en-IN")}` },
            {
              header: "Penalty",
              render: (d) => (d.penalty_amount > 0 ? `₹${d.penalty_amount.toLocaleString("en-IN")}` : "—"),
            },
            { header: "Total outstanding", render: (d) => `₹${d.total_amount.toLocaleString("en-IN")}` },
            { header: "Due date", render: (d) => new Date(d.due_date).toLocaleDateString("en-IN") },
            { header: "Status", render: (d) => <Badge status={d.status}>{d.status}</Badge> },
          ]}
          rows={duesQuery.data}
        />
      )}
    </div>
  );
}
