import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { locationsApi, propertyAdminApi, type SocietyLocationOut } from "@/api/societies";
import { propertiesApi, type PropertyOut } from "@/api/properties";
import { Loader, EmptyState, ErrorState, apiErrorMessage } from "@/components/States";
import { Table } from "@/components/Table";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { HouseType, LocationType } from "@/types/enums";

export function AdminProperties() {
  const queryClient = useQueryClient();
  const [addingLocation, setAddingLocation] = useState(false);
  const [addingProperty, setAddingProperty] = useState(false);

  const locationsQuery = useQuery({
    queryKey: ["admin", "locations"],
    queryFn: () => locationsApi.list().then((r) => r.data),
  });
  const propertiesQuery = useQuery({
    queryKey: ["admin", "properties"],
    queryFn: () => propertiesApi.list().then((r) => r.data),
  });

  const locationName = (locationId: string) =>
    locationsQuery.data?.find((l) => l.id === locationId)?.name ?? "—";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-navy">Properties</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setAddingLocation(true)}>Add wing/row</Button>
          <Button onClick={() => setAddingProperty(true)}>Add property</Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Wings / Rows</h2>
        {locationsQuery.isLoading && <Loader />}
        {locationsQuery.isError && <ErrorState message="Couldn't load locations." onRetry={() => locationsQuery.refetch()} />}
        {locationsQuery.data && locationsQuery.data.length === 0 && <EmptyState title="No wings/rows yet" />}
        {locationsQuery.data && locationsQuery.data.length > 0 && (
          <Table<SocietyLocationOut>
            keyFor={(l) => l.id}
            columns={[
              { header: "Name", render: (l) => l.name },
              { header: "Type", render: (l) => (l.location_type === "WING" ? "Wing" : "Row") },
            ]}
            rows={locationsQuery.data}
          />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-navy-muted">Properties</h2>
        {propertiesQuery.isLoading && <Loader />}
        {propertiesQuery.isError && <ErrorState message="Couldn't load properties." onRetry={() => propertiesQuery.refetch()} />}
        {propertiesQuery.data && propertiesQuery.data.length === 0 && <EmptyState title="No properties yet" />}
        {propertiesQuery.data && propertiesQuery.data.length > 0 && (
          <Table<PropertyOut>
            keyFor={(p) => p.id}
            columns={[
              { header: "House #", render: (p) => p.house_number },
              { header: "Wing/Row", render: (p) => locationName(p.location_id) },
              { header: "Type", render: (p) => (p.house_type === "FLAT" ? "Flat" : "Bungalow") },
              { header: "Floor", render: (p) => p.floor_number ?? "—" },
              { header: "Status", render: (p) => p.status },
            ]}
            rows={propertiesQuery.data}
          />
        )}
      </section>

      {addingLocation && (
        <AddLocationModal
          onClose={() => setAddingLocation(false)}
          onSuccess={() => {
            setAddingLocation(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "locations"] });
          }}
        />
      )}

      {addingProperty && (
        <AddPropertyModal
          locations={locationsQuery.data ?? []}
          onClose={() => setAddingProperty(false)}
          onSuccess={() => {
            setAddingProperty(false);
            void queryClient.invalidateQueries({ queryKey: ["admin", "properties"] });
          }}
        />
      )}
    </div>
  );
}

function AddLocationModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [locationType, setLocationType] = useState<LocationType>("WING");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => locationsApi.create(name, locationType),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not create wing/row.")),
  });

  return (
    <Modal open onClose={onClose} title="Add wing/row">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Type</label>
          <div className="flex gap-2">
            {(["WING", "ROW"] as LocationType[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setLocationType(opt)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  locationType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "WING" ? "Wing" : "Row"}
              </button>
            ))}
          </div>
        </div>
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Wing A" />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>Create</Button>
        </div>
      </div>
    </Modal>
  );
}

function AddPropertyModal({
  locations, onClose, onSuccess,
}: { locations: SocietyLocationOut[]; onClose: () => void; onSuccess: () => void }) {
  const [houseType, setHouseType] = useState<HouseType>("FLAT");
  const [locationId, setLocationId] = useState("");
  const [houseNumber, setHouseNumber] = useState("");
  const [floorNumber, setFloorNumber] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Section 11: FLAT properties live in a WING, BUNGALOW properties live in a ROW.
  const filteredLocations = locations.filter((l) =>
    houseType === "FLAT" ? l.location_type === "WING" : l.location_type === "ROW"
  );

  const create = useMutation({
    mutationFn: () =>
      propertyAdminApi.create(locationId, houseNumber, houseType, floorNumber ? Number(floorNumber) : undefined),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Could not create property.")),
  });

  const canSubmit = !!locationId && !!houseNumber.trim() && (houseType === "BUNGALOW" || !!floorNumber);

  return (
    <Modal open onClose={onClose} title="Add property">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Type</label>
          <div className="flex gap-2">
            {(["FLAT", "BUNGALOW"] as HouseType[]).map((opt) => (
              <button
                key={opt}
                onClick={() => { setHouseType(opt); setLocationId(""); }}
                className={`px-3 py-1.5 rounded text-sm border ${
                  houseType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "FLAT" ? "Flat" : "Bungalow"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-navy-muted mb-1">
            {houseType === "FLAT" ? "Wing" : "Row"}
          </label>
          <select
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
          >
            <option value="">Select {houseType === "FLAT" ? "a wing" : "a row"}</option>
            {filteredLocations.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
          {filteredLocations.length === 0 && (
            <p className="text-xs text-navy-muted mt-1">
              No {houseType === "FLAT" ? "wings" : "rows"} yet — add one first.
            </p>
          )}
        </div>

        <Input label="House number" value={houseNumber} onChange={(e) => setHouseNumber(e.target.value)} />

        {houseType === "FLAT" && (
          <Input
            label="Floor number"
            type="number"
            value={floorNumber}
            onChange={(e) => setFloorNumber(e.target.value)}
          />
        )}
        {houseType === "BUNGALOW" && (
          <Input
            label="Floor number (optional)"
            type="number"
            value={floorNumber}
            onChange={(e) => setFloorNumber(e.target.value)}
          />
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!canSubmit} onClick={() => create.mutate()}>Create</Button>
        </div>
      </div>
    </Modal>
  );
}
