import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { visitorsApi, type VisitorOut } from "@/api/visitors";
import { useActiveProperty } from "@/hooks/useActiveProperty";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { PropertySelector } from "@/components/PropertySelector";

export function ResidentVisitors() {
  const { activePropertyId, setActivePropertyId, options, hasMultipleProperties } = useActiveProperty();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const visitorsQuery = useQuery({
    queryKey: ["visitors", "mine"],
    queryFn: () => visitorsApi.mine().then((r) => r.data),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => visitorsApi.updateStatus(id, "CANCELLED"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["visitors", "mine"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-navy">Visitors</h1>
        <Button onClick={() => setShowCreate(true)}>Pre-approve visitor</Button>
      </div>

      {visitorsQuery.isLoading && <Loader />}
      {visitorsQuery.isError && <ErrorState message="Couldn't load visitors." onRetry={() => visitorsQuery.refetch()} />}
      {visitorsQuery.data && visitorsQuery.data.items.length === 0 && (
        <EmptyState title="No visitors yet" description="Pre-approve someone so security knows to expect them." />
      )}
      {visitorsQuery.data && visitorsQuery.data.items.length > 0 && (
        <Table<VisitorOut>
          keyFor={(v) => v.id}
          columns={[
            { header: "Name", render: (v) => v.visitor_name },
            { header: "Visit date", render: (v) => new Date(v.visit_date).toLocaleDateString("en-IN") },
            { header: "Status", render: (v) => <Badge status={v.status}>{v.status.replace("_", " ")}</Badge> },
            {
              header: "",
              render: (v) =>
                (v.status === "PRE_APPROVED" || v.status === "EXPECTED") ? (
                  <button
                    onClick={() => cancelMutation.mutate(v.id)}
                    className="text-sm text-danger underline"
                  >
                    Cancel
                  </button>
                ) : null,
            },
          ]}
          rows={visitorsQuery.data.items}
        />
      )}

      {showCreate && (
        <PreApproveModal
          properties={options}
          activePropertyId={activePropertyId}
          hasMultipleProperties={hasMultipleProperties}
          onPropertyChange={setActivePropertyId}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            void queryClient.invalidateQueries({ queryKey: ["visitors", "mine"] });
          }}
        />
      )}
    </div>
  );
}

function PreApproveModal({
  properties, activePropertyId, hasMultipleProperties, onPropertyChange, onClose, onSuccess,
}: {
  properties: { property_id: string; label: string }[];
  activePropertyId: string | null;
  hasMultipleProperties: boolean;
  onPropertyChange: (id: string) => void;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [visitDate, setVisitDate] = useState(new Date().toISOString().slice(0, 10));
  const [purpose, setPurpose] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      visitorsApi.preApprove({
        property_id: activePropertyId!, visitor_name: name, visitor_mobile: mobile || undefined,
        visit_date: visitDate, purpose: purpose || undefined,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't pre-approve the visitor.")),
  });

  return (
    <Modal open onClose={onClose} title="Pre-approve a visitor">
      <div className="space-y-4">
        {hasMultipleProperties && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Property</label>
            <PropertySelector properties={properties} activePropertyId={activePropertyId} onChange={onPropertyChange} />
          </div>
        )}
        <Input label="Visitor name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Mobile (optional)" value={mobile} onChange={(e) => setMobile(e.target.value)} />
        <Input label="Visit date" type="date" value={visitDate} onChange={(e) => setVisitDate(e.target.value)} />
        <Input label="Purpose (optional)" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!name || !visitDate} onClick={() => create.mutate()}>
            Pre-approve
          </Button>
        </div>
      </div>
    </Modal>
  );
}
