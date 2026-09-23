import type { SocietyLocationOut } from "@/api/societies";
import type { PropertyOut } from "@/api/properties";

const FLOOR_H = 42;
const WIN_W = 46;
const WIN_H = 26;
const WIN_GAP = 8;
const SIDE_PAD = 10;
const HOUSE_W = 54;
const HOUSE_H = 40;
const HOUSE_GAP = 8;

const OCC_FILL = "#E3F1E8";
const OCC_STROKE = "#2F7A4D";
const OCC_TEXT = "#1D5334";
const VAC_FILL = "#EEF0F2";
const VAC_STROKE = "#9AA5B1";
const VAC_TEXT = "#3A4E6E";

function byHouseNumber(a: PropertyOut, b: PropertyOut) {
  return a.house_number.localeCompare(b.house_number, undefined, { numeric: true, sensitivity: "base" });
}

function sortLocations(locations: SocietyLocationOut[]) {
  return [...locations].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }));
}

/** House/flat numbers now usually carry a "Tower A-" prefix, so a fixed
 * box width clips or overlaps longer ones — size each diagram's boxes to
 * fit its own longest label instead. */
function boxWidthFor(labels: string[], base: number): number {
  const longest = labels.reduce((max, l) => Math.max(max, l.length), 0);
  return Math.max(base, longest * 6 + 16);
}

/**
 * A small building-elevation / row-of-houses diagram of everything mapped
 * so far — one card per Wing (floors stacked, flats as windows) or Row
 * (a row of houses), colored by occupancy (green = a Resident is linked,
 * grey = vacant). Read-only unless `onSelectUnit` is given, in which case
 * clicking a flat/house calls it back with the location (and floor, for a
 * Wing) so a caller like the Society Mapping page can jump straight to
 * editing it.
 */
export function StructureDiagram({
  locations, properties, onSelectUnit,
}: {
  locations: SocietyLocationOut[];
  properties: PropertyOut[];
  onSelectUnit?: (locationId: string, floorNumber: number | null) => void;
}) {
  const wings = sortLocations(locations.filter((l) => l.location_type === "WING"));
  const rows = sortLocations(locations.filter((l) => l.location_type === "ROW"));

  if (wings.length === 0 && rows.length === 0) {
    return <p className="text-sm text-navy-muted">Nothing mapped yet.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-8 items-end overflow-x-auto pb-1">
        {wings.map((w) => (
          <BuildingCard
            key={w.id}
            wing={w}
            properties={properties.filter((p) => p.location_id === w.id)}
            onSelectUnit={onSelectUnit}
          />
        ))}
        {rows.map((r) => (
          <RowCard
            key={r.id}
            row={r}
            properties={properties.filter((p) => p.location_id === r.id)}
            onSelectUnit={onSelectUnit}
          />
        ))}
      </div>
      <Legend />
    </div>
  );
}

function EmptyCard({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy-muted mb-1">{label}</div>
      <div className="w-[150px] h-[80px] border border-dashed border-line rounded flex items-center justify-center text-xs text-navy-muted bg-paper">
        Not mapped yet
      </div>
    </div>
  );
}

function groupFlatsByFloor(properties: PropertyOut[]) {
  const byFloor = new Map<number, PropertyOut[]>();
  for (const p of properties) {
    if (p.floor_number == null) continue;
    if (!byFloor.has(p.floor_number)) byFloor.set(p.floor_number, []);
    byFloor.get(p.floor_number)!.push(p);
  }
  return Array.from(byFloor.entries())
    .sort((a, b) => b[0] - a[0]) // highest floor at the top, like a real building
    .map(([floorNumber, flats]) => ({ floorNumber, flats: [...flats].sort(byHouseNumber) }));
}

function BuildingCard({
  wing, properties, onSelectUnit,
}: { wing: SocietyLocationOut; properties: PropertyOut[]; onSelectUnit?: (locationId: string, floorNumber: number | null) => void }) {
  const floors = groupFlatsByFloor(properties);
  if (floors.length === 0) return <EmptyCard label={wing.name} />;

  const winW = boxWidthFor(properties.map((p) => p.house_number), WIN_W);
  const maxFlats = Math.max(...floors.map((f) => f.flats.length), 1);
  const width = SIDE_PAD * 2 + maxFlats * winW + (maxFlats - 1) * WIN_GAP;
  const height = floors.length * FLOOR_H;

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{wing.name}</div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <rect x={0} y={0} width={width} height={height} fill="#FFFFFF" stroke="#0A1F44" strokeWidth={1.5} />
        {floors.map((floor, i) => {
          const floorTop = i * FLOOR_H;
          const n = floor.flats.length;
          const rowW = n * winW + (n - 1) * WIN_GAP;
          const startX = (width - rowW) / 2;
          const wy = floorTop + (FLOOR_H - WIN_H) / 2;
          return (
            <g key={floor.floorNumber}>
              {i > 0 && <line x1={0} y1={floorTop} x2={width} y2={floorTop} stroke="#E3E6EB" strokeWidth={1} />}
              {floor.flats.map((p, j) => {
                const wx = startX + j * (winW + WIN_GAP);
                const occ = p.is_occupied;
                return (
                  <g
                    key={p.id}
                    style={{ cursor: onSelectUnit ? "pointer" : "default" }}
                    onClick={() => onSelectUnit?.(wing.id, floor.floorNumber)}
                  >
                    <title>{`${p.house_number} — ${occ ? "occupied" : "vacant"}`}</title>
                    <rect
                      x={wx} y={wy} width={winW} height={WIN_H} rx={2}
                      fill={occ ? OCC_FILL : VAC_FILL} stroke={occ ? OCC_STROKE : VAC_STROKE} strokeWidth={1.4}
                    />
                    <text
                      x={wx + winW / 2} y={wy + WIN_H / 2 + 4} textAnchor="middle" fontSize={10} fontWeight={600}
                      fill={occ ? OCC_TEXT : VAC_TEXT}
                    >
                      {p.house_number}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="text-xs text-navy-muted mt-1">
        {floors.length} floor{floors.length !== 1 ? "s" : ""} mapped &middot; {properties.length} flat{properties.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

/**
 * A live preview of one Wing while it's being mapped — same look as
 * BuildingCard above, but driven by the FULL floor list (including
 * floors with no flats yet, shown as an empty band) rather than only
 * floors that already have properties, and with `highlightFloor` picked
 * out (the floor being worked on right now). Used by the Floor-mapping
 * and Flats & Houses-mapping steps so the Platform Owner can see the
 * building take shape floor by floor instead of only at the end.
 */
export function WingPreview({
  wing, floors, properties, highlightFloor,
}: {
  wing: SocietyLocationOut;
  floors: number[];
  properties: PropertyOut[];
  highlightFloor?: number | null;
}) {
  if (floors.length === 0) return <EmptyCard label={wing.name} />;

  const PREVIEW_FLOOR_H = 54; // taller than FLOOR_H — leaves room for the "F<n>" label above the windows
  const sortedFloors = [...floors].sort((a, b) => b - a); // highest at the top
  const flatsPerFloor = sortedFloors.map((f) => properties.filter((p) => p.floor_number === f).sort(byHouseNumber));
  const winW = boxWidthFor(properties.map((p) => p.house_number), WIN_W);
  const maxFlats = Math.max(...flatsPerFloor.map((f) => f.length), 1);
  const width = SIDE_PAD * 2 + maxFlats * winW + (maxFlats - 1) * WIN_GAP;
  const height = sortedFloors.length * PREVIEW_FLOOR_H;

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{wing.name}</div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <rect x={0} y={0} width={width} height={height} fill="#FFFFFF" stroke="#0A1F44" strokeWidth={1.5} />
        {sortedFloors.map((floorNumber, i) => {
          const floorTop = i * PREVIEW_FLOOR_H;
          const flats = flatsPerFloor[i];
          const highlighted = highlightFloor === floorNumber;
          const n = flats.length;
          const rowW = n * winW + (n - 1) * WIN_GAP;
          const startX = (width - rowW) / 2;
          const wy = floorTop + 22;
          return (
            <g key={floorNumber}>
              {i > 0 && <line x1={0} y1={floorTop} x2={width} y2={floorTop} stroke="#E3E6EB" strokeWidth={1} />}
              {highlighted && (
                <rect
                  x={1} y={floorTop + 1} width={width - 2} height={PREVIEW_FLOOR_H - 2}
                  fill="#FBF3E4" stroke="#B8873A" strokeWidth={1.5}
                />
              )}
              <text x={width / 2} y={floorTop + 13} textAnchor="middle" fontSize={10} fontWeight={700} fill="#3A4E6E">
                Floor {floorNumber}
              </text>
              {n === 0 ? (
                <text x={width / 2} y={floorTop + 36} textAnchor="middle" fontSize={10} fill="#9AA5B1">
                  no flats yet
                </text>
              ) : (
                flats.map((p, j) => {
                  const wx = startX + j * (winW + WIN_GAP);
                  const occ = p.is_occupied;
                  return (
                    <g key={p.id}>
                      <rect
                        x={wx} y={wy} width={winW} height={WIN_H} rx={2}
                        fill={occ ? OCC_FILL : VAC_FILL} stroke={occ ? OCC_STROKE : VAC_STROKE} strokeWidth={1.4}
                      />
                      <text
                        x={wx + winW / 2} y={wy + WIN_H / 2 + 4} textAnchor="middle" fontSize={10} fontWeight={600}
                        fill={occ ? OCC_TEXT : VAC_TEXT}
                      >
                        {p.house_number}
                      </text>
                    </g>
                  );
                })
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function RowCard({
  row, properties, onSelectUnit,
}: { row: SocietyLocationOut; properties: PropertyOut[]; onSelectUnit?: (locationId: string, floorNumber: number | null) => void }) {
  if (properties.length === 0) return <EmptyCard label={row.name} />;

  const houses = [...properties].sort(byHouseNumber);
  const houseW = boxWidthFor(houses.map((p) => p.house_number), HOUSE_W);
  const width = houses.length * houseW + (houses.length - 1) * HOUSE_GAP;

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{row.name}</div>
      <svg width={width} height={HOUSE_H} viewBox={`0 0 ${width} ${HOUSE_H}`}>
        {houses.map((p, i) => {
          const x = i * (houseW + HOUSE_GAP);
          const occ = p.is_occupied;
          return (
            <g
              key={p.id}
              style={{ cursor: onSelectUnit ? "pointer" : "default" }}
              onClick={() => onSelectUnit?.(row.id, null)}
            >
              <title>{`${p.house_number} — ${occ ? "occupied" : "vacant"}`}</title>
              <rect
                x={x} y={0} width={houseW} height={HOUSE_H} rx={4}
                fill={occ ? OCC_FILL : VAC_FILL} stroke={occ ? OCC_STROKE : VAC_STROKE} strokeWidth={1.4}
              />
              <text x={x + houseW / 2} y={HOUSE_H / 2 + 4} textAnchor="middle" fontSize={10} fontWeight={600} fill={occ ? OCC_TEXT : VAC_TEXT}>
                {p.house_number}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="text-xs text-navy-muted mt-1">{houses.length} house{houses.length !== 1 ? "s" : ""}</div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex gap-4 pt-3 border-t border-line text-xs text-navy-muted">
      <span className="flex items-center gap-1.5">
        <span className="w-3.5 h-3.5 rounded-sm inline-block" style={{ background: OCC_FILL, border: `1.4px solid ${OCC_STROKE}` }} />
        Occupied (Resident linked)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-3.5 h-3.5 rounded-sm inline-block" style={{ background: VAC_FILL, border: `1.4px solid ${VAC_STROKE}` }} />
        Vacant
      </span>
    </div>
  );
}
