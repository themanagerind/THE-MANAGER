import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expenseBillsApi, type ExpenseBillOut } from "@/api/expenseBills";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";

/**
 * Sub-admin's own view — Admin's ExpenseBills page creates/finalizes
 * bills, which is Admin-only; this one decides on them instead (Section
 * 23: 100% of active Sub-admins must APPROVE, any single REJECT is final).
 */
export function SubAdminExpenseBills() {
  const queryClient = useQueryClient();
  const [detailId, setDetailId] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<ExpenseBillOut | null>(null);

  const billsQuery = useQuery({
    queryKey: ["subadmin", "expense-bills"],
    queryFn: () => expenseBillsApi.list().then((r) => r.data),
  });

  const approve = useMutation({
    mutationFn: (id: string) => expenseBillsApi.decide(id, "APPROVE"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["subadmin", "expense-bills"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Expense Bills</h1>

      {billsQuery.isLoading && <Loader />}
      {billsQuery.isError && (
        <ErrorState message="Couldn't load expense bills." onRetry={() => billsQuery.refetch()} />
      )}
      {billsQuery.data && billsQuery.data.items.length === 0 && (
        <EmptyState title="No expense bills yet" description="Bills the Admin opens for approval show up here." />
      )}
      {billsQuery.data && billsQuery.data.items.length > 0 && (
        <Table<ExpenseBillOut>
          keyFor={(b) => b.id}
          columns={[
            { header: "Title", render: (b) => <span className="font-medium">{b.title}</span> },
            { header: "Category", render: (b) => b.category ?? "—" },
            { header: "Amount", render: (b) => `₹${b.amount.toLocaleString("en-IN")}` },
            { header: "Status", render: (b) => <Badge status={b.status}>{b.status.replace("_", " ")}</Badge> },
            {
              header: "",
              render: (b) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="secondary" onClick={() => setDetailId(b.id)}>Details</Button>
                  {b.status === "PENDING_APPROVAL" && (
                    <>
                      <Button variant="secondary" onClick={() => setRejecting(b)}>Reject</Button>
                      <Button
                        loading={approve.isPending && approve.variables === b.id}
                        onClick={() => approve.mutate(b.id)}
                      >
                        Approve
                      </Button>
                    </>
                  )}
                </div>
              ),
            },
          ]}
          rows={billsQuery.data.items}
        />
      )}

      {detailId && <BillDetailModal id={detailId} onClose={() => setDetailId(null)} />}

      {rejecting && (
        <RejectModal
          bill={rejecting}
          onClose={() => setRejecting(null)}
          onSuccess={() => {
            setRejecting(null);
            void queryClient.invalidateQueries({ queryKey: ["subadmin", "expense-bills"] });
          }}
        />
      )}
    </div>
  );
}

function BillDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const detailQuery = useQuery({
    queryKey: ["subadmin", "expense-bill-detail", id],
    queryFn: () => expenseBillsApi.detail(id).then((r) => r.data),
  });

  return (
    <Modal open onClose={onClose} title={detailQuery.data?.bill.title ?? "Expense bill"}>
      {detailQuery.isLoading && <Loader />}
      {detailQuery.data && (
        <div className="space-y-3 text-sm">
          {detailQuery.data.bill.description && (
            <p className="text-navy-muted whitespace-pre-wrap">{detailQuery.data.bill.description}</p>
          )}
          <div className="flex justify-between">
            <span className="text-navy-muted">Amount</span>
            <span className="font-medium">₹{detailQuery.data.bill.amount.toLocaleString("en-IN")}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-navy-muted">Status</span>
            <Badge status={detailQuery.data.bill.status}>{detailQuery.data.bill.status.replace("_", " ")}</Badge>
          </div>
          {detailQuery.data.bill.status === "PENDING_APPROVAL" && (
            <div className="flex justify-between">
              <span className="text-navy-muted">Sub-admin approvals</span>
              <span>{detailQuery.data.approve_count} / {detailQuery.data.active_subadmin_count} (needs {detailQuery.data.approvals_needed})</span>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function RejectModal({
  bill, onClose, onSuccess,
}: { bill: ExpenseBillOut; onClose: () => void; onSuccess: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reject = useMutation({
    mutationFn: () => expenseBillsApi.decide(bill.id, "REJECT", reason.trim() || undefined),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't reject this bill.")),
  });

  return (
    <Modal open onClose={onClose} title={`Reject — ${bill.title}`}>
      <div className="space-y-4">
        <p className="text-xs text-navy-muted">
          A single REJECT is final for this bill (Section 23) — this can't be undone.
        </p>
        <Input label="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={reject.isPending} onClick={() => reject.mutate()}>
            Reject
          </Button>
        </div>
      </div>
    </Modal>
  );
}
