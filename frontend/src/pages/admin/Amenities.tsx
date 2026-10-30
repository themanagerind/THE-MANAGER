import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { amenitiesApi, type AmenityBookingOut } from "@/api/amenities";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";

export function AdminAmenities() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  const amenitiesQuery = useQuery({
    queryKey: ["admin", "amenities"],
    queryFn: () => amenitiesApi.list().then((r) => r.data),
  });
  const bookingsQuery = useQuery({
    queryKey: ["admin", "amenity-bookings"],
    queryFn: () => amenitiesApi.bookings().then((r) => r.data),
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => amenitiesApi.decideBooking(id, approve),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "amenity-bookings"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Amenities</h1>
        <Button onClick={() => setCreating(true)}>Add amenity</Button>
      </div>

      {amenitiesQuery.isLoading && <Loader />}
      {amenitiesQuery.isError && <ErrorState message="Couldn't load amenities." onRetry={() => amenitiesQuery.refetch()} />}
      {amenitiesQuery.data && amenitiesQuery.data.length === 0 && <EmptyState title="No amenities listed yet" />}

      <div className="grid grid-cols-2 gap-3">
        {amenitiesQuery.data?.map((a) => (
          <div key={a.id} className="border border-line rounded p-4">
            <div className="flex items-center justify-between">
              <p className="font-medium text-ink">{a.name}</p>
              {!a.is_active && <Badge status="INACTIVE">Inactive</Badge>}
            </div>
            {a.description && <p className="text-xs text-navy-muted mt-1">{a.description}</p>}
          </div>
        ))}
      </div>

      <div>
        <h2 className="text-sm font-medium text-navy-muted mb-2">Bookings</h2>
        {bookingsQuery.isLoading && <Loader />}
        {bookingsQuery.data && bookingsQuery.data.items.length === 0 && <EmptyState title="No bookings yet" />}
        {bookingsQuery.data && bookingsQuery.data.items.length > 0 && (
          <Table<AmenityBookingOut>
            keyFor={(b) => b.id}
            columns={[
              { header: "Date", render: (b) => new Date(b.booking_date).toLocaleDateString("en-IN") },
              { header: "Time", render: (b) => `${b.start_time}–${b.end_time}` },
              { header: "Status", render: (b) => <Badge status={b.status}>{b.status}</Badge> },
              {
                header: "",
                render: (b) =>
                  b.status === "PENDING" ? (
                    <div className="flex gap-2 justify-end">
                      <Button
                        variant="secondary"
                        loading={decide.isPending && decide.variables?.id === b.id && !decide.variables.approve}
                        onClick={() => decide.mutate({ id: b.id, approve: false })}
                      >
                        Reject
                      </Button>
                      <Button
                        loading={decide.isPending && decide.variables?.id === b.id && decide.variables.approve}
                        onClick={() => decide.mutate({ id: b.id, approve: true })}
                      >
                        Approve
                      </Button>
                    </div>
                  ) : null,
              },
            ]}
            rows={bookingsQuery.data.items}
          />
        )}
      </div>

      {creating && (
        <CreateAmenityModal
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "amenities"] });
          }}
        />
      )}
    </div>
  );
}

function CreateAmenityModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => amenitiesApi.create(name.trim(), description.trim() || undefined),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add this amenity.")),
  });

  return (
    <Modal open onClose={onClose} title="Add amenity">
      <div className="space-y-4">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Clubhouse, Pool, ..." />
        <Input label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>
            Add
          </Button>
        </div>
      </div>
    </Modal>
  );
}
