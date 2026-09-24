import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { amenitiesApi, type AmenityBookingOut, type AmenitySlotOut } from "@/api/amenities";
import { useActiveProperty } from "@/hooks/useActiveProperty";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Badge } from "@/components/Badge";
import { Table } from "@/components/Table";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { PropertySelector } from "@/components/PropertySelector";

export function ResidentAmenities() {
  const { activePropertyId, setActivePropertyId, options, hasMultipleProperties } = useActiveProperty();
  const queryClient = useQueryClient();
  const [bookingAmenityId, setBookingAmenityId] = useState<string | null>(null);

  const amenitiesQuery = useQuery({ queryKey: ["amenities"], queryFn: () => amenitiesApi.list().then((r) => r.data) });
  const bookingsQuery = useQuery({ queryKey: ["amenity-bookings", "mine"], queryFn: () => amenitiesApi.bookings().then((r) => r.data) });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-navy">Amenities</h1>

      {amenitiesQuery.isLoading && <Loader />}
      {amenitiesQuery.isError && <ErrorState message="Couldn't load amenities." />}
      {amenitiesQuery.data && amenitiesQuery.data.length === 0 && <EmptyState title="No amenities listed yet" />}

      <div className="grid grid-cols-2 gap-3">
        {amenitiesQuery.data?.filter((a) => a.is_active).map((a) => (
          <div key={a.id} className="border border-line rounded p-4">
            <p className="font-medium text-ink mb-1">{a.name}</p>
            {a.description && <p className="text-xs text-navy-muted mb-3">{a.description}</p>}
            <Button variant="secondary" onClick={() => setBookingAmenityId(a.id)}>Book</Button>
          </div>
        ))}
      </div>

      <div>
        <h2 className="text-sm font-medium text-navy-muted mb-2">Your bookings</h2>
        {bookingsQuery.data && bookingsQuery.data.items.length === 0 && <EmptyState title="No bookings yet" />}
        {bookingsQuery.data && bookingsQuery.data.items.length > 0 && (
          <Table<AmenityBookingOut>
            keyFor={(b) => b.id}
            columns={[
              { header: "Date", render: (b) => new Date(b.booking_date).toLocaleDateString("en-IN") },
              { header: "Time", render: (b) => `${b.start_time}–${b.end_time}` },
              { header: "Status", render: (b) => <Badge status={b.status}>{b.status}</Badge> },
            ]}
            rows={bookingsQuery.data.items}
          />
        )}
      </div>

      {bookingAmenityId && (
        <BookingModal
          amenityId={bookingAmenityId}
          properties={options}
          activePropertyId={activePropertyId}
          hasMultipleProperties={hasMultipleProperties}
          onPropertyChange={setActivePropertyId}
          onClose={() => setBookingAmenityId(null)}
          onSuccess={() => {
            setBookingAmenityId(null);
            void queryClient.invalidateQueries({ queryKey: ["amenity-bookings", "mine"] });
          }}
        />
      )}
    </div>
  );
}

function BookingModal({
  amenityId, properties, activePropertyId, hasMultipleProperties, onPropertyChange, onClose, onSuccess,
}: {
  amenityId: string;
  properties: { property_id: string; label: string }[];
  activePropertyId: string | null;
  hasMultipleProperties: boolean;
  onPropertyChange: (id: string) => void;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [startTime, setStartTime] = useState("10:00");
  const [endTime, setEndTime] = useState("11:00");
  const [error, setError] = useState<string | null>(null);

  const slotsQuery = useQuery({
    queryKey: ["amenity-slots", amenityId, date],
    queryFn: () => amenitiesApi.occupiedSlots(amenityId, date).then((r) => r.data),
  });

  const book = useMutation({
    mutationFn: () =>
      amenitiesApi.createBooking({
        amenity_id: amenityId, property_id: activePropertyId!,
        booking_date: date, start_time: startTime, end_time: endTime,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't create the booking. That slot may already be booked.")),
  });

  const validRange = startTime < endTime;
  // Same overlap rule the backend enforces (start1 < end2 && start2 < end1)
  // — checked here too so the Resident sees the conflict before submitting,
  // not just after a 409. The API returns "HH:MM:SS" while these inputs
  // hold "HH:MM" — comparing the raw strings breaks ("11:00" < "11:00:00"
  // is true), so both sides are truncated to "HH:MM" first.
  const overlapsExistingSlot = (slotsQuery.data ?? []).some(
    (s) => startTime < s.end_time.slice(0, 5) && s.start_time.slice(0, 5) < endTime
  );

  return (
    <Modal open onClose={onClose} title="Book amenity">
      <div className="space-y-4">
        {hasMultipleProperties && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Property</label>
            <PropertySelector properties={properties} activePropertyId={activePropertyId} onChange={onPropertyChange} />
          </div>
        )}
        <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Start time" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          <Input label="End time" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} error={!validRange ? "Must be after start time" : undefined} />
        </div>

        <div>
          <h3 className="text-xs font-medium text-navy-muted mb-1">Already booked on this date</h3>
          {slotsQuery.isLoading && <Loader />}
          {slotsQuery.data && slotsQuery.data.length === 0 && (
            <p className="text-xs text-navy-muted">No bookings yet — any slot is free.</p>
          )}
          {slotsQuery.data && slotsQuery.data.length > 0 && (
            <ul className="space-y-1">
              {slotsQuery.data.map((s: AmenitySlotOut, i: number) => (
                <li key={i} className="text-xs text-navy-muted flex items-center gap-2">
                  <span>{s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)}</span>
                  <Badge status={s.status}>{s.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </div>

        {validRange && overlapsExistingSlot && (
          <p className="text-sm text-danger">This time overlaps a slot that's already booked or pending. Pick another time.</p>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={book.isPending} disabled={!validRange || overlapsExistingSlot} onClick={() => book.mutate()}>
            Request booking
          </Button>
        </div>
      </div>
    </Modal>
  );
}
