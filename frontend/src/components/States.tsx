export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-navy-muted text-sm gap-2">
      <div className="w-4 h-4 border-2 border-navy border-t-transparent rounded-full animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-4">
      <div className="w-10 h-10 rounded-full border border-line mb-3" aria-hidden="true" />
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && <p className="text-sm text-navy-muted mt-1 max-w-xs">{description}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-4">
      <p className="text-sm font-medium text-danger">{message ?? "Something went wrong."}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 text-sm text-navy underline">
          Try again
        </button>
      )}
    </div>
  );
}

/** Extracts a human-readable message from an axios error, matching the
 * backend's frozen error shape (docs/API_CONTRACT.md): {"detail": "..."}
 * or Pydantic's {"detail": [{"msg": "..."}]} for validation errors. */
export function apiErrorMessage(e: unknown, fallback = "Something went wrong."): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}
