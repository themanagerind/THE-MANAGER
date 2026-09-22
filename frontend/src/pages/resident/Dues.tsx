import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useActiveProperty } from "@/hooks/useActiveProperty";
import { paymentsApi, type MaintenanceDueOut } from "@/api/payments";
import { PropertySelector } from "@/components/PropertySelector";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { PaymentMethod, ProofType } from "@/types/enums";

export function ResidentDues() {
  const { activePropertyId, setActivePropertyId, options, hasMultipleProperties, isLoading: propsLoading } = useActiveProperty();
  const queryClient = useQueryClient();
  const [payingDue, setPayingDue] = useState<MaintenanceDueOut | null>(null);

  const duesQuery = useQuery({
    queryKey: ["dues", activePropertyId],
    queryFn: () => paymentsApi.duesForProperty(activePropertyId!).then((r) => r.data),
    enabled: !!activePropertyId,
  });

  if (propsLoading) return <Loader />;
  if (options.length === 0) return <EmptyState title="No linked property yet" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Maintenance Dues</h1>
        {hasMultipleProperties && (
          <PropertySelector properties={options} activePropertyId={activePropertyId} onChange={setActivePropertyId} />
        )}
      </div>

      {duesQuery.isLoading && <Loader />}
      {duesQuery.isError && <ErrorState message="Couldn't load dues." onRetry={() => duesQuery.refetch()} />}
      {duesQuery.data && duesQuery.data.length === 0 && (
        <EmptyState title="No dues yet" description="Bills your Admin generates will appear here." />
      )}
      {duesQuery.data && duesQuery.data.length > 0 && (
        <Table<MaintenanceDueOut>
          keyFor={(d) => d.id}
          columns={[
            { header: "Month", render: (d) => new Date(d.billing_month).toLocaleDateString("en-IN", { month: "long", year: "numeric" }) },
            { header: "Amount", render: (d) => `₹${d.amount.toLocaleString("en-IN")}` },
            { header: "Status", render: (d) => <Badge status={d.status}>{d.status}</Badge> },
            {
              header: "",
              render: (d) =>
                d.status === "PENDING" ? (
                  <Button variant="secondary" onClick={() => setPayingDue(d)}>
                    Pay
                  </Button>
                ) : null,
            },
          ]}
          rows={duesQuery.data}
        />
      )}

      {payingDue && (
        <PaymentModal
          due={payingDue}
          onClose={() => setPayingDue(null)}
          onSuccess={() => {
            setPayingDue(null);
            void queryClient.invalidateQueries({ queryKey: ["dues", activePropertyId] });
            void queryClient.invalidateQueries({ queryKey: ["wallet", "me"] });
          }}
        />
      )}
    </div>
  );
}

function PaymentModal({ due, onClose, onSuccess }: { due: MaintenanceDueOut; onClose: () => void; onSuccess: () => void }) {
  const [method, setMethod] = useState<PaymentMethod>("MOCK_ONLINE");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofPreviewUrl, setProofPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function onFileSelected(file: File | null) {
    setProofFile(file);
    setProofPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return file ? URL.createObjectURL(file) : null;
    });
  }

  const submit = useMutation({
    mutationFn: async () => {
      const isManual = method !== "MOCK_ONLINE";
      const proofType: ProofType | undefined = isManual ? (method === "MANUAL_UPI" ? "UPI_SCREENSHOT" : "CASH_RECEIPT") : undefined;

      // Section 14.2/14.3: upload the actual image first (audit fix — this
      // used to be a pasted URL with no real upload behind it), then
      // submit the payment referencing the returned file_url.
      let proofFileUrl: string | undefined;
      if (isManual && proofFile) {
        const { data } = await paymentsApi.uploadProof(proofFile);
        proofFileUrl = data.file_url;
      }

      return paymentsApi.submit({
        maintenance_due_id: due.id,
        payment_method: method,
        reference_number: referenceNumber || undefined,
        proof_type: proofType,
        proof_file_url: proofFileUrl,
      });
    },
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Payment could not be submitted.")),
  });

  const isManual = method !== "MOCK_ONLINE";
  const canSubmit = !isManual || !!proofFile;

  return (
    <Modal open onClose={onClose} title={`Pay ₹${due.amount.toLocaleString("en-IN")}`}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Payment method</label>
          <div className="flex gap-2">
            {([
              { value: "MOCK_ONLINE", label: "Online" },
              { value: "MANUAL_UPI", label: "UPI" },
              { value: "MANUAL_CASH", label: "Cash" },
            ] as { value: PaymentMethod; label: string }[]).map((opt) => (
              <button
                key={opt.value}
                onClick={() => setMethod(opt.value)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  method === opt.value ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {isManual && (
          <>
            <Input
              label="Reference number (optional)"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
            />
            <div>
              <label className="block text-sm text-navy-muted mb-1">
                {method === "MANUAL_UPI" ? "UPI payment screenshot" : "Cash receipt photo"}
              </label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                onChange={(e) => onFileSelected(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-navy-muted file:mr-3 file:px-3 file:py-1.5 file:rounded file:border file:border-line file:bg-white file:text-navy file:text-sm"
              />
              {proofPreviewUrl && (
                <img
                  src={proofPreviewUrl}
                  alt="Payment proof preview"
                  className="mt-2 max-h-40 rounded border border-line"
                />
              )}
            </div>
            <p className="text-xs text-navy-muted">
              Proof is required for {method === "MANUAL_UPI" ? "UPI" : "cash"} payments before an Admin/Sub-admin can approve it.
            </p>
          </>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={submit.isPending} disabled={!canSubmit} onClick={() => submit.mutate()}>
            {isManual ? "Submit for approval" : "Pay now"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
