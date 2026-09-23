import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expenseBillsApi, type ExpenseBillOut } from "@/api/expenseBills";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";

export function AdminExpenseBills() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const billsQuery = useQuery({
    queryKey: ["admin", "expense-bills"],
    queryFn: () => expenseBillsApi.list().then((r) => r.data),
  });

  const finalize = useMutation({
    mutationFn: (id: string) => expenseBillsApi.finalize(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "expense-bills"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Expense Bills</h1>
        <Button onClick={() => setCreating(true)}>Add bill</Button>
      </div>

      {billsQuery.isLoading && <Loader />}
      {billsQuery.isError && (
        <ErrorState message="Couldn't load expense bills." onRetry={() => billsQuery.refetch()} />
      )}
      {billsQuery.data && billsQuery.data.items.length === 0 && (
        <EmptyState title="No expense bills yet" description="Bills created here or drafted by the Manager show up here." />
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
                  {b.status === "DRAFT" && (
                    <Button
                      loading={finalize.isPending && finalize.variables === b.id}
                      onClick={() => finalize.mutate(b.id)}
                    >
                      Finalize
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
          rows={billsQuery.data.items}
        />
      )}

      {creating && (
        <CreateBillModal
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "expense-bills"] });
          }}
        />
      )}

      {detailId && <BillDetailModal id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function BillDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const detailQuery = useQuery({
    queryKey: ["admin", "expense-bill-detail", id],
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

function CreateBillModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      expenseBillsApi.createAndFinalize({
        title: title.trim(),
        description: description.trim() || undefined,
        amount: Number(amount),
        category: category.trim() || undefined,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add this bill.")),
  });

  const validAmount = Number(amount) > 0;

  return (
    <Modal open onClose={onClose} title="Add expense bill">
      <div className="space-y-4">
        <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Input label="Category (optional)" value={category} onChange={(e) => setCategory(e.target.value)} />
        <Input
          label="Amount"
          type="number"
          min="0"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <div>
          <label className="block text-sm text-navy-muted mb-1">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!title.trim() || !validAmount} onClick={() => create.mutate()}>
            Add & finalize
          </Button>
        </div>
      </div>
    </Modal>
  );
}
