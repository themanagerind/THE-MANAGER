import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { societiesApi, type SocietyLocationOut } from "@/api/societies";
import type { PropertyOut } from "@/api/properties";
import { Loader, ErrorState, apiErrorMessage } from "@/components/States";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

type Tab = "WINGS" | "FLOORS" | "FLATS";

/**
 * A Platform Owner mapping out a Flats-type society's structure in three
 * steps, each building on the last: Wings -> which floors each Wing has
 * -> the actual flat numbers on a given Wing/floor (hand-typed, since
 * real numbering schemes — "12-A", skipped 13th floors, whatever a
 * builder actually used — don't follow a single sequential pattern).
 * Replaces the old single-shot bulk generator, which assumed every floor
 * in a request looked the same.
 */
export function SocietyMapping() {
  const { societyId } = useParams<{ societyId: string }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("WINGS");

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
  const wings = (locationsQuery.data ?? []).filter((l) => l.location_type === "WING");

  const propertiesQueryKey = ["platform", "societies", societyId, "properties"];
  const propertiesQuery = useQuery({
    queryKey: propertiesQueryKey,
    queryFn: () => societiesApi.listProperties(societyId!).then((r) => r.data),
    enabled: !!societyId,
  });

  // Floors a Wing already has flats on, plus any the Platform Owner has
  // added in this session but hasn't put a flat on yet — purely local,
  // just to populate the Floor picker in the Flats step ahead of time.
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
          Map out this society's Wings, which floors each one has, and the actual flat numbers on each floor.
        </p>
      </div>

      <div className="flex gap-2 border-b border-line">
        {(
          [
            ["WINGS", "1. Wings"],
            ["FLOORS", "2. Floor mapping"],
            ["FLATS", "3. Flats mapping"],
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
        <ErrorState message="Couldn't load Wings." onRetry={() => locationsQuery.refetch()} />
      )}

      {tab === "WINGS" && (
        <WingsStep societyId={societyId} wings={wings} locationsQueryKey={locationsQueryKey} />
      )}

      {tab === "FLOORS" && (
        <FloorsStep wings={wings} floorsForWing={floorsForWing} addFloorToWing={addFloorToWing} />
      )}

      {tab === "FLATS" && (
        <FlatsStep
          societyId={societyId}
          wings={wings}
          floorsForWing={floorsForWing}
          addFloorToWing={addFloorToWing}
          properties={propertiesQuery.data ?? []}
          propertiesLoading={propertiesQuery.isLoading}
          onFlatsChanged={() => void queryClient.invalidateQueries({ queryKey: propertiesQueryKey })}
        />
      )}
    </div>
  );
}

function WingsStep({
  societyId, wings, locationsQueryKey,
}: { societyId: string; wings: SocietyLocationOut[]; locationsQueryKey: unknown[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const addWing = useMutation({
    mutationFn: () => societiesApi.addLocation(societyId, name.trim(), "WING"),
    onSuccess: () => {
      setName("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: locationsQueryKey });
    },
    onError: (e) => setError(apiErrorMessage(e, "Couldn't add the Wing.")),
  });

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Start by naming every Wing/Tower in this society — Floor and Flats mapping (next tabs) pick from this list.
      </p>
      {wings.length === 0 && <p className="text-xs text-navy-muted">No Wings yet — add the first one below.</p>}
      {wings.length > 0 && (
        <ul className="space-y-1">
          {wings.map((w) => (
            <li key={w.id} className="text-sm text-ink px-3 py-2 border border-line rounded">
              {w.name}
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2 items-end">
        <Input label="Wing name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Tower A" />
        <Button loading={addWing.isPending} disabled={!name.trim()} onClick={() => addWing.mutate()}>
          Add Wing
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function FloorsStep({
  wings, floorsForWing, addFloorToWing,
}: {
  wings: SocietyLocationOut[];
  floorsForWing: (wingId: string) => number[];
  addFloorToWing: (wingId: string, floorNumber: number) => void;
}) {
  const [selectedWingId, setSelectedWingId] = useState("");
  const [newFloor, setNewFloor] = useState("");

  if (wings.length === 0) {
    return <p className="text-sm text-navy-muted">Add at least one Wing in the "Wings" tab first.</p>;
  }

  const floors = selectedWingId ? floorsForWing(selectedWingId) : [];

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Pick a Wing, then list which floors it has — the Flats-mapping tab only offers floors you've added here.
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

      {selectedWingId && (
        <>
          {floors.length === 0 && <p className="text-xs text-navy-muted">No floors added yet for this Wing.</p>}
          {floors.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {floors.map((f) => (
                <li key={f} className="px-3 py-1 border border-line rounded text-sm text-ink bg-paper">
                  Floor {f}
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

function FlatsStep({
  societyId, wings, floorsForWing, addFloorToWing, properties, propertiesLoading, onFlatsChanged,
}: {
  societyId: string;
  wings: SocietyLocationOut[];
  floorsForWing: (wingId: string) => number[];
  addFloorToWing: (wingId: string, floorNumber: number) => void;
  properties: PropertyOut[];
  propertiesLoading: boolean;
  onFlatsChanged: () => void;
}) {
  const [selectedWingId, setSelectedWingId] = useState("");
  const [selectedFloor, setSelectedFloor] = useState("");
  const [flatCount, setFlatCount] = useState("");
  const [flatNumbers, setFlatNumbers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (wings.length === 0) {
    return <p className="text-sm text-navy-muted">Add at least one Wing in the "Wings" tab first.</p>;
  }

  const floors = selectedWingId ? floorsForWing(selectedWingId) : [];
  const existingFlats = properties.filter(
    (p) => p.location_id === selectedWingId && String(p.floor_number) === selectedFloor
  );

  function setCount(v: string) {
    setFlatCount(v);
    const n = Math.max(0, Math.min(200, Number(v) || 0));
    setFlatNumbers((prev) => Array.from({ length: n }, (_, i) => prev[i] ?? ""));
  }

  async function saveFlats() {
    setError(null);
    setSaving(true);
    const toSave = flatNumbers.map((n) => n.trim()).filter((n) => n.length > 0);
    const results = await Promise.allSettled(
      toSave.map((n) => societiesApi.addProperty(societyId, selectedWingId, n, Number(selectedFloor)))
    );
    const failedCount = results.filter((r) => r.status === "rejected").length;
    setSaving(false);
    onFlatsChanged();
    if (failedCount === 0) {
      setFlatCount("");
      setFlatNumbers([]);
    } else {
      setError(
        `${toSave.length - failedCount} of ${toSave.length} flat(s) saved — ${failedCount} failed ` +
          `(likely a duplicate number). Fix and retry those below."`
      );
    }
  }

  return (
    <div className="space-y-3 max-w-md">
      <p className="text-sm text-navy-muted">
        Pick a Wing and floor, say how many flats are on it, then type each flat's actual number.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-sm text-navy-muted mb-1">Wing</label>
          <select
            value={selectedWingId}
            onChange={(e) => {
              setSelectedWingId(e.target.value);
              setSelectedFloor("");
              setFlatCount("");
              setFlatNumbers([]);
            }}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy"
          >
            <option value="">Select a Wing</option>
            {wings.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-navy-muted mb-1">Floor</label>
          <select
            value={selectedFloor}
            onChange={(e) => {
              setSelectedFloor(e.target.value);
              setFlatCount("");
              setFlatNumbers([]);
            }}
            disabled={!selectedWingId}
            className="w-full px-3 py-2 border border-line rounded text-sm text-ink bg-white focus:border-navy disabled:bg-paper"
          >
            <option value="">Select a floor</option>
            {floors.map((f) => (
              <option key={f} value={f}>Floor {f}</option>
            ))}
          </select>
        </div>
      </div>

      {selectedWingId && floors.length === 0 && (
        <QuickAddFloor onAdd={(f) => { addFloorToWing(selectedWingId, f); setSelectedFloor(String(f)); }} />
      )}

      {selectedWingId && selectedFloor && (
        <>
          {propertiesLoading && <Loader />}
          {existingFlats.length > 0 && (
            <div>
              <label className="block text-sm text-navy-muted mb-1">Already on record</label>
              <ul className="flex flex-wrap gap-2">
                {existingFlats.map((f) => (
                  <li key={f.id} className="px-3 py-1 border border-line rounded text-sm text-ink bg-paper">
                    {f.house_number}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Input
            label="Number of flats to add" type="number" value={flatCount} onChange={(e) => setCount(e.target.value)}
          />
          {flatNumbers.length > 0 && (
            <div className="space-y-2">
              <label className="block text-sm text-navy-muted">Flat numbers</label>
              <div className="grid grid-cols-2 gap-2">
                {flatNumbers.map((n, i) => (
                  <input
                    key={i}
                    value={n}
                    onChange={(e) =>
                      setFlatNumbers((prev) => prev.map((v, vi) => (vi === i ? e.target.value : v)))
                    }
                    placeholder={`e.g. ${selectedFloor}0${i + 1}`}
                    className="px-2 py-1.5 border border-line rounded text-sm text-ink bg-white focus:border-navy"
                  />
                ))}
              </div>
              <Button loading={saving} disabled={flatNumbers.every((n) => !n.trim())} onClick={() => void saveFlats()}>
                Save flats
              </Button>
            </div>
          )}
          {error && <p className="text-sm text-danger">{error}</p>}
        </>
      )}
    </div>
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
