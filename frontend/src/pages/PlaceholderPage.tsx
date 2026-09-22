export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-navy mb-2">{title}</h1>
      <p className="text-sm text-navy-muted">This screen is being built next.</p>
    </div>
  );
}
