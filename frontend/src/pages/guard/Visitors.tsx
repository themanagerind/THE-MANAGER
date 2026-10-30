import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { visitorsApi, type GuardVisitorOut } from "@/api/visitors";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";

const QUERY_KEY = ["guard", "visitors"];

/** Security Guard's gate view — Section 21 data boundary: only what's
 * needed to let someone in/out (house number, visitor name/mobile, visit
 * date, status), never resident/payment/wallet data. Entry is only valid
 * from PRE_APPROVED/EXPECTED, exit only from ENTERED — the backend
 * enforces this (409 otherwise); the buttons here just hide the action
 * once it's no longer valid instead of letting the Guard hit that 409. */
export function GuardVisitors() {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const visitorsQuery = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => visitorsApi.guardView().then((r) => r.data),
  });

  const markEntry = useMutation({
    mutationFn: (id: string) => visitorsApi.markEntry(id),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (e) => setActionError(apiErrorMessage(e, "Couldn't mark entry.")),
  });

  const markExit = useMutation({
    mutationFn: (id: string) => visitorsApi.markExit(id),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (e) => setActionError(apiErrorMessage(e, "Couldn't mark exit.")),
  });

  const sorted = [...(visitorsQuery.data ?? [])].sort(
    (a, b) => new Date(b.visit_date).getTime() - new Date(a.visit_date).getTime()
  );

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Visitors</h1>

      {visitorsQuery.isLoading && <Loader />}
      {visitorsQuery.isError && (
        <ErrorState message="Couldn't load visitors." onRetry={() => visitorsQuery.refetch()} />
      )}
      {visitorsQuery.data && visitorsQuery.data.length === 0 && (
        <EmptyState title="No visitors yet" description="Resident pre-approvals show up here for entry/exit." />
      )}
      {actionError && <p className="text-sm text-danger">{actionError}</p>}
      {visitorsQuery.data && visitorsQuery.data.length > 0 && (
        <Table<GuardVisitorOut>
          keyFor={(v) => v.id}
          columns={[
            { header: "House", render: (v) => <span className="font-medium">{v.property_house_number}</span> },
            { header: "Visitor", render: (v) => v.visitor_name },
            { header: "Mobile", render: (v) => v.visitor_mobile ?? "—" },
            { header: "Visit date", render: (v) => new Date(v.visit_date).toLocaleDateString("en-IN") },
            { header: "Status", render: (v) => <Badge status={v.status}>{v.status.replace("_", " ")}</Badge> },
            {
              header: "",
              render: (v) => (
                <div className="flex justify-end">
                  {(v.status === "PRE_APPROVED" || v.status === "EXPECTED") && (
                    <Button
                      loading={markEntry.isPending && markEntry.variables === v.id}
                      onClick={() => markEntry.mutate(v.id)}
                    >
                      Mark entry
                    </Button>
                  )}
                  {v.status === "ENTERED" && (
                    <Button
                      variant="secondary"
                      loading={markExit.isPending && markExit.variables === v.id}
                      onClick={() => markExit.mutate(v.id)}
                    >
                      Mark exit
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
          rows={sorted}
        />
      )}
    </div>
  );
}
