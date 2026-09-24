import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi, type MaintenanceDueOut, type PaymentOut } from "@/api/payments";
import { propertiesApi } from "@/api/properties";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { AuthenticatedImage } from "@/components/AuthenticatedImage";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

/**
 * Shared by Admin (/admin/dues) and Sub-admin (/subadmin/dues) — approve,
 * reject and correct are open to both roles server-side, with a Sub-admin's
 * results already scoped to their Wing/Row by the API. Monthly bill
 * generation is Admin-only (Section 13.2), so `canGenerateBills` hides
 * that action rather than showing a button that would 403 for a Sub-admin.
 */
export function DuesPage({ canGenerateBills }: { canGenerateBills: boolean }) {
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [rejecting, setRejecting] = useState<PaymentOut | null>(null);
  const [correcting, setCorrecting] = useState<PaymentOut | null>(null);
  const [viewingProof, setViewingProof] = useState<PaymentOut | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: ["dues", "payments"] });
    void queryClient.invalidateQueries({ queryKey: ["dues", "maintenance-dues"] });
  };

  const pendingQuery = useQuery({
    queryKey: ["dues", "payments", "pending"],
    queryFn: () => paymentsApi.pending().then((r) => r.data),
  });

  const allQuery = useQuery({
    queryKey: ["dues", "payments", "all", page],
    queryFn: () => paymentsApi.list(page * pageSize, pageSize).then((r) => r.data),
  });

  const duesQueryKey = ["dues", "maintenance-dues", "all"];
  const duesQuery = useQuery({
    queryKey: duesQueryKey,
    queryFn: () => paymentsApi.allDues().then((r) => r.data),
  });
  const propertiesQuery = useQuery({
    queryKey: ["dues", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });
  const houseNumberFor = (propertyId: string) =>
    propertiesQuery.data?.find((p) => p.id === propertyId)?.house_number ?? "—";

  const approve = useMutation({
    mutationFn: (id: string) => paymentsApi.approve(id),
    onSuccess: invalidateAll,
  });

  const waivePenalty = useMutation({
    mutationFn: (dueId: string) => paymentsApi.waivePenalty(dueId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: duesQueryKey }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-navy">Maintenance Dues</h1>
        {canGenerateBills && <Button onClick={() => setGenerating(true)}>Generate monthly bills</Button>}
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Pending approval</h2>
        {pendingQuery.isLoading && <Loader />}
        {pendingQuery.isError && <ErrorState message="Couldn't load pending payments." onRetry={() => pendingQuery.refetch()} />}
        {pendingQuery.data && pendingQuery.data.length === 0 && <EmptyState title="No payments awaiting approval" />}
        {pendingQuery.data && pendingQuery.data.length > 0 && (
          <Table<PaymentOut>
            keyFor={(p) => p.id}
            columns={[
              { header: "Amount", render: (p) => `₹${p.amount.toLocaleString("en-IN")}` },
              { header: "Method", render: (p) => p.payment_method },
              { header: "Reference", render: (p) => p.reference_number ?? "—" },
              {
                header: "",
                render: (p) => (
                  <div className="flex gap-2 justify-end">
                    {p.payment_method !== "MOCK_ONLINE" && (
                      <Button variant="secondary" onClick={() => setViewingProof(p)}>View proof</Button>
                    )}
                    <Button variant="secondary" onClick={() => setRejecting(p)}>Reject</Button>
                    <Button loading={approve.isPending} onClick={() => approve.mutate(p.id)}>Approve</Button>
                  </div>
                ),
              },
            ]}
            rows={pendingQuery.data}
          />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">All maintenance dues</h2>
        {duesQuery.isLoading && <Loader />}
        {duesQuery.isError && <ErrorState message="Couldn't load dues." onRetry={() => duesQuery.refetch()} />}
        {duesQuery.data && duesQuery.data.length === 0 && <EmptyState title="No bills generated yet" />}
        {duesQuery.data && duesQuery.data.length > 0 && (
          <Table<MaintenanceDueOut>
            keyFor={(d) => d.id}
            columns={[
              { header: "Property", render: (d) => houseNumberFor(d.property_id) },
              {
                header: "Month",
                render: (d) => new Date(d.billing_month).toLocaleDateString("en-IN", { month: "short", year: "numeric" }),
              },
              { header: "Amount", render: (d) => `₹${d.amount.toLocaleString("en-IN")}` },
              {
                header: "Penalty",
                render: (d) =>
                  !d.penalty_enabled ? (
                    "—"
                  ) : d.penalty_waived ? (
                    <span className="text-xs text-navy-muted">Waived</span>
                  ) : d.penalty_amount > 0 ? (
                    `₹${d.penalty_amount.toLocaleString("en-IN")}`
                  ) : (
                    "₹0"
                  ),
              },
              { header: "Total", render: (d) => `₹${d.total_amount.toLocaleString("en-IN")}` },
              { header: "Due date", render: (d) => new Date(d.due_date).toLocaleDateString("en-IN") },
              { header: "Status", render: (d) => <Badge status={d.status}>{d.status}</Badge> },
              {
                header: "",
                render: (d) =>
                  canGenerateBills && d.penalty_enabled && !d.penalty_waived && d.penalty_amount > 0 ? (
                    <div className="flex justify-end">
                      <Button
                        variant="secondary"
                        loading={waivePenalty.isPending && waivePenalty.variables === d.id}
                        onClick={() => waivePenalty.mutate(d.id)}
                      >
                        Waive penalty
                      </Button>
                    </div>
                  ) : null,
              },
            ]}
            rows={duesQuery.data}
          />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">All payments</h2>
        {allQuery.isLoading && <Loader />}
        {allQuery.isError && <ErrorState message="Couldn't load payments." onRetry={() => allQuery.refetch()} />}
        {allQuery.data && allQuery.data.items.length === 0 && <EmptyState title="No payments yet" />}
        {allQuery.data && allQuery.data.items.length > 0 && (
          <>
            <Table<PaymentOut>
              keyFor={(p) => p.id}
              columns={[
                { header: "Amount", render: (p) => `₹${p.amount.toLocaleString("en-IN")}` },
                { header: "Method", render: (p) => p.payment_method },
                { header: "Status", render: (p) => <Badge status={p.status}>{p.status}</Badge> },
                { header: "Created", render: (p) => new Date(p.created_at).toLocaleDateString("en-IN") },
                {
                  header: "",
                  render: (p) =>
                    p.status === "PAID" ? (
                      <Button variant="secondary" onClick={() => setCorrecting(p)}>Correct</Button>
                    ) : null,
                },
              ]}
              rows={allQuery.data.items}
            />
            <div className="flex items-center justify-between text-sm text-navy-muted">
              <span>
                {page * pageSize + 1}–{Math.min((page + 1) * pageSize, allQuery.data.total)} of {allQuery.data.total}
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button
                  variant="secondary"
                  disabled={(page + 1) * pageSize >= allQuery.data.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </section>

      {generating && (
        <GenerateBillsModal
          onClose={() => setGenerating(false)}
          onSuccess={() => {
            setGenerating(false);
            invalidateAll();
          }}
        />
      )}

      {rejecting && (
        <RejectModal
          payment={rejecting}
          onClose={() => setRejecting(null)}
          onSuccess={() => {
            setRejecting(null);
            invalidateAll();
          }}
        />
      )}

      {correcting && (
        <CorrectModal
          payment={correcting}
          onClose={() => setCorrecting(null)}
          onSuccess={() => {
            setCorrecting(null);
            invalidateAll();
          }}
        />
      )}

      {viewingProof && (
        <ProofModal payment={viewingProof} onClose={() => setViewingProof(null)} />
      )}
    </div>
  );
}

function ProofModal({ payment, onClose }: { payment: PaymentOut; onClose: () => void }) {
  const proofsQuery = useQuery({
    queryKey: ["dues", "payments", payment.id, "proofs"],
    queryFn: () => paymentsApi.proofs(payment.id).then((r) => r.data),
  });

  return (
    <Modal open onClose={onClose} title={`Proof — ₹${payment.amount.toLocaleString("en-IN")}`}>
      <div className="space-y-4">
        {proofsQuery.isLoading && <Loader />}
        {proofsQuery.isError && <ErrorState message="Couldn't load proof." onRetry={() => proofsQuery.refetch()} />}
        {proofsQuery.data && proofsQuery.data.length === 0 && <EmptyState title="No proof on file for this payment" />}
        {proofsQuery.data?.map((proof) => (
          <div key={proof.id} className="space-y-1">
            <p className="text-xs text-navy-muted">
              {proof.proof_type === "UPI_SCREENSHOT" ? "UPI screenshot" : "Cash receipt"} · uploaded{" "}
              {new Date(proof.uploaded_at).toLocaleString("en-IN")}
            </p>
            <AuthenticatedImage src={proof.file_url} alt="Payment proof" className="max-h-96 rounded border border-line" />
          </div>
        ))}
        <div className="flex justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Modal>
  );
}

function GenerateBillsModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const today = new Date();
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
  const [occupiedAmount, setOccupiedAmount] = useState("");
  const [vacantAmount, setVacantAmount] = useState("");
  const [billingMonth, setBillingMonth] = useState(defaultMonth);
  const [dueDate, setDueDate] = useState(defaultMonth);
  const [penaltyEnabled, setPenaltyEnabled] = useState(false);
  const [penaltyPerDay, setPenaltyPerDay] = useState("");
  const [error, setError] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      paymentsApi.generateBills(
        Number(occupiedAmount), Number(vacantAmount), billingMonth, dueDate,
        penaltyEnabled, penaltyEnabled ? Number(penaltyPerDay) : undefined
      ),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not generate bills.")),
  });

  const canSubmit =
    !!occupiedAmount && Number(occupiedAmount) >= 0 &&
    !!vacantAmount && Number(vacantAmount) >= 0 &&
    !!dueDate &&
    (!penaltyEnabled || (!!penaltyPerDay && Number(penaltyPerDay) > 0));

  return (
    <Modal open onClose={onClose} title="Generate monthly bills">
      <div className="space-y-4">
        <p className="text-xs text-navy-muted">
          Section 13.2: creates one bill per active property, society-wide, for the given month — occupied flats/
          houses get one amount, vacant ones another.
        </p>
        <Input
          label="Occupied flats/houses — amount (₹)"
          type="number"
          value={occupiedAmount}
          onChange={(e) => setOccupiedAmount(e.target.value)}
        />
        <Input
          label="Vacant flats/houses — amount (₹)"
          type="number"
          value={vacantAmount}
          onChange={(e) => setVacantAmount(e.target.value)}
        />
        <Input
          label="Billing month"
          type="date"
          value={billingMonth}
          onChange={(e) => setBillingMonth(e.target.value)}
        />
        <Input
          label="Due date"
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
        />

        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={penaltyEnabled}
            onChange={(e) => setPenaltyEnabled(e.target.checked)}
          />
          Apply a late-payment penalty after the due date
        </label>
        {penaltyEnabled && (
          <Input
            label="Penalty per day, after due date (₹)"
            type="number"
            value={penaltyPerDay}
            onChange={(e) => setPenaltyPerDay(e.target.value)}
          />
        )}

        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={generate.isPending} disabled={!canSubmit} onClick={() => generate.mutate()}>
            Generate
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function RejectModal({
  payment, onClose, onSuccess,
}: { payment: PaymentOut; onClose: () => void; onSuccess: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reject = useMutation({
    mutationFn: () => paymentsApi.reject(payment.id, reason),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not reject payment.")),
  });

  return (
    <Modal open onClose={onClose} title={`Reject payment — ₹${payment.amount.toLocaleString("en-IN")}`}>
      <div className="space-y-4">
        <Input label="Rejection reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={reject.isPending} disabled={!reason.trim()} onClick={() => reject.mutate()}>
            Reject
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function CorrectModal({
  payment, onClose, onSuccess,
}: { payment: PaymentOut; onClose: () => void; onSuccess: () => void }) {
  const [newAmount, setNewAmount] = useState(String(payment.amount));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const correct = useMutation({
    mutationFn: () => paymentsApi.correct(payment.id, Number(newAmount), reason),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not correct payment.")),
  });

  return (
    <Modal open onClose={onClose} title="Correct payment">
      <div className="space-y-4">
        <p className="text-xs text-navy-muted">
          Section 13.3/49.3: this records a correction event — it never overwrites the original payment history.
        </p>
        <Input label="New amount (₹)" type="number" value={newAmount} onChange={(e) => setNewAmount(e.target.value)} />
        <Input label="Reason (mandatory)" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={correct.isPending}
            disabled={!reason.trim() || !newAmount || Number(newAmount) <= 0}
            onClick={() => correct.mutate()}
          >
            Save correction
          </Button>
        </div>
      </div>
    </Modal>
  );
}
