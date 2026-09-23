import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { complaintsApi, type ComplaintOut } from "@/api/complaints";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import type { ComplaintStatus } from "@/types/enums";

/** Natural workflow order for the UI's action button — the backend
 * doesn't enforce a state machine on complaint status (see
 * pages/manager/Complaints.tsx), this only shapes what's offered next. */
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

export function AdminComplaints() {
  const queryClient = useQueryClient();
  const [assigning, setAssigning] = useState<ComplaintOut | null>(null);

  const complaintsQuery = useQuery({
    queryKey: ["admin", "complaints"],
    queryFn: () => complaintsApi.list().then((r) => r.data),
  });

  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ComplaintStatus }) => complaintsApi.updateStatus(id, status),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "complaints"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Complaints</h1>

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
                return (
                  <div className="flex gap-2 justify-end">
                    <Button variant="secondary" onClick={() => setAssigning(c)}>Assign</Button>
                    {target && label && (
                      <Button
                        variant="secondary"
                        loading={advance.isPending && advance.variables?.id === c.id}
                        onClick={() => advance.mutate({ id: c.id, status: target })}
                      >
                        {label}
                      </Button>
                    )}
                  </div>
                );
              },
            },
          ]}
          rows={complaintsQuery.data}
        />
      )}

      {assigning && (
        <AssignModal
          complaint={assigning}
          onClose={() => setAssigning(null)}
          onSuccess={() => setAssigning(null)}
        />
      )}
    </div>
  );
}

function AssignModal({
  complaint, onClose, onSuccess,
}: { complaint: ComplaintOut; onClose: () => void; onSuccess: () => void }) {
  const [managerId, setManagerId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const assign = useMutation({
    mutationFn: () => complaintsApi.assign(complaint.id, managerId.trim()),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't assign this complaint.")),
  });

  return (
    <Modal open onClose={onClose} title={`Assign — ${complaint.title}`}>
      <div className="space-y-4">
        <Input
          label="Manager's user ID"
          value={managerId}
          onChange={(e) => setManagerId(e.target.value)}
          placeholder="Paste the Manager's user ID"
        />
        <p className="text-xs text-navy-muted">
          Must be an active Manager in this society — checked server-side.
        </p>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={assign.isPending} disabled={!managerId.trim()} onClick={() => assign.mutate()}>
            Assign
          </Button>
        </div>
      </div>
    </Modal>
  );
}
