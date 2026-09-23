import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { residentsApi, subadminsApi, type ResidentOut, type SubAdminScopeOut } from "@/api/residents";
import { propertiesApi, type PropertyOut } from "@/api/properties";
import { locationsApi, type SocietyLocationOut } from "@/api/societies";
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
  const [promotingResident, setPromotingResident] = useState<ResidentOut | null>(null);

  const pendingQuery = useQuery({
    queryKey: ["admin", "residents", "pending"],
    queryFn: () => residentsApi.pending().then((r) => r.data),
  });

  const activeResidentsQuery = useQuery({
    queryKey: ["admin", "residents", "active"],
    queryFn: () => residentsApi.list("ACTIVE").then((r) => r.data),
  });

  const approve = useMutation({
    mutationFn: (id: string) => residentsApi.decideApproval(id, true),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "residents", "pending"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "residents", "active"] });
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Residents</h1>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Pending approvals</h2>
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
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Active residents</h2>
        {activeResidentsQuery.isLoading && <Loader />}
        {activeResidentsQuery.isError && (
          <ErrorState message="Couldn't load residents." onRetry={() => activeResidentsQuery.refetch()} />
        )}
        {activeResidentsQuery.data && activeResidentsQuery.data.length === 0 && (
          <EmptyState title="No active residents yet" />
        )}
        {activeResidentsQuery.data && activeResidentsQuery.data.length > 0 && (
          <Table<ResidentOut>
            keyFor={(r) => r.id}
            columns={[
              { header: "Name", render: (r) => r.full_name },
              { header: "Mobile", render: (r) => r.mobile },
              { header: "Email", render: (r) => r.email ?? "—" },
              {
                header: "",
                render: (r) => (
                  <div className="flex justify-end">
                    <Button variant="secondary" onClick={() => setPromotingResident(r)}>
                      Sub-admin
                    </Button>
                  </div>
                ),
              },
            ]}
            rows={activeResidentsQuery.data}
          />
        )}
      </section>

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

      {promotingResident && (
        <PromoteModal resident={promotingResident} onClose={() => setPromotingResident(null)} />
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

/**
 * Promotes a Resident to Sub-admin of one or more Wings/Rows (Section 6/7)
 * — backend has supported this since before this session (POST /subadmins/
 * promote), but no UI ever called it. Re-running promote on someone
 * already a Sub-admin just adds more scope (subadmin_service.
 * promote_to_subadmin never duplicates the SUB_ADMIN role), so "assign
 * more" and "first promotion" are the same action here.
 */
function PromoteModal({ resident, onClose }: { resident: ResidentOut; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["admin", "locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
  });

  const scopesQueryKey = ["admin", "subadmins", resident.id, "scopes"];
  const scopesQuery = useQuery({
    queryKey: scopesQueryKey,
    queryFn: () => subadminsApi.scopes(resident.id).then((r) => r.data),
  });

  const assign = useMutation({
    mutationFn: () => subadminsApi.promote(resident.id, Array.from(selected)),
    onSuccess: () => {
      setSelected(new Set());
      setError(null);
      void queryClient.invalidateQueries({ queryKey: scopesQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Could not assign scope.")),
  });

  const revoke = useMutation({
    mutationFn: (scopeId: string) => subadminsApi.revokeScope(scopeId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: scopesQueryKey }),
    onError: (e) => setError(apiErrorMessage(e, "Could not remove scope.")),
  });

  function toggle(locationId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(locationId)) next.delete(locationId);
      else next.add(locationId);
      return next;
    });
  }

  const locations = locationsQuery.data ?? [];
  const activeScopes: SubAdminScopeOut[] = scopesQuery.data ?? [];
  const assignedLocationIds = new Set(activeScopes.map((s) => s.location_id));
  const locationsById = new Map(locations.map((l) => [l.id, l] as [string, SocietyLocationOut]));
  const unassignedLocations = locations.filter((l) => !assignedLocationIds.has(l.id));

  return (
    <Modal open onClose={onClose} title={`Sub-admin — ${resident.full_name}`}>
      <div className="space-y-4">
        {(locationsQuery.isLoading || scopesQuery.isLoading) && <Loader />}

        {activeScopes.length > 0 && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Currently scoped to</label>
            <ul className="space-y-1">
              {activeScopes.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between text-sm text-ink border border-line rounded px-3 py-1.5"
                >
                  <span>{locationsById.get(s.location_id)?.name ?? "—"}</span>
                  <button
                    type="button"
                    onClick={() => revoke.mutate(s.id)}
                    disabled={revoke.isPending}
                    className="text-xs text-navy-muted hover:text-danger underline"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {unassignedLocations.length > 0 && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">
              {activeScopes.length > 0 ? "Add more Wings/Rows" : "Assign Wings/Rows"}
            </label>
            <div className="space-y-1 max-h-48 overflow-y-auto border border-line rounded p-2">
              {unassignedLocations.map((l) => (
                <label key={l.id} className="flex items-center gap-2 text-sm text-ink">
                  <input type="checkbox" checked={selected.has(l.id)} onChange={() => toggle(l.id)} />
                  {l.name} ({l.location_type === "WING" ? "Wing" : "Row"})
                </label>
              ))}
            </div>
          </div>
        )}

        {locations.length > 0 && unassignedLocations.length === 0 && (
          <p className="text-xs text-navy-muted">Already scoped to every Wing/Row in this society.</p>
        )}
        {!locationsQuery.isLoading && locations.length === 0 && (
          <p className="text-xs text-navy-muted">No Wings/Rows on record yet — add them from the Properties page.</p>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Done</Button>
          <Button loading={assign.isPending} disabled={selected.size === 0} onClick={() => assign.mutate()}>
            Assign
          </Button>
        </div>
      </div>
    </Modal>
  );
}
