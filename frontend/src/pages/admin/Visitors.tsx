import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { visitorsApi, type VisitorOut } from "@/api/visitors";
import { propertiesApi } from "@/api/properties";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

/** Read-only — entry/exit marking is Guard's job (Section 21 data
 * boundary), Admin just needs visibility into the log. */
export function AdminVisitors() {
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const visitorsQuery = useQuery({
    queryKey: ["admin", "visitors", page],
    queryFn: () => visitorsApi.list(page * pageSize, pageSize).then((r) => r.data),
  });

  const propertiesQuery = useQuery({
    queryKey: ["admin", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });

  const houseNumberById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of propertiesQuery.data ?? []) map.set(p.id, p.house_number);
    return map;
  }, [propertiesQuery.data]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Visitors</h1>

      {visitorsQuery.isLoading && <Loader />}
      {visitorsQuery.isError && (
        <ErrorState message="Couldn't load visitors." onRetry={() => visitorsQuery.refetch()} />
      )}
      {visitorsQuery.data && visitorsQuery.data.items.length === 0 && (
        <EmptyState title="No visitors yet" description="Resident pre-approvals and Guard entries show up here." />
      )}
      {visitorsQuery.data && visitorsQuery.data.items.length > 0 && (
        <>
          <Table<VisitorOut>
            keyFor={(v) => v.id}
            columns={[
              { header: "Visitor", render: (v) => <span className="font-medium">{v.visitor_name}</span> },
              { header: "Mobile", render: (v) => v.visitor_mobile ?? "—" },
              { header: "Property", render: (v) => houseNumberById.get(v.property_id) ?? "—" },
              { header: "Visit date", render: (v) => new Date(v.visit_date).toLocaleDateString("en-IN") },
              { header: "Status", render: (v) => <Badge status={v.status}>{v.status.replace("_", " ")}</Badge> },
            ]}
            rows={visitorsQuery.data.items}
          />
          <div className="flex items-center justify-between text-sm text-navy-muted">
            <span>
              {visitorsQuery.data.total === 0
                ? "0 visitors"
                : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, visitorsQuery.data.total)} of ${visitorsQuery.data.total}`}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <Button
                variant="secondary"
                disabled={(page + 1) * pageSize >= visitorsQuery.data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
