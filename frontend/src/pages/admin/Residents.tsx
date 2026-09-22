import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { residentsApi, type ResidentOut } from "@/api/residents";
import { propertiesApi, type PropertyOut } from "@/api/properties";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { RelationshipType } from "@/types/enums";

export function AdminResidents() {
  const queryClient = useQueryClient();
  const [linkingResident, setLinkingResident] = useState<ResidentOut | null>(null);
  const [rejectingResident, setRejectingResident] = useState<ResidentOut | null>(null);

  const pendingQuery = useQuery({
    queryKey: ["admin", "residents", "pending"],
    queryFn: () => residentsApi.pending().then((r) => r.data),
  });

  const approve = useMutation({
    mutationFn: (id: string) => residentsApi.decideApproval(id, true),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "residents", "pending"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-navy">Residents</h1>

      {pendingQuery.isLoading && <Loader />}
      {pendingQuery.isError && <ErrorState message="Couldn't load residents." onRetry={() => pendingQuery.refetch()} />}
      {pendingQuery.data && pendingQuery.data.length === 0 && (
        <EmptyState title="No pending resident approvals" />
      )}
      {pendingQuery.data && pendingQuery.data.length > 0 && (
        <Table<ResidentOut>
          keyFor={(r) => r.id}
          columns={[
            { header: "Name", render: (r) => r.full_name },
            { header: "Mobile", render: (r) => r.mobile },
            { header: "Email", render: (r) => r.email ?? "—" },
            {
              header: "",
              render: (r) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="secondary" onClick={() => setRejectingResident(r)}>
                    Reject
                  </Button>
                  <Button onClick={() => approve.mutate(r.id)} loading={approve.isPending}>
                    Approve
                  </Button>
                  <Button variant="secondary" onClick={() => setLinkingResident(r)}>
                    Link property
                  </Button>
                </div>
              ),
            },
          ]}
          rows={pendingQuery.data}
        />
      )}

      {linkingResident && (
        <LinkPropertyModal
          resident={linkingResident}
          onClose={() => setLinkingResident(null)}
          onSuccess={() => setLinkingResident(null)}
        />
      )}

      {rejectingResident && (
        <RejectModal
          resident={rejectingResident}
          onClose={() => setRejectingResident(null)}
          onSuccess={() => {
            setRejectingResident(null);
            void queryClient.invalidateQueries({ queryKey: ["admin", "residents", "pending"] });
          }}
        />
      )}
    </div>
  );
}

function LinkPropertyModal({
  resident, onClose, onSuccess,
}: { resident: ResidentOut; onClose: () => void; onSuccess: () => void }) {
  const [propertyId, setPropertyId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipType>("OWNER");
  const [error, setError] = useState<string | null>(null);

  const propertiesQuery = useQuery({
    queryKey: ["admin", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });

  const link = useMutation({
    mutationFn: () => residentsApi.linkProperty(propertyId, resident.id, relationshipType),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not link property.")),
  });

  return (
    <Modal open onClose={onClose} title={`Link property — ${resident.full_name}`}>
      <div className="space-y-4">
        {propertiesQuery.isLoading && <Loader />}
        {propertiesQuery.data && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Property</label>
            <select
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
              value={propertyId}
              onChange={(e) => setPropertyId(e.target.value)}
            >
              <option value="">Select a property</option>
              {propertiesQuery.data.map((p: PropertyOut) => (
                <option key={p.id} value={p.id}>
                  {p.house_number} ({p.house_type})
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="block text-sm text-navy-muted mb-1">Relationship</label>
          <div className="flex gap-2">
            {(["OWNER", "TENANT"] as RelationshipType[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setRelationshipType(opt)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  relationshipType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "OWNER" ? "Owner" : "Tenant"}
              </button>
            ))}
          </div>
          {relationshipType === "TENANT" && (
            <p className="text-xs text-navy-muted mt-1">
              Section 12: the property's Owner record must already exist and be linked separately.
            </p>
          )}
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={link.isPending} disabled={!propertyId} onClick={() => link.mutate()}>
            Link
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function RejectModal({
  resident, onClose, onSuccess,
}: { resident: ResidentOut; onClose: () => void; onSuccess: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reject = useMutation({
    mutationFn: () => residentsApi.decideApproval(resident.id, false, reason),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not reject resident.")),
  });

  return (
    <Modal open onClose={onClose} title={`Reject — ${resident.full_name}`}>
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
