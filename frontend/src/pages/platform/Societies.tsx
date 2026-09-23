import { useState } from "react";
import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { societiesApi, type SocietyLocationOut, type SocietyOut } from "@/api/societies";
import type { PropertyOut } from "@/api/properties";
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
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createdCode, setCreatedCode] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      societiesApi.create({
        name: name.trim(), city: city.trim(), state: state.trim(),
        address: address.trim(), pincode: pincode.trim(),
        locations: locations.filter((l) => l.name.trim()).map((l) => ({ name: l.name.trim(), location_type: l.location_type })),
        latitude: latitude.trim() ? Number(latitude) : undefined,
        longitude: longitude.trim() ? Number(longitude) : undefined,
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

  const gpsBothOrNeither = !!latitude.trim() === !!longitude.trim();
  const canSubmit = [name, city, state, address, pincode].every((f) => f.trim().length > 0) && gpsBothOrNeither;

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

        <div className="border-t border-line pt-3">
          <label className="block text-sm text-navy-muted mb-2">GPS location (optional)</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Latitude" type="number" step="any" value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
            />
            <Input
              label="Longitude" type="number" step="any" value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
            />
          </div>
          {!gpsBothOrNeither && (
            <p className="text-xs text-danger mt-1">Provide both latitude and longitude, or leave both blank.</p>
          )}
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
  const queryClient = useQueryClient();
  const [name, setName] = useState(society.name);
  const [city, setCity] = useState(society.city ?? "");
  const [state, setState] = useState(society.state ?? "");
  const [address, setAddress] = useState(society.address ?? "");
  const [pincode, setPincode] = useState(society.pincode ?? "");
  const [latitude, setLatitude] = useState(society.latitude != null ? String(society.latitude) : "");
  const [longitude, setLongitude] = useState(society.longitude != null ? String(society.longitude) : "");
  const [error, setError] = useState<string | null>(null);
  const [newLocationName, setNewLocationName] = useState("");
  const [newLocationType, setNewLocationType] = useState<LocationType>("WING");
  const [locationError, setLocationError] = useState<string | null>(null);

  const locationsQueryKey = ["platform", "societies", society.id, "locations"];
  const locationsQuery = useQuery({
    queryKey: locationsQueryKey,
    queryFn: () => societiesApi.listLocations(society.id).then((r) => r.data),
  });

  const update = useMutation({
    mutationFn: () =>
      societiesApi.update(society.id, {
        name: name.trim(), city: city.trim(), state: state.trim(),
        address: address.trim(), pincode: pincode.trim(),
        latitude: latitude.trim() ? Number(latitude) : undefined,
        longitude: longitude.trim() ? Number(longitude) : undefined,
      }),
    onSuccess,
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update the society.")),
  });

  const addLocation = useMutation({
    mutationFn: () => societiesApi.addLocation(society.id, newLocationName.trim(), newLocationType),
    onSuccess: () => {
      setNewLocationName("");
      setLocationError(null);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setLocationError(apiErrorMessage(e, "Couldn't add the wing/row.")),
  });

  const gpsBothOrNeither = !!latitude.trim() === !!longitude.trim();
  const canSubmit = [name, city, state, address, pincode].every((f) => f.trim().length > 0) && gpsBothOrNeither;

  return (
    <Modal open onClose={onClose} title={`Edit — ${society.name}`}>
      <div className="space-y-4">
        <Input label="Society name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <p className="text-xs text-navy-muted -mt-2">Code: {society.code} (fixed, not editable)</p>
        <Input label="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input label="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Input label="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
        <Input label="Pincode" value={pincode} onChange={(e) => setPincode(e.target.value)} />

        <div>
          <label className="block text-sm text-navy-muted mb-1">GPS location (optional)</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Latitude" type="number" step="any" value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
            />
            <Input
              label="Longitude" type="number" step="any" value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
            />
          </div>
          {!gpsBothOrNeither && (
            <p className="text-xs text-danger mt-1">Provide both latitude and longitude, or leave both blank.</p>
          )}
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={update.isPending} disabled={!canSubmit} onClick={() => update.mutate()}>
            Save
          </Button>
        </div>

        <div className="border-t border-line pt-3">
          <label className="block text-sm text-navy-muted mb-2">Wings/Rows</label>
          {locationsQuery.isLoading && <Loader />}
          {locationsQuery.isError && (
            <ErrorState message="Couldn't load wings/rows." onRetry={() => locationsQuery.refetch()} />
          )}
          {locationsQuery.data && locationsQuery.data.length === 0 && (
            <p className="text-xs text-navy-muted mb-2">No wings/rows yet.</p>
          )}
          {locationsQuery.data && locationsQuery.data.length > 0 && (
            <ul className="space-y-1 mb-2">
              {locationsQuery.data.map((l: SocietyLocationOut) => (
                <LocationRow key={l.id} societyId={society.id} location={l} locationsQueryKey={locationsQueryKey} />
              ))}
            </ul>
          )}
          <div className="flex gap-2 items-center">
            <input
              value={newLocationName}
              onChange={(e) => setNewLocationName(e.target.value)}
              placeholder="e.g. Wing A"
              className="flex-1 px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            />
            <select
              value={newLocationType}
              onChange={(e) => setNewLocationType(e.target.value as LocationType)}
              className="px-2 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            >
              <option value="WING">Wing</option>
              <option value="ROW">Row</option>
            </select>
            <Button
              variant="secondary"
              loading={addLocation.isPending}
              disabled={!newLocationName.trim()}
              onClick={() => addLocation.mutate()}
            >
              Add
            </Button>
          </div>
          {locationError && <p className="text-sm text-danger mt-1">{locationError}</p>}
        </div>

        <BulkStructureSection societyId={society.id} locationsQueryKey={locationsQueryKey} />
      </div>
    </Modal>
  );
}

function LocationRow({
  societyId, location, locationsQueryKey,
}: { societyId: string; location: SocietyLocationOut; locationsQueryKey: QueryKey }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(location.name);
  const [locationType, setLocationType] = useState<LocationType>(location.location_type);
  const [error, setError] = useState<string | null>(null);

  const update = useMutation({
    mutationFn: () => societiesApi.updateLocation(societyId, location.id, name.trim(), locationType),
    onSuccess: () => {
      setError(null);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update.")),
  });

  if (!editing) {
    return (
      <li className="text-sm text-ink flex items-center gap-2">
        <span className="flex-1">{location.name}</span>
        <span className="text-xs text-navy-muted">({location.location_type === "WING" ? "Wing" : "Row"})</span>
        <button
          type="button"
          onClick={() => {
            setName(location.name);
            setLocationType(location.location_type);
            setError(null);
            setEditing(true);
          }}
          className="text-xs text-navy-muted hover:text-navy underline"
        >
          Edit
        </button>
      </li>
    );
  }

  return (
    <li className="space-y-1">
      <div className="flex gap-2 items-center">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          className="flex-1 px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        />
        <select
          value={locationType}
          onChange={(e) => setLocationType(e.target.value as LocationType)}
          className="px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        >
          <option value="WING">Wing</option>
          <option value="ROW">Row</option>
        </select>
        <Button variant="secondary" loading={update.isPending} disabled={!name.trim()} onClick={() => update.mutate()}>
          Save
        </Button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="text-xs text-navy-muted hover:text-danger px-1"
        >
          Cancel
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </li>
  );
}

function BulkStructureSection({
  societyId, locationsQueryKey,
}: { societyId: string; locationsQueryKey: QueryKey }) {
  const queryClient = useQueryClient();
  const [structureType, setStructureType] = useState<"FLATS" | "BUNGALOW">("FLATS");
  const [towerCount, setTowerCount] = useState("");
  const [floorsPerTower, setFloorsPerTower] = useState("");
  const [flatsPerFloor, setFlatsPerFloor] = useState("");
  const [rowCount, setRowCount] = useState("");
  const [housesPerRow, setHousesPerRow] = useState("");
  const [structureError, setStructureError] = useState<string | null>(null);
  const [structureSuccess, setStructureSuccess] = useState<string | null>(null);

  const propertiesQueryKey: QueryKey = ["platform", "societies", societyId, "properties"];
  const propertiesQuery = useQuery({
    queryKey: propertiesQueryKey,
    queryFn: () => societiesApi.listProperties(societyId).then((r) => r.data),
  });

  const generateFlats = useMutation({
    mutationFn: () =>
      societiesApi.generateFlatsStructure(
        societyId, Number(towerCount), Number(floorsPerTower), Number(flatsPerFloor)
      ),
    onSuccess: (r) => {
      setStructureSuccess(`Created ${r.data.length} flats across ${towerCount} tower(s).`);
      setStructureError(null);
      setTowerCount("");
      setFloorsPerTower("");
      setFlatsPerFloor("");
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
      void queryClient.invalidateQueries({ queryKey: propertiesQueryKey });
    },
    onError: (e) => setStructureError(apiErrorMessage(e, "Couldn't generate the structure.")),
  });

  const generateBungalows = useMutation({
    mutationFn: () => societiesApi.generateBungalowStructure(societyId, Number(rowCount), Number(housesPerRow)),
    onSuccess: (r) => {
      setStructureSuccess(`Created ${r.data.length} houses across ${rowCount} row(s).`);
      setStructureError(null);
      setRowCount("");
      setHousesPerRow("");
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
      void queryClient.invalidateQueries({ queryKey: propertiesQueryKey });
    },
    onError: (e) => setStructureError(apiErrorMessage(e, "Couldn't generate the structure.")),
  });

  const bungalowHouses = (propertiesQuery.data ?? []).filter((p) => p.house_type === "BUNGALOW");
  const canGenerateFlats = [towerCount, floorsPerTower, flatsPerFloor].every((v) => Number(v) > 0);
  const canGenerateBungalows = [rowCount, housesPerRow].every((v) => Number(v) > 0);

  return (
    <div className="border-t border-line pt-3">
      <label className="block text-sm text-navy-muted mb-2">Bulk-generate structure</label>
      <div className="flex gap-2 mb-3">
        {(["FLATS", "BUNGALOW"] as const).map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => setStructureType(opt)}
            className={`px-3 py-1.5 rounded text-sm border ${
              structureType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
            }`}
          >
            {opt === "FLATS" ? "Flats" : "Bungalow"}
          </button>
        ))}
      </div>

      {structureType === "FLATS" ? (
        <div className="grid grid-cols-3 gap-2 mb-2">
          <Input label="Towers" type="number" value={towerCount} onChange={(e) => setTowerCount(e.target.value)} />
          <Input
            label="Floors/tower"
            type="number"
            value={floorsPerTower}
            onChange={(e) => setFloorsPerTower(e.target.value)}
          />
          <Input
            label="Flats/floor"
            type="number"
            value={flatsPerFloor}
            onChange={(e) => setFlatsPerFloor(e.target.value)}
          />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <Input label="Rows" type="number" value={rowCount} onChange={(e) => setRowCount(e.target.value)} />
            <Input
              label="Houses/row"
              type="number"
              value={housesPerRow}
              onChange={(e) => setHousesPerRow(e.target.value)}
            />
          </div>
          <p className="text-xs text-navy-muted mb-2">
            Every house starts at ground floor only — set additional storeys per house below, after generating.
          </p>
        </>
      )}

      <div className="flex justify-end">
        {structureType === "FLATS" ? (
          <Button
            variant="secondary"
            loading={generateFlats.isPending}
            disabled={!canGenerateFlats}
            onClick={() => generateFlats.mutate()}
          >
            Generate
          </Button>
        ) : (
          <Button
            variant="secondary"
            loading={generateBungalows.isPending}
            disabled={!canGenerateBungalows}
            onClick={() => generateBungalows.mutate()}
          >
            Generate
          </Button>
        )}
      </div>

      {structureError && <p className="text-sm text-danger mt-1">{structureError}</p>}
      {structureSuccess && <p className="text-sm text-success mt-1">{structureSuccess}</p>}

      {bungalowHouses.length > 0 && (
        <div className="mt-4">
          <label className="block text-sm text-navy-muted mb-2">Houses — floors above ground</label>
          <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
            {bungalowHouses.map((house) => (
              <HouseFloorsRow
                key={house.id}
                societyId={societyId}
                house={house}
                propertiesQueryKey={propertiesQueryKey}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HouseFloorsRow({
  societyId, house, propertiesQueryKey,
}: { societyId: string; house: PropertyOut; propertiesQueryKey: QueryKey }) {
  const queryClient = useQueryClient();
  const [floors, setFloors] = useState(String(house.floors_above_ground));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => societiesApi.updatePropertyFloors(societyId, house.id, Number(floors)),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: propertiesQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update.")),
  });

  const dirty = Number(floors) !== house.floors_above_ground;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="flex-1 text-ink">{house.house_number}</span>
      <input
        type="number"
        min={0}
        value={floors}
        onChange={(e) => setFloors(e.target.value)}
        className="w-16 px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
      />
      <Button variant="secondary" loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
        Save
      </Button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
