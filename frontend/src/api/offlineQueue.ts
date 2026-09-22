/**
 * Offline outbox — Section 37: background sync for offline manual "Paid"
 * submission. Backed by IndexedDB (not localStorage — audit fix): payment
 * bodies can include a proof URL and other fields that don't belong in
 * localStorage's small synchronous string store, and IndexedDB stores
 * structured objects directly, so there's no JSON.parse step that a
 * corrupted string could ever fail on — a queue entry is either a valid
 * record in the object store or it simply isn't there.
 *
 * Idempotency (Section 37): every queued POST already carries the
 * client-generated `idempotency_key` your call site set (e.g. payment
 * submission) — replaying a queued request that already succeeded before
 * the "online" event fired is safe; the backend's
 * UNIQUE(maintenance_due_id, idempotency_key) makes a duplicate replay a
 * clean 409, not a duplicate payment.
 */
import { apiClient } from "@/api/client";

const DB_NAME = "hs_offline_outbox";
const DB_VERSION = 1;
const STORE_NAME = "queue";

interface QueuedRequest {
  id: string;
  method: "post" | "patch" | "put";
  url: string;
  body: unknown;
  queuedAt: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const store = tx.objectStore(STORE_NAME);
    const req = fn(store);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

async function readAll(): Promise<QueuedRequest[]> {
  return withStore("readonly", (store) => store.getAll() as IDBRequest<QueuedRequest[]>);
}

export async function enqueue(method: QueuedRequest["method"], url: string, body: unknown): Promise<void> {
  const entry: QueuedRequest = { id: crypto.randomUUID(), method, url, body, queuedAt: new Date().toISOString() };
  await withStore("readwrite", (store) => store.add(entry));
}

export async function pendingCount(): Promise<number> {
  return (await readAll()).length;
}

/** Attempts to replay every queued write, in order. Stops at the first
 * failure that isn't a safely-idempotent 409 — a real error (e.g. still
 * offline) should leave the rest of the queue intact rather than silently
 * drop them.
 *
 * 409-handling is deliberately narrow (fix, audit concern): a 409 only
 * means "already applied, safe to drop" when the queued request itself
 * carries an `idempotency_key` — that's the specific guarantee the
 * backend's `UNIQUE(maintenance_due_id, idempotency_key)` constraint
 * gives us (docs/API_CONTRACT.md). A 409 on a request WITHOUT an
 * idempotency_key could be any other business-rule conflict (e.g. a
 * complaint/booking state that changed while offline) — that must NOT be
 * silently treated as success. It's still removed from the *retry* queue
 * (blindly retrying forever won't resolve a business-rule conflict
 * either), but reported as `failed`, not `succeeded`, so a future UI can
 * surface it to the user instead of the item just vanishing. */
export interface FlushResult {
  succeeded: number;
  failed: number;
  remaining: number;
}

export async function flushQueue(): Promise<FlushResult> {
  const queue = await readAll();
  let succeeded = 0;
  let failed = 0;
  let stoppedAt = -1;

  for (let i = 0; i < queue.length; i++) {
    const req = queue[i];
    const hasIdempotencyKey =
      typeof req.body === "object" && req.body !== null && "idempotency_key" in req.body;

    try {
      await apiClient.request({ method: req.method, url: req.url, data: req.body });
      await withStore("readwrite", (store) => store.delete(req.id));
      succeeded++;
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 409 && hasIdempotencyKey) {
        // Same idempotency_key already applied — genuinely safe to drop.
        await withStore("readwrite", (store) => store.delete(req.id));
        succeeded++;
        continue;
      }
      if (status === 409) {
        // Some other business-rule conflict (not idempotency-guaranteed) —
        // don't keep retrying it automatically, but don't count it as a
        // silent success either. Remove from the queue, report as failed.
        await withStore("readwrite", (store) => store.delete(req.id));
        failed++;
        continue;
      }
      // Genuine failure (still offline, server error) — stop here; this
      // and every request after it stay queued for the next attempt.
      stoppedAt = i;
      break;
    }
  }

  const remaining = stoppedAt === -1 ? 0 : queue.length - stoppedAt;
  return { succeeded, failed, remaining };
}

let listenerAttached = false;
export function attachAutoFlush(onFlushed?: (result: FlushResult) => void): void {
  if (listenerAttached) return;
  listenerAttached = true;
  window.addEventListener("online", () => {
    void flushQueue().then((result) => onFlushed?.(result));
  });
  // Also try once at startup, in case we regained connectivity while closed.
  if (navigator.onLine) {
    void pendingCount().then((count) => {
      if (count > 0) void flushQueue().then((result) => onFlushed?.(result));
    });
  }
}
