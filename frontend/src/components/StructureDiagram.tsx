import type { SocietyLocationOut } from "@/api/societies";
import type { PropertyOut } from "@/api/properties";

const WIN_W = 46;
const WIN_H = 26;
const GAP_X = 8;
const GAP_Y = 6;
const SIDE_PAD = 10;
const HOUSE_W = 54;
const HOUSE_H = 40;
// Cap how wide any single diagram grows before wrapping to a new row —
// without this, a Row with 86 houses (a real case) renders as one
// off-screen-long strip instead of a compact, roughly-square block.
const MAX_GRID_WIDTH = 480;

const OCC_FILL = "#E3F1E8";
const OCC_STROKE = "#2F7A4D";
const OCC_TEXT = "#1D5334";
const VAC_FILL = "#EEF0F2";
const VAC_STROKE = "#9AA5B1";
const VAC_TEXT = "#0A1F44";

function byHouseNumber(a: PropertyOut, b: PropertyOut) {
  return a.house_number.localeCompare(b.house_number, undefined, { numeric: true, sensitivity: "base" });
}

function sortLocations(locations: SocietyLocationOut[]) {
  return [...locations].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }));
}

/** Groups Wings/Rows by their shared name prefix ("A1"/"A2" -> "A",
 * "B1"/"B2" -> "B") so each block renders as its own flex row — plain
 * flex-wrap alone packs cards by whatever fits the available width,
 * which visually clumps unrelated wings together (B1 sharing a row with
 * A1/A2 just because there was room) instead of keeping same-letter
 * wings together. Falls back to one-per-group (unchanged from before)
 * when a name has no trailing number to group by. Order follows the
 * already-sorted input, so groups come out in the same A, B, C sequence. */
function groupByPrefix(locations: SocietyLocationOut[]): SocietyLocationOut[][] {
  const groups = new Map<string, SocietyLocationOut[]>();
  for (const loc of locations) {
    const prefix = loc.name.replace(/\d+\s*$/, "").trim() || loc.name;
    if (!groups.has(prefix)) groups.set(prefix, []);
    groups.get(prefix)!.push(loc);
  }
  return Array.from(groups.values());
}

/** House/flat numbers now usually carry a "Tower A-" prefix, so a fixed
 * box width clips or overlaps longer ones — size each diagram's boxes to
 * fit its own longest label instead. */
function boxWidthFor(labels: string[], base: number): number {
  const longest = labels.reduce((max, l) => Math.max(max, l.length), 0);
  return Math.max(base, longest * 7 + 16);
}

/** How many columns to wrap a set of `count` same-size boxes into, so the
 * block reads as a compact, roughly-square grid instead of one long row —
 * e.g. 4 flats on a floor become a 2x2 block, not a 4-tall strip. Column
 * count is based on `count` alone (a plain ceil(sqrt(count)) grid), capped
 * so a row never exceeds MAX_GRID_WIDTH. It deliberately ignores box
 * width/height: weighing by box size used to shrink wide boxes (long,
 * auto-prefixed house numbers like "A1-101") down to a single column even
 * for a small, even count like 4 — the opposite of "compact and square". */
function gridColumns(count: number, boxW: number): number {
  if (count <= 1) return 1;
  const maxCols = Math.max(1, Math.floor((MAX_GRID_WIDTH + GAP_X) / (boxW + GAP_X)));
  const idealCols = Math.ceil(Math.sqrt(count));
  return Math.min(count, maxCols, idealCols);
}

/**
 * A small building-elevation / row-of-houses diagram of everything mapped
 * so far — one card per Wing (floors stacked, flats as windows) or Row
 * (a grid of houses), colored by occupancy (green = a Resident is linked,
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

  const wingGroups = groupByPrefix(wings);
  const rowGroups = groupByPrefix(rows);

  return (
    <div className="space-y-3">
      <div className="space-y-6 overflow-x-auto pb-1">
        {wingGroups.map((group) => (
          <div key={group[0].id} className="flex flex-wrap gap-8 items-end">
            {group.map((w) => (
              <BuildingCard
                key={w.id}
                wing={w}
                properties={properties.filter((p) => p.location_id === w.id)}
                onSelectUnit={onSelectUnit}
              />
            ))}
          </div>
        ))}
        {rowGroups.map((group) => (
          <div key={group[0].id} className="flex flex-wrap gap-8 items-end">
            {group.map((r) => (
              <RowCard
                key={r.id}
                row={r}
                properties={properties.filter((p) => p.location_id === r.id)}
                onSelectUnit={onSelectUnit}
              />
            ))}
          </div>
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

/** A floor's flats laid out in a wrapped grid (not one row) — a floor
 * with a lot of flats on it stays a compact block instead of stretching
 * the whole building sideways. `cols` is shared across every floor in
 * the same building so the columns line up. */
function floorGrid(flats: PropertyOut[], cols: number): { rows: number } {
  return { rows: flats.length === 0 ? 1 : Math.ceil(flats.length / cols) };
}

// Room on the left of each floor's row for its floor number ("5", "4", ...)
// — without this the Overview diagram showed flats grouped into bands with
// no way to tell which floor a band was (unlike the live mapping preview,
// which labels every floor as it's built).
const FLOOR_LABEL_W = 28;

function BuildingCard({
  wing, properties, onSelectUnit,
}: { wing: SocietyLocationOut; properties: PropertyOut[]; onSelectUnit?: (locationId: string, floorNumber: number | null) => void }) {
  const floors = groupFlatsByFloor(properties);
  if (floors.length === 0) return <EmptyCard label={wing.name} />;

  const winW = boxWidthFor(properties.map((p) => p.house_number), WIN_W);
  const maxFlats = Math.max(...floors.map((f) => f.flats.length), 1);
  const cols = gridColumns(maxFlats, winW);
  const gridWidth = SIDE_PAD * 2 + cols * winW + (cols - 1) * GAP_X;
  const width = FLOOR_LABEL_W + gridWidth;

  const floorLayouts = floors.map((floor) => floorGrid(floor.flats, cols));
  const floorHeights = floorLayouts.map((l) => l.rows * WIN_H + (l.rows - 1) * GAP_Y + 12);
  const height = floorHeights.reduce((a, b) => a + b, 0);

  let yCursor = 0;
  const floorTops = floorHeights.map((h) => {
    const top = yCursor;
    yCursor += h;
    return top;
  });

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{wing.name}</div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <rect x={FLOOR_LABEL_W} y={0} width={gridWidth} height={height} fill="#FFFFFF" stroke="#0A1F44" strokeWidth={1.5} />
        {floors.map((floor, i) => {
          const floorTop = floorTops[i];
          const floorH = floorHeights[i];
          const n = floor.flats.length;
          const gridW = Math.min(n, cols) * winW + (Math.min(n, cols) - 1) * GAP_X;
          const startX = FLOOR_LABEL_W + (gridWidth - gridW) / 2;
          const gridTop = floorTop + (floorH - floorLayouts[i].rows * WIN_H - (floorLayouts[i].rows - 1) * GAP_Y) / 2;
          return (
            <g key={floor.floorNumber}>
              {i > 0 && <line x1={FLOOR_LABEL_W} y1={floorTop} x2={width} y2={floorTop} stroke="#E3E6EB" strokeWidth={1} />}
              <text
                x={FLOOR_LABEL_W / 2} y={floorTop + floorH / 2 + 5} textAnchor="middle" fontSize={14} fontWeight={700}
                fill="#0A1F44"
              >
                {floor.floorNumber}
              </text>
              {floor.flats.map((p, j) => {
                const col = j % cols;
                const row = Math.floor(j / cols);
                const wx = startX + col * (winW + GAP_X);
                const wy = gridTop + row * (WIN_H + GAP_Y);
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
                      x={wx + winW / 2} y={wy + WIN_H / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={700}
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

  const LABEL_H = 22; // room for the "Floor <n>" label above each floor's grid
  const sortedFloors = [...floors].sort((a, b) => b - a); // highest at the top
  const flatsPerFloor = sortedFloors.map((f) => properties.filter((p) => p.floor_number === f).sort(byHouseNumber));
  const winW = boxWidthFor(properties.map((p) => p.house_number), WIN_W);
  const maxFlats = Math.max(...flatsPerFloor.map((f) => f.length), 1);
  const cols = gridColumns(maxFlats, winW);
  const width = SIDE_PAD * 2 + cols * winW + (cols - 1) * GAP_X;

  const floorLayouts = flatsPerFloor.map((flats) => floorGrid(flats, cols));
  const floorHeights = floorLayouts.map((l) => LABEL_H + l.rows * WIN_H + (l.rows - 1) * GAP_Y + 8);
  const height = floorHeights.reduce((a, b) => a + b, 0);
  let yCursor = 0;
  const floorTops = floorHeights.map((h) => {
    const top = yCursor;
    yCursor += h;
    return top;
  });

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{wing.name}</div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <rect x={0} y={0} width={width} height={height} fill="#FFFFFF" stroke="#0A1F44" strokeWidth={1.5} />
        {sortedFloors.map((floorNumber, i) => {
          const floorTop = floorTops[i];
          const floorH = floorHeights[i];
          const flats = flatsPerFloor[i];
          const highlighted = highlightFloor === floorNumber;
          const n = flats.length;
          const gridW = Math.min(Math.max(n, 1), cols) * winW + (Math.min(Math.max(n, 1), cols) - 1) * GAP_X;
          const startX = (width - gridW) / 2;
          const gridTop = floorTop + LABEL_H;
          return (
            <g key={floorNumber}>
              {i > 0 && <line x1={0} y1={floorTop} x2={width} y2={floorTop} stroke="#E3E6EB" strokeWidth={1} />}
              {highlighted && (
                <rect
                  x={1} y={floorTop + 1} width={width - 2} height={floorH - 2}
                  fill="#FBF3E4" stroke="#B8873A" strokeWidth={1.5}
                />
              )}
              <text x={width / 2} y={floorTop + 13} textAnchor="middle" fontSize={10} fontWeight={700} fill="#3A4E6E">
                Floor {floorNumber}
              </text>
              {n === 0 ? (
                <text x={width / 2} y={gridTop + WIN_H / 2 + 4} textAnchor="middle" fontSize={10} fill="#9AA5B1">
                  no flats yet
                </text>
              ) : (
                flats.map((p, j) => {
                  const col = j % cols;
                  const row = Math.floor(j / cols);
                  const wx = startX + col * (winW + GAP_X);
                  const wy = gridTop + row * (WIN_H + GAP_Y);
                  const occ = p.is_occupied;
                  return (
                    <g key={p.id}>
                      <rect
                        x={wx} y={wy} width={winW} height={WIN_H} rx={2}
                        fill={occ ? OCC_FILL : VAC_FILL} stroke={occ ? OCC_STROKE : VAC_STROKE} strokeWidth={1.4}
                      />
                      <text
                        x={wx + winW / 2} y={wy + WIN_H / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={700}
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
  const cols = gridColumns(houses.length, houseW);
  const rows = Math.ceil(houses.length / cols);
  const width = cols * houseW + (cols - 1) * GAP_X;
  const height = rows * HOUSE_H + (rows - 1) * GAP_Y;

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-bold text-navy mb-1">{row.name}</div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {houses.map((p, i) => {
          const col = i % cols;
          const rowIdx = Math.floor(i / cols);
          const x = col * (houseW + GAP_X);
          const y = rowIdx * (HOUSE_H + GAP_Y);
          const occ = p.is_occupied;
          return (
            <g
              key={p.id}
              style={{ cursor: onSelectUnit ? "pointer" : "default" }}
              onClick={() => onSelectUnit?.(row.id, null)}
            >
              <title>{`${p.house_number} — ${occ ? "occupied" : "vacant"}`}</title>
              <rect
                x={x} y={y} width={houseW} height={HOUSE_H} rx={4}
                fill={occ ? OCC_FILL : VAC_FILL} stroke={occ ? OCC_STROKE : VAC_STROKE} strokeWidth={1.4}
              />
              <text x={x + houseW / 2} y={y + HOUSE_H / 2 + 4} textAnchor="middle" fontSize={11} fontWeight={700} fill={occ ? OCC_TEXT : VAC_TEXT}>
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
