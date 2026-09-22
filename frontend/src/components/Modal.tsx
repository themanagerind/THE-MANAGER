import { useEffect, type ReactNode } from "react";

export function Modal({
  open, onClose, title, children,
}: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-navy/40" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="relative bg-white rounded-t-lg md:rounded w-full md:max-w-md max-h-[90vh] overflow-y-auto p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 id="modal-title" className="text-base font-semibold text-navy">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-navy-muted hover:text-navy text-xl leading-none">
            &times;
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
