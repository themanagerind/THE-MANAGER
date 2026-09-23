import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { societiesApi, type SocietyOut } from "@/api/societies";
import { adminsApi, type AdminOut } from "@/api/admins";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { LocationType } from "@/types/enums";

/**
 * A society only ever comes into existence here — created directly by the
 * Platform Owner (ACTIVE immediately, no separate approval step). Admin
 * signup (the Signup page's "As an Admin" option) targets an existing
 * society by its code and waits for approval below.
 */
export function PlatformSocieties() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<SocietyOut | null>(null);

  const societiesQuery = useQuery({
    queryKey: ["platform", "societies"],
    queryFn: () => societiesApi.list().then((r) => r.data),
  });

  const pendingAdminsQuery = useQuery({
    queryKey: ["platform", "admins", "pending"],
    queryFn: () => adminsApi.pending().then((r) => r.data),
  });

  const toggleStatus = useMutation({
    mutationFn: (society: SocietyOut) =>
      societiesApi.updateStatus(society.id, society.status === "SUSPENDED" ? "ACTIVE" : "SUSPENDED"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["platform", "societies"] }),
  });

  const decideAdmin = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => adminsApi.decideApproval(id, approve),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["platform", "admins", "pending"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold text-navy">Societies</h1>
        <Button onClick={() => setCreating(true)}>Create society</Button>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">All societies</h2>
        {societiesQuery.isLoading && <Loader />}
        {societiesQuery.isError && (
          <ErrorState message="Couldn't load societies." onRetry={() => societiesQuery.refetch()} />
        )}
        {societiesQuery.data && societiesQuery.data.length === 0 && (
          <EmptyState title="No societies yet" description="Create the first one to get started." />
        )}
        {societiesQuery.data && societiesQuery.data.length > 0 && (
          <Table<SocietyOut>
            keyFor={(s) => s.id}
            columns={[
              { header: "Name", render: (s) => <span className="font-medium">{s.name}</span> },
              { header: "Code", render: (s) => s.code },
              { header: "City", render: (s) => s.city ?? "—" },
              { header: "Status", render: (s) => <Badge status={s.status}>{s.status}</Badge> },
              {
                header: "",
                render: (s) => (
                  <div className="flex gap-2 justify-end">
                    <Button variant="secondary" onClick={() => setEditing(s)}>Edit</Button>
                    {s.status !== "PENDING" && (
                      <Button
                        variant="secondary"
                        loading={toggleStatus.isPending && toggleStatus.variables?.id === s.id}
                        onClick={() => toggleStatus.mutate(s)}
                      >
                        {s.status === "SUSPENDED" ? "Reactivate" : "Suspend"}
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
            rows={societiesQuery.data}
          />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Pending Admin signups</h2>
        {pendingAdminsQuery.isLoading && <Loader />}
        {pendingAdminsQuery.isError && (
          <ErrorState message="Couldn't load pending admins." onRetry={() => pendingAdminsQuery.refetch()} />
        )}
        {pendingAdminsQuery.data && pendingAdminsQuery.data.length === 0 && (
          <EmptyState title="No pending Admin signups" />
        )}
        {pendingAdminsQuery.data && pendingAdminsQuery.data.length > 0 && (
          <Table<AdminOut>
            keyFor={(a) => a.id}
            columns={[
              { header: "Name", render: (a) => a.full_name },
              { header: "Mobile", render: (a) => a.mobile },
              {
                header: "Society",
                render: (a) => societiesQuery.data?.find((s) => s.id === a.society_id)?.name ?? "—",
              },
              {
                header: "",
                render: (a) => (
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="secondary"
                      loading={decideAdmin.isPending && decideAdmin.variables?.id === a.id && !decideAdmin.variables?.approve}
                      onClick={() => decideAdmin.mutate({ id: a.id, approve: false })}
                    >
                      Reject
                    </Button>
                    <Button
                      loading={decideAdmin.isPending && decideAdmin.variables?.id === a.id && decideAdmin.variables?.approve}
                      onClick={() => decideAdmin.mutate({ id: a.id, approve: true })}
                    >
                      Approve
                    </Button>
                  </div>
                ),
              },
            ]}
            rows={pendingAdminsQuery.data}
          />
        )}
      </section>

      {creating && (
        <CreateSocietyModal
          onClose={() => setCreating(false)}
          onSuccess={() => void queryClient.invalidateQueries({ queryKey: ["platform", "societies"] })}
        />
      )}

      {editing && (
        <EditSocietyModal
          society={editing}
          onClose={() => setEditing(null)}
          onSuccess={() => {
            setEditing(null);
            void queryClient.invalidateQueries({ queryKey: ["platform", "societies"] });
          }}
        />
      )}
    </div>
  );
}

interface LocationRow {
  name: string;
  location_type: LocationType;
}

function CreateSocietyModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [createdCode, setCreatedCode] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      societiesApi.create({
        name: name.trim(), city: city.trim(), state: state.trim(),
        address: address.trim(), pincode: pincode.trim(),
        locations: locations.filter((l) => l.name.trim()).map((l) => ({ name: l.name.trim(), location_type: l.location_type })),
      }),
    onSuccess: (r) => {
      onSuccess();
      setCreatedCode(r.data.code);
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't create the society.")),
  });

  function addLocationRow() {
    setLocations((prev) => [...prev, { name: "", location_type: "WING" }]);
  }
  function updateLocationRow(index: number, patch: Partial<LocationRow>) {
    setLocations((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }
  function removeLocationRow(index: number) {
    setLocations((prev) => prev.filter((_, i) => i !== index));
  }

  const canSubmit = [name, city, state, address, pincode].every((f) => f.trim().length > 0);

  if (createdCode) {
    return (
      <Modal open onClose={onClose} title="Society created">
        <div className="space-y-4">
          <p className="text-sm text-ink">
            <span className="font-medium">{name}</span> is now active. Its society code is:
          </p>
          <p className="text-2xl font-bold text-navy tracking-wide text-center py-3 bg-paper rounded border border-line">
            {createdCode}
          </p>
          <p className="text-xs text-navy-muted">
            Share this code with the society's Admin and Residents so they can find it when signing up.
          </p>
          <div className="flex justify-end pt-2">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open onClose={onClose} title="Create society">
      <div className="space-y-4">
        <Input label="Society name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <p className="text-xs text-navy-muted -mt-2">
          The society code is generated automatically once created — no need to make one up.
        </p>
        <Input label="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input label="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Input label="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
        <Input label="Pincode" value={pincode} onChange={(e) => setPincode(e.target.value)} />

        <div className="border-t border-line pt-3">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm text-navy-muted">Wings/Rows (optional)</label>
            <Button variant="secondary" onClick={addLocationRow}>Add location</Button>
          </div>
          {locations.length === 0 && (
            <p className="text-xs text-navy-muted">
              Skip this if you don't have the details yet — the Admin can add Wings/Rows later.
            </p>
          )}
          <div className="space-y-2">
            {locations.map((loc, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  value={loc.name}
                  onChange={(e) => updateLocationRow(i, { name: e.target.value })}
                  placeholder="e.g. Wing A"
                  className="flex-1 px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                />
                <select
                  value={loc.location_type}
                  onChange={(e) => updateLocationRow(i, { location_type: e.target.value as LocationType })}
                  className="px-2 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                >
                  <option value="WING">Wing</option>
                  <option value="ROW">Row</option>
                </select>
                <button
                  type="button"
                  onClick={() => removeLocationRow(i)}
                  aria-label="Remove location"
                  className="text-navy-muted hover:text-danger text-lg leading-none px-1"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!canSubmit} onClick={() => create.mutate()}>
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function EditSocietyModal({
  society, onClose, onSuccess,
}: { society: SocietyOut; onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState(society.name);
  const [city, setCity] = useState(society.city ?? "");
  const [state, setState] = useState(society.state ?? "");
  const [address, setAddress] = useState(society.address ?? "");
  const [pincode, setPincode] = useState(society.pincode ?? "");
  const [error, setError] = useState<string | null>(null);

  const update = useMutation({
    mutationFn: () =>
      societiesApi.update(society.id, {
        name: name.trim(), city: city.trim(), state: state.trim(),
        address: address.trim(), pincode: pincode.trim(),
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update the society.")),
  });

  const canSubmit = [name, city, state, address, pincode].every((f) => f.trim().length > 0);

  return (
    <Modal open onClose={onClose} title={`Edit — ${society.name}`}>
      <div className="space-y-4">
        <Input label="Society name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <p className="text-xs text-navy-muted -mt-2">Code: {society.code} (fixed, not editable)</p>
        <Input label="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input label="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Input label="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
        <Input label="Pincode" value={pincode} onChange={(e) => setPincode(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={update.isPending} disabled={!canSubmit} onClick={() => update.mutate()}>
            Save
          </Button>
        </div>
      </div>
    </Modal>
  );
}
