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

/**
 * A society only ever comes into existence here — created directly by the
 * Platform Owner (ACTIVE immediately, no separate approval step). Admin
 * signup (the Signup page's "As an Admin" option) targets an existing
 * society by its code and waits for approval below.
 */
export function PlatformSocieties() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

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
                render: (s) =>
                  s.status === "PENDING" ? null : (
                    <div className="flex justify-end">
                      <Button
                        variant="secondary"
                        loading={toggleStatus.isPending && toggleStatus.variables?.id === s.id}
                        onClick={() => toggleStatus.mutate(s)}
                      >
                        {s.status === "SUSPENDED" ? "Reactivate" : "Suspend"}
                      </Button>
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
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["platform", "societies"] });
          }}
        />
      )}
    </div>
  );
}

function CreateSocietyModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      societiesApi.create({
        name, code,
        city: city || undefined, state: state || undefined,
        address: address || undefined, pincode: pincode || undefined,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't create the society.")),
  });

  return (
    <Modal open onClose={onClose} title="Create society">
      <div className="space-y-4">
        <Input label="Society name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <Input
          label="Society code"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
        />
        <p className="text-xs text-navy-muted -mt-2">
          Share this code with the society's Admin and Residents so they can find it when signing up.
        </p>
        <Input label="City (optional)" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input label="State (optional)" value={state} onChange={(e) => setState(e.target.value)} />
        <Input label="Address (optional)" value={address} onChange={(e) => setAddress(e.target.value)} />
        <Input label="Pincode (optional)" value={pincode} onChange={(e) => setPincode(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!name.trim() || !code.trim()} onClick={() => create.mutate()}>
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}
