interface Props {
  properties: { property_id: string; label: string }[];
  activePropertyId: string | null;
  onChange: (id: string) => void;
}

export function PropertySelector({ properties, activePropertyId, onChange }: Props) {
  if (properties.length <= 1) return null;
  return (
    <select
      value={activePropertyId ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className="border border-line rounded px-3 py-1.5 text-sm bg-white"
      aria-label="Select property"
    >
      {properties.map((p) => (
        <option key={p.property_id} value={p.property_id}>
          {p.label}
        </option>
      ))}
    </select>
  );
}
