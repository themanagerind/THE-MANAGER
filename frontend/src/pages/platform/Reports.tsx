import { societiesApi, type SocietyReportOut } from "@/api/societies";
import { useQuery } from "@tanstack/react-query";
import { Loader, EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";

/**
 * Platform Owner reporting dashboard — one row per society: how many
 * flats/houses are on record, how many Residents are currently actively
 * linked, and who the Admin is (name + mobile) so the Platform Owner can
 * reach them without opening each society individually.
 */
export function PlatformReports() {
  const reportsQuery = useQuery({
    queryKey: ["platform", "societies", "reports"],
    queryFn: () => societiesApi.reports().then((r) => r.data),
  });

  return (
    <div className="space-y-6">
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
  );
}
