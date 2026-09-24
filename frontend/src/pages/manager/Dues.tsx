import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { paymentsApi, type MaintenanceDueOut } from "@/api/payments";
import { propertiesApi } from "@/api/properties";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";

/**
 * View-only, property-level — this is the ENTIRE scope of Manager's
 * finance visibility (finalized requirement: no society-wide ledger, no
 * resident identity, no write/approve/reject access). MaintenanceDueOut
 * itself carries no resident_id/resident name, so there's nothing to
 * accidentally leak here even by rendering every field.
 */
export function ManagerDues() {
  const [propertyId, setPropertyId] = useState("");

  const propertiesQuery = useQuery({
    queryKey: ["manager", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });

  const duesQuery = useQuery({
    queryKey: ["manager", "dues", propertyId],
    queryFn: () => paymentsApi.duesForProperty(propertyId).then((r) => r.data),
    enabled: !!propertyId,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">MONTHLY MAINTENANCE</h1>
      <p className="text-sm text-navy-muted">
        Property-level dues, view-only — pick a property to see its billing history.
      </p>

      {propertiesQuery.isLoading && <Loader />}
      {propertiesQuery.isError && (
        <ErrorState message="Couldn't load properties." onRetry={() => propertiesQuery.refetch()} />
      )}
      {propertiesQuery.data && (
        <div>
          <label className="block text-sm text-navy-muted mb-1">Property</label>
          <select
            value={propertyId}
            onChange={(e) => setPropertyId(e.target.value)}
            className="w-full max-w-xs px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select a property</option>
            {propertiesQuery.data.map((p) => (
              <option key={p.id} value={p.id}>{p.house_number}</option>
            ))}
          </select>
        </div>
      )}

      {propertyId && duesQuery.isLoading && <Loader />}
      {propertyId && duesQuery.isError && (
        <ErrorState message="Couldn't load dues for this property." onRetry={() => duesQuery.refetch()} />
      )}
      {propertyId && duesQuery.data && duesQuery.data.length === 0 && (
        <EmptyState title="No dues on record" description="No maintenance dues have been generated for this property yet." />
      )}
      {propertyId && duesQuery.data && duesQuery.data.length > 0 && (
        <Table<MaintenanceDueOut>
          keyFor={(d) => d.id}
          columns={[
            { header: "Billing month", render: (d) => new Date(d.billing_month).toLocaleDateString("en-IN", { month: "short", year: "numeric" }) },
            { header: "Amount", render: (d) => `₹${d.amount.toLocaleString("en-IN")}` },
            { header: "Due date", render: (d) => new Date(d.due_date).toLocaleDateString("en-IN") },
            { header: "Status", render: (d) => <Badge status={d.status}>{d.status}</Badge> },
          ]}
          rows={duesQuery.data}
        />
      )}
    </div>
  );
}
