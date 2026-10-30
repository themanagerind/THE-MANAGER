import { useQuery } from "@tanstack/react-query";
import { noticesApi } from "@/api/notices";
import { Loader, EmptyState, ErrorState } from "@/components/States";

export function ResidentNotices() {
  const noticesQuery = useQuery({
    queryKey: ["notices"],
    queryFn: () => noticesApi.list().then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Notices</h1>

      {noticesQuery.isLoading && <Loader />}
      {noticesQuery.isError && <ErrorState message="Couldn't load notices." onRetry={() => noticesQuery.refetch()} />}
      {noticesQuery.data && noticesQuery.data.items.length === 0 && (
        <EmptyState title="No notices yet" description="Society-wide announcements will show up here." />
      )}

      <div className="space-y-3">
        {noticesQuery.data?.items.map((n) => (
          <div key={n.id} className="border border-line rounded p-4">
            <div className="flex items-center justify-between mb-1">
              <h2 className="font-medium text-ink">{n.title}</h2>
              <span className="text-xs text-navy-muted">{new Date(n.created_at).toLocaleDateString("en-IN")}</span>
            </div>
            <p className="text-sm text-navy-muted whitespace-pre-wrap">{n.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
