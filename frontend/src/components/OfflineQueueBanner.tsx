import { useEffect, useState } from "react";
import type { FlushResult } from "@/api/offlineQueue";

const EVENT_NAME = "hs:offline-queue-flushed";
const AUTO_DISMISS_MS = 8000;

/** Audit #15: previously an offline-queued write (e.g. a manual UPI/cash
 * payment submitted while offline) resolved silently once connectivity
 * returned — success or failure both vanished with no on-screen trace.
 * src/auth/AuthContext.tsx broadcasts every flushQueue() result as a
 * `hs:offline-queue-flushed` CustomEvent; this banner surfaces it. */
export function OfflineQueueBanner() {
  const [result, setResult] = useState<FlushResult | null>(null);

  useEffect(() => {
    function onFlushed(e: Event) {
      setResult((e as CustomEvent<FlushResult>).detail);
    }
    window.addEventListener(EVENT_NAME, onFlushed);
    return () => window.removeEventListener(EVENT_NAME, onFlushed);
  }, []);

  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(() => setResult(null), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [result]);

  if (!result || (result.succeeded === 0 && result.failed === 0)) return null;

  const tone = result.failed > 0 ? "border-danger bg-danger/5 text-danger" : "border-success bg-success/5 text-success";

  return (
    <div className={`fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 px-4 py-2.5 rounded border text-sm shadow-sm bg-white ${tone}`}>
      {result.failed > 0 ? (
        <>
          {result.failed} queued {result.failed === 1 ? "item" : "items"} could not be applied
          {result.succeeded > 0 && ` (${result.succeeded} synced successfully)`} — check and retry from the relevant screen.
        </>
      ) : (
        <>
          {result.succeeded} offline {result.succeeded === 1 ? "submission" : "submissions"} synced successfully.
        </>
      )}
      <button className="ml-3 underline" onClick={() => setResult(null)}>
        Dismiss
      </button>
    </div>
  );
}
