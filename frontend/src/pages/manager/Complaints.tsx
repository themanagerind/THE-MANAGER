import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { complaintsApi, type ComplaintOut } from "@/api/complaints";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import type { ComplaintStatus } from "@/types/enums";

/** Natural workflow order for the UI's action button. The backend doesn't
 * enforce a state machine on complaint status (any -> any is accepted), so
 * this only shapes what Manager sees as the "next" action — it isn't a
 * restriction the API itself applies. */
const nextStatus: Partial<Record<ComplaintStatus, ComplaintStatus>> = {
  OPEN: "IN_PROGRESS",
  IN_PROGRESS: "RESOLVED",
  RESOLVED: "CLOSED",
};
const nextActionLabel: Partial<Record<ComplaintStatus, string>> = {
  OPEN: "Start",
  IN_PROGRESS: "Mark resolved",
  RESOLVED: "Close",
};

export function ManagerComplaints() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const complaintsQuery = useQuery({
    queryKey: ["manager", "complaints"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });

  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ComplaintStatus }) => complaintsApi.updateStatus(id, status),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["manager", "complaints"] });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update the complaint status.")),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Complaints</h1>

      {error && <p className="text-sm text-danger">{error}</p>}

      {complaintsQuery.isLoading && <Loader />}
      {complaintsQuery.isError && (
        <ErrorState message="Couldn't load complaints." onRetry={() => complaintsQuery.refetch()} />
      )}
      {complaintsQuery.data && complaintsQuery.data.length === 0 && (
        <EmptyState title="No complaints" description="Complaints raised by Residents will show up here." />
      )}
      {complaintsQuery.data && complaintsQuery.data.length > 0 && (
        <Table<ComplaintOut>
          keyFor={(c) => c.id}
          columns={[
            { header: "Title", render: (c) => <span className="font-medium">{c.title}</span> },
            { header: "Category", render: (c) => c.category },
            { header: "Status", render: (c) => <Badge status={c.status}>{c.status.replace("_", " ")}</Badge> },
            { header: "Raised", render: (c) => new Date(c.created_at).toLocaleDateString("en-IN") },
            {
              header: "",
              render: (c) => {
                const target = nextStatus[c.status];
                const label = nextActionLabel[c.status];
                if (!target || !label) return null;
                return (
                  <div className="flex justify-end">
                    <Button
                      variant="secondary"
                      loading={advance.isPending && advance.variables?.id === c.id}
                      onClick={() => advance.mutate({ id: c.id, status: target })}
                    >
                      {label}
                    </Button>
                  </div>
                );
              },
            },
          ]}
          rows={complaintsQuery.data}
        />
      )}
    </div>
  );
}
