import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { societiesApi, type SocietyLocationOut } from "@/api/societies";
import type { PropertyOut } from "@/api/properties";
import type { HouseType, LocationType } from "@/types/enums";
import { Loader, ErrorState, apiErrorMessage } from "@/components/States";
import { StructureDiagram, WingPreview, RowCard } from "@/components/StructureDiagram";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

type Tab = "LOCATIONS" | "FLOORS" | "UNITS" | "OVERVIEW";

function sortByName(locations: SocietyLocationOut[]): SocietyLocationOut[] {
  return [...locations].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }));
}

/**
 * A Platform Owner mapping out a society's structure in three input steps,
 * each building on the last: Wings & Rows -> which floors each Wing has
 * (Rows/Bungalows skip this — they have no floors) -> the actual flat/
 * house numbers, hand-typed since real numbering schemes ("12-A", skipped
 * 13th floors, a Row's own house-number scheme) don't follow a single
 * sequential pattern — plus a read-only Overview diagram of everything
 * mapped so far. Replaces the old single-shot bulk generator, which
 * assumed every floor in a request looked the same.
 */
export function SocietyMapping() {
  const { societyId } = useParams<{ societyId: string }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("LOCATIONS");
  const [jumpTarget, setJumpTarget] = useState<{ locationId: string; floorNumber: number | null } | null>(null);

  const societiesQuery = useQuery({
    queryKey: ["platform", "societies"],
    queryFn: () => societiesApi.list().then((r) => r.data),
  });
  const society = societiesQuery.data?.find((s) => s.id === societyId);

  const locationsQueryKey = ["platform", "societies", societyId, "locations"];
  const locationsQuery = useQuery({
    queryKey: locationsQueryKey,
    queryFn: () => societiesApi.listLocations(societyId!).then((r) => r.data),
    enabled: !!societyId,
  });
  const locations = sortByName(locationsQuery.data ?? []);
  const wings = locations.filter((l) => l.location_type === "WING");

  const propertiesQueryKey = ["platform", "societies", societyId, "properties"];
  const propertiesQuery = useQuery({
    queryKey: propertiesQueryKey,
    queryFn: () => societiesApi.listProperties(societyId!).then((r) => r.data),
    enabled: !!societyId,
  });

  // Floors a Wing already has flats on, plus any the Platform Owner has
  // added in this session but hasn't put a flat on yet — purely local,
  // just to populate the Floor picker in the Units step ahead of time.
  const [extraFloorsByWing, setExtraFloorsByWing] = useState<Record<string, number[]>>({});
  function floorsForWing(wingId: string): number[] {
    const fromProperties = (propertiesQuery.data ?? [])
      .filter((p) => p.location_id === wingId && p.floor_number != null)
      .map((p) => p.floor_number as number);
    const extra = extraFloorsByWing[wingId] ?? [];
    return Array.from(new Set([...fromProperties, ...extra])).sort((a, b) => a - b);
  }
  function addFloorToWing(wingId: string, floorNumber: number) {
    setExtraFloorsByWing((prev) => ({
      ...prev,
      [wingId]: Array.from(new Set([...(prev[wingId] ?? []), floorNumber])),
    }));
  }
  function canRemoveFloor(wingId: string, floorNumber: number): boolean {
    const hasProperty = (propertiesQuery.data ?? []).some(
      (p) => p.location_id === wingId && p.floor_number === floorNumber
    );
    return !hasProperty;
  }
  function removeFloorFromWing(wingId: string, floorNumber: number) {
    setExtraFloorsByWing((prev) => ({
      ...prev,
      [wingId]: (prev[wingId] ?? []).filter((f) => f !== floorNumber),
    }));
  }

  function jumpToUnit(locationId: string, floorNumber: number | null) {
    setJumpTarget({ locationId, floorNumber });
    setTab("UNITS");
  }

  if (!societyId) return <ErrorState message="No society specified." />;

  return (
    <div className="space-y-4">
      <div>
        <Link to="/platform/societies" className="text-sm text-navy-muted hover:text-navy underline">
          &larr; Back to Societies
        </Link>
        <h1 className="text-xl font-semibold text-navy mt-1">
          Society Mapping {society ? `— ${society.name}` : ""}
        </h1>
        <p className="text-sm text-navy-muted">
          Map out this society's Wings and Rows, which floors each Wing has, and the actual flat/house numbers.
        </p>
      </div>

      <div className="flex gap-2 border-b border-line flex-wrap">
        {(
          [
            ["LOCATIONS", "1. Wings & Rows"],
            ["FLOORS", "2. Floor mapping"],
            ["UNITS", "3. Flats & Houses"],
            ["OVERVIEW", "4. Overview"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px ${
              tab === key ? "border-navy text-navy font-medium" : "border-transparent text-navy-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {locationsQuery.isLoading && <Loader />}
      {locationsQuery.isError && (
        <ErrorState message="Couldn't load Wings/Rows." onRetry={() => locationsQuery.refetch()} />
      )}

      {tab === "LOCATIONS" && (
        <LocationsStep societyId={societyId} locations={locations} locationsQueryKey={locationsQueryKey} />
      )}

      {tab === "FLOORS" && (
        <FloorsStep
          wings={wings}
          properties={propertiesQuery.data ?? []}
          floorsForWing={floorsForWing}
          addFloorToWing={addFloorToWing}
          canRemoveFloor={canRemoveFloor}
          removeFloorFromWing={removeFloorFromWing}
        />
      )}

      {tab === "UNITS" && (
        <UnitsStep
          key={jumpTarget ? `${jumpTarget.locationId}:${jumpTarget.floorNumber}` : "default"}
          societyId={societyId}
          locations={locations}
          floorsForWing={floorsForWing}
          addFloorToWing={addFloorToWing}
          properties={propertiesQuery.data ?? []}
          propertiesLoading={propertiesQuery.isLoading}
          onUnitsChanged={() => void queryClient.invalidateQueries({ queryKey: propertiesQueryKey })}
          initialLocationId={jumpTarget?.locationId}
          initialFloor={jumpTarget?.floorNumber ?? undefined}
        />
      )}

      {tab === "OVERVIEW" && (
        <div className="space-y-2">
          <p className="text-sm text-navy-muted">
            Everything mapped so far, drawn like the real thing — green means a Resident is linked, grey means
            vacant. Click a flat or house to jump to editing it.
          </p>
          {propertiesQuery.isLoading && <Loader />}
          <StructureDiagram locations={locations} properties={propertiesQuery.data ?? []} onSelectUnit={jumpToUnit} />
        </div>
      )}
    </div>
  );
}

function LocationsStep({
  societyId, locations, locationsQueryKey,
}: { societyId: string; locations: SocietyLocationOut[]; locationsQueryKey: unknown[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [locationType, setLocationType] = useState<LocationType>("WING");
  const [error, setError] = useState<string | null>(null);

  const addLocation = useMutation({
    mutationFn: () => societiesApi.addLocation(societyId, name.trim(), locationType),
    onSuccess: () => {
      setName("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add it.")),
  });

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Name every Wing (for Flats) and Row (for Bungalows) in this society — Floor, Flats/Houses and Overview
        (next tabs) pick from this list. Typed a name wrong? Click it to fix it.
      </p>
      {locations.length === 0 && <p className="text-xs text-navy-muted">Nothing added yet — add the first one below.</p>}
      {locations.length > 0 && (
        <ul className="space-y-1">
          {locations.map((l) => (
            <LocationRow key={l.id} societyId={societyId} location={l} locationsQueryKey={locationsQueryKey} />
          ))}
        </ul>
      )}
      <div className="flex gap-2 items-end flex-wrap">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Type</label>
          <div className="flex gap-2">
            {(["WING", "ROW"] as LocationType[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setLocationType(opt)}
                className={`px-3 py-2 rounded text-sm border ${
                  locationType === opt ? "bg-navy text-white border-navy" : "border-line text-navy-muted"
                }`}
              >
                {opt === "WING" ? "Wing" : "Row"}
              </button>
            ))}
          </div>
        </div>
        <Input
          label={locationType === "WING" ? "Wing name" : "Row name"}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={locationType === "WING" ? "e.g. Tower A" : "e.g. Row A"}
        />
        <Button loading={addLocation.isPending} disabled={!name.trim()} onClick={() => addLocation.mutate()}>
          Add {locationType === "WING" ? "Wing" : "Row"}
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function LocationRow({
  societyId, location, locationsQueryKey,
}: { societyId: string; location: SocietyLocationOut; locationsQueryKey: unknown[] }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(location.name);
  const [error, setError] = useState<string | null>(null);

  const rename = useMutation({
    mutationFn: () => societiesApi.updateLocation(societyId, location.id, name.trim(), location.location_type),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't rename this.")),
  });

  const remove = useMutation({
    mutationFn: () => societiesApi.deleteLocation(societyId, location.id),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't delete — it may still have flats/houses on it.")),
  });

  function handleDelete() {
    if (window.confirm(`Delete "${location.name}"? This can't be undone.`)) {
      remove.mutate();
    }
  }

  if (!editing) {
    return (
      <li className="text-sm text-ink flex items-center gap-2 px-3 py-2 border border-line rounded">
        <span className="text-xs text-navy-muted w-10 shrink-0">{location.location_type === "WING" ? "Wing" : "Row"}</span>
        <span className="flex-1">{location.name}</span>
        <button
          type="button"
          onClick={() => { setName(location.name); setError(null); setEditing(true); }}
          className="text-xs text-navy-muted hover:text-navy underline"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={remove.isPending}
          className="text-xs text-navy-muted hover:text-danger underline"
        >
          Delete
        </button>
        {error && <span className="text-xs text-danger">{error}</span>}
      </li>
    );
  }

  return (
    <li className="space-y-1 px-3 py-2 border border-navy rounded">
      <div className="flex gap-2 items-center">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          className="flex-1 px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        />
        <Button variant="secondary" loading={rename.isPending} disabled={!name.trim()} onClick={() => rename.mutate()}>
          Save
        </Button>
        <button type="button" onClick={() => setEditing(false)} className="text-xs text-navy-muted hover:text-danger px-1">
          Cancel
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </li>
  );
}

function FloorsStep({
  wings, properties, floorsForWing, addFloorToWing, canRemoveFloor, removeFloorFromWing,
}: {
  wings: SocietyLocationOut[];
  properties: PropertyOut[];
  floorsForWing: (wingId: string) => number[];
  addFloorToWing: (wingId: string, floorNumber: number) => void;
  canRemoveFloor: (wingId: string, floorNumber: number) => boolean;
  removeFloorFromWing: (wingId: string, floorNumber: number) => void;
}) {
  const [selectedWingId, setSelectedWingId] = useState("");
  const [newFloor, setNewFloor] = useState("");
  const selectedWing = wings.find((w) => w.id === selectedWingId);

  if (wings.length === 0) {
    return (
      <p className="text-sm text-navy-muted">
        Add a Wing in the "Wings &amp; Rows" tab first. (Rows/Bungalows don't need floor mapping — go straight to
        the Flats &amp; Houses tab for those.)
      </p>
    );
  }

  const floors = selectedWingId ? floorsForWing(selectedWingId) : [];

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Pick a Wing, then list which floors it has — the Flats-mapping tab only offers floors you've added here.
        Rows/Bungalows have no floors, so they don't appear here.
      </p>
      <div>
        <label className="block text-sm text-navy-muted mb-1">Wing</label>
        <select
          value={selectedWingId}
          onChange={(e) => setSelectedWingId(e.target.value)}
          className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        >
          <option value="">Select a Wing</option>
          {wings.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
      </div>

      {selectedWingId && selectedWing && (
        <>
          <WingPreview
            wing={selectedWing}
            floors={floors}
            properties={properties.filter((p) => p.location_id === selectedWingId)}
            highlightFloor={newFloor.trim() && !Number.isNaN(Number(newFloor)) ? Number(newFloor) : null}
          />
          {floors.length === 0 && <p className="text-xs text-navy-muted">No floors added yet for this Wing.</p>}
          {floors.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {floors.map((f) => (
                <li
                  key={f}
                  className="flex items-center gap-1.5 px-3 py-1 border border-line rounded text-sm text-ink bg-paper"
                >
                  Floor {f}
                  {canRemoveFloor(selectedWingId, f) && (
                    <button
                      type="button"
                      onClick={() => removeFloorFromWing(selectedWingId, f)}
                      aria-label={`Remove floor ${f}`}
                      className="text-navy-muted hover:text-danger leading-none"
                    >
                      &times;
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2 items-end">
            <Input
              label="Floor number" type="number" value={newFloor} onChange={(e) => setNewFloor(e.target.value)}
              placeholder="e.g. 1"
            />
            <Button
              disabled={!newFloor.trim()}
              onClick={() => {
                addFloorToWing(selectedWingId, Number(newFloor));
                setNewFloor("");
              }}
            >
              Add floor
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function UnitsStep({
  societyId, locations, floorsForWing, addFloorToWing, properties, propertiesLoading, onUnitsChanged,
  initialLocationId, initialFloor,
}: {
  societyId: string;
  locations: SocietyLocationOut[];
  floorsForWing: (wingId: string) => number[];
  addFloorToWing: (wingId: string, floorNumber: number) => void;
  properties: PropertyOut[];
  propertiesLoading: boolean;
  onUnitsChanged: () => void;
  initialLocationId?: string;
  initialFloor?: number | null;
}) {
  const wings = locations.filter((l) => l.location_type === "WING");
  const rows = locations.filter((l) => l.location_type === "ROW");

  const [selectedLocationId, setSelectedLocationId] = useState(initialLocationId ?? "");
  const [selectedFloor, setSelectedFloor] = useState(initialFloor != null ? String(initialFloor) : "");
  const [unitCount, setUnitCount] = useState("");
  const [unitNumbers, setUnitNumbers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (locations.length === 0) {
    return <p className="text-sm text-navy-muted">Add at least one Wing or Row in the "Wings &amp; Rows" tab first.</p>;
  }

  const selectedLocation = locations.find((l) => l.id === selectedLocationId);
  const isWing = selectedLocation?.location_type === "WING";
  const floors = isWing && selectedLocationId ? floorsForWing(selectedLocationId) : [];
  const ready = isWing ? !!selectedLocationId && !!selectedFloor : !!selectedLocationId;
  const existingUnits = properties
    .filter((p) => {
      if (p.location_id !== selectedLocationId) return false;
      return isWing ? String(p.floor_number) === selectedFloor : true;
    })
    .sort((a, b) => a.house_number.localeCompare(b.house_number, undefined, { numeric: true, sensitivity: "base" }));

  function setCount(v: string) {
    setUnitCount(v);
    const n = Math.max(0, Math.min(200, Number(v) || 0));
    setUnitNumbers((prev) => Array.from({ length: n }, (_, i) => prev[i] ?? ""));
  }

  const unitPrefix = selectedLocation ? `${selectedLocation.name}-` : "";

  async function saveUnits() {
    setError(null);
    setSaving(true);
    // Keep each entry's original box index so a partial failure can clear
    // out just the ones that saved and leave the failed ones in place to
    // fix — resending an already-saved entry on retry would just collide
    // with itself and report as "failed" a second time.
    const entries = unitNumbers
      .map((n, index) => ({ index, suffix: n.trim() }))
      .filter((e) => e.suffix.length > 0);
    const houseType: HouseType = isWing ? "FLAT" : "BUNGALOW";
    const floorArg = isWing ? Number(selectedFloor) : undefined;
    const results = await Promise.allSettled(
      entries.map((e) => societiesApi.addProperty(societyId, selectedLocationId, `${unitPrefix}${e.suffix}`, houseType, floorArg))
    );
    const failedCount = results.filter((r) => r.status === "rejected").length;
    setSaving(false);
    onUnitsChanged();
    if (failedCount === 0) {
      setUnitCount("");
      setUnitNumbers([]);
    } else {
      const succeededIndexes = new Set(
        entries.filter((_, i) => results[i].status === "fulfilled").map((e) => e.index)
      );
      setUnitNumbers((prev) => prev.map((v, i) => (succeededIndexes.has(i) ? "" : v)));
      setError(
        `${entries.length - failedCount} of ${entries.length} unit(s) saved — ${failedCount} failed ` +
          `(likely a duplicate number). Fix and retry those below.`
      );
    }
  }

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Pick a Wing (then a floor) or a Row, say how many flats/houses are on it, then type each one's actual
        number.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Wing / Row</label>
          <select
            value={selectedLocationId}
            onChange={(e) => {
              setSelectedLocationId(e.target.value);
              setSelectedFloor("");
              setUnitCount("");
              setUnitNumbers([]);
              setError(null);
            }}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select a Wing or Row</option>
            {wings.length > 0 && (
              <optgroup label="Wings (Flats)">
                {wings.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </optgroup>
            )}
            {rows.length > 0 && (
              <optgroup label="Rows (Bungalows)">
                {rows.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </optgroup>
            )}
          </select>
        </div>
        {isWing && (
          <div>
            <label className="block text-sm text-navy-muted mb-1">Floor</label>
            <select
              value={selectedFloor}
              onChange={(e) => {
                setSelectedFloor(e.target.value);
                setUnitCount("");
                setUnitNumbers([]);
                setError(null);
              }}
              disabled={!selectedLocationId}
              className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy disabled:bg-paper"
            >
              <option value="">Select a floor</option>
              {floors.map((f) => (
                <option key={f} value={f}>Floor {f}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {selectedLocation && isWing && (
        <WingPreview
          wing={selectedLocation}
          floors={floors}
          properties={properties.filter((p) => p.location_id === selectedLocationId)}
          highlightFloor={selectedFloor ? Number(selectedFloor) : null}
        />
      )}
      {selectedLocation && !isWing && (
        <RowCard row={selectedLocation} properties={properties.filter((p) => p.location_id === selectedLocationId)} />
      )}

      {isWing && selectedLocationId && floors.length === 0 && (
        <QuickAddFloor onAdd={(f) => { addFloorToWing(selectedLocationId, f); setSelectedFloor(String(f)); }} />
      )}

      {selectedLocation && !isWing && (
        <p className="text-xs text-navy-muted">
          Rows/Bungalows have no floors of their own — add the houses below first, then set each one's own
          "Floors above ground" once it's on record (a Row's houses don't all have to match).
        </p>
      )}

      {ready && (
        <>
          {propertiesLoading && <Loader />}
          {existingUnits.length > 0 && (
            <div>
              <label className="block text-sm text-navy-muted mb-1">
                Already on record — click one to fix a typo
              </label>
              <ul className="space-y-1">
                {existingUnits.map((u) => (
                  <ExistingUnitRow
                    key={u.id}
                    societyId={societyId}
                    unit={u}
                    locationId={selectedLocationId}
                    houseType={isWing ? "FLAT" : "BUNGALOW"}
                    floors={floors}
                    onChanged={onUnitsChanged}
                  />
                ))}
              </ul>
            </div>
          )}

          <Input
            label={isWing ? "Number of flats to add" : "Number of houses to add"}
            type="number" value={unitCount} onChange={(e) => setCount(e.target.value)}
          />
          {unitNumbers.length > 0 && (
            <div className="space-y-2">
              <label className="block text-sm text-navy-muted">
                {isWing ? "Flat numbers" : "House numbers"} — "{unitPrefix}" is added automatically, just type the
                rest
              </label>
              <div className="grid grid-cols-2 gap-2">
                {unitNumbers.map((n, i) => (
                  <div key={i} className="flex">
                    <span className="px-2 py-1.5 border border-r-0 border-line rounded-l text-sm text-navy-muted bg-paper whitespace-nowrap overflow-hidden text-ellipsis max-w-[45%]">
                      {unitPrefix}
                    </span>
                    <input
                      value={n}
                      onChange={(e) =>
                        setUnitNumbers((prev) => prev.map((v, vi) => (vi === i ? e.target.value : v)))
                      }
                      placeholder={isWing ? `e.g. ${selectedFloor}0${i + 1}` : `e.g. ${i + 1}`}
                      className="flex-1 min-w-0 px-2 py-1.5 border border-line rounded-r text-sm text-ink bg-white focus:border-navy"
                    />
                  </div>
                ))}
              </div>
              <Button loading={saving} disabled={unitNumbers.every((n) => !n.trim())} onClick={() => void saveUnits()}>
                Save {isWing ? "flats" : "houses"}
              </Button>
            </div>
          )}
          {error && <p className="text-sm text-danger">{error}</p>}
        </>
      )}
    </div>
  );
}

function ExistingUnitRow({
  societyId, unit, locationId, houseType, floors, onChanged,
}: {
  societyId: string;
  unit: PropertyOut;
  locationId: string;
  houseType: HouseType;
  floors: number[];
  onChanged: () => void;
}) {
  const isWing = houseType === "FLAT";
  const [editing, setEditing] = useState(false);
  const [houseNumber, setHouseNumber] = useState(unit.house_number);
  const [floorNumber, setFloorNumber] = useState(unit.floor_number != null ? String(unit.floor_number) : "");
  const [floorsAboveGround, setFloorsAboveGround] = useState(String(unit.floors_above_ground));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      societiesApi.updateProperty(
        societyId, unit.id, locationId, houseNumber.trim(), houseType, isWing ? Number(floorNumber) : undefined
      ),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      onChanged();
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't save — that number may already be in use.")),
  });

  const remove = useMutation({
    mutationFn: () => societiesApi.deleteProperty(societyId, unit.id),
    onSuccess: () => {
      setError(null);
      onChanged();
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't delete — it may already be linked to a Resident.")),
  });

  // Bungalow-only — how many storeys THIS house has above the ground
  // floor. A Row's houses don't all have the same number of floors, so
  // this is set per house, after it's created (not up front).
  const saveFloors = useMutation({
    mutationFn: () => societiesApi.updatePropertyFloors(societyId, unit.id, Number(floorsAboveGround)),
    onSuccess: () => {
      setError(null);
      onChanged();
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't update floors.")),
  });
  const floorsDirty = Number(floorsAboveGround) !== unit.floors_above_ground;

  function handleDelete() {
    if (window.confirm(`Delete "${unit.house_number}"? This can't be undone.`)) {
      remove.mutate();
    }
  }

  if (!editing) {
    return (
      <li className="text-sm text-ink flex items-center gap-2 px-3 py-1.5 border border-line rounded bg-paper">
        <span className="flex-1">{unit.house_number}</span>
        {!isWing && (
          <div className="flex items-center gap-1">
            <label className="text-xs text-navy-muted whitespace-nowrap">Floors above ground</label>
            <input
              type="number"
              min={0}
              value={floorsAboveGround}
              onChange={(e) => setFloorsAboveGround(e.target.value)}
              className="w-14 px-1.5 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
            />
            <Button
              variant="secondary"
              loading={saveFloors.isPending}
              disabled={!floorsDirty}
              onClick={() => saveFloors.mutate()}
            >
              Save
            </Button>
          </div>
        )}
        <button
          type="button"
          onClick={() => {
            setHouseNumber(unit.house_number);
            setFloorNumber(unit.floor_number != null ? String(unit.floor_number) : "");
            setError(null);
            setEditing(true);
          }}
          className="text-xs text-navy-muted hover:text-navy underline"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={remove.isPending}
          className="text-xs text-navy-muted hover:text-danger underline"
        >
          Delete
        </button>
        {error && <span className="text-xs text-danger">{error}</span>}
      </li>
    );
  }

  return (
    <li className="space-y-1 px-3 py-1.5 border border-navy rounded">
      <div className="flex gap-2 items-center">
        <input
          value={houseNumber}
          onChange={(e) => setHouseNumber(e.target.value)}
          autoFocus
          className="flex-1 px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
        />
        {isWing && (
          <select
            value={floorNumber}
            onChange={(e) => setFloorNumber(e.target.value)}
            className="px-2 py-1 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            {floors.map((f) => (
              <option key={f} value={f}>Floor {f}</option>
            ))}
          </select>
        )}
        <Button
          variant="secondary"
          loading={save.isPending}
          disabled={!houseNumber.trim() || (isWing && !floorNumber)}
          onClick={() => save.mutate()}
        >
          Save
        </Button>
        <button type="button" onClick={() => setEditing(false)} className="text-xs text-navy-muted hover:text-danger px-1">
          Cancel
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </li>
  );
}

function QuickAddFloor({ onAdd }: { onAdd: (floorNumber: number) => void }) {
  const [floor, setFloor] = useState("");
  return (
    <div className="flex gap-2 items-end">
      <Input
        label="This Wing has no floors yet — add one" type="number" value={floor}
        onChange={(e) => setFloor(e.target.value)} placeholder="e.g. 1"
      />
      <Button
        disabled={!floor.trim()}
        onClick={() => { onAdd(Number(floor)); setFloor(""); }}
      >
        Add floor
      </Button>
    </div>
  );
}
