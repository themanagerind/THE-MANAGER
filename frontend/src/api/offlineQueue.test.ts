import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  apiClient: { request: vi.fn() },
}));

import { apiClient } from "@/api/client";
import { enqueue, flushQueue, pendingCount } from "@/api/offlineQueue";

function resetDb(): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.deleteDatabase("hs_offline_outbox");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve(); // best-effort in a test environment
  });
}

describe("offlineQueue (IndexedDB-backed)", () => {
  beforeEach(async () => {
    vi.mocked(apiClient.request).mockReset();
    await resetDb();
  });

  it("starts empty", async () => {
    expect(await pendingCount()).toBe(0);
  });

  it("enqueue adds a request that survives until flushed", async () => {
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });
    expect(await pendingCount()).toBe(1);
  });

  it("flushQueue replays queued requests and clears them on success", async () => {
    vi.mocked(apiClient.request).mockResolvedValue({ data: { id: "payment-1" } });
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });

    const result = await flushQueue();

    expect(result).toEqual({ succeeded: 1, failed: 0, remaining: 0 });
    expect(await pendingCount()).toBe(0);
    expect(apiClient.request).toHaveBeenCalledWith(
      expect.objectContaining({ method: "post", url: "/payments" })
    );
  });

  it("treats a 409 as success ONLY when the request carries an idempotency_key (audit fix — was too broad)", async () => {
    vi.mocked(apiClient.request).mockRejectedValue({ response: { status: 409 } });
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });

    const result = await flushQueue();

    // Section 37: a duplicate replay of an already-applied idempotent
    // write must not be treated as a failure that keeps retrying forever.
    expect(result).toEqual({ succeeded: 1, failed: 0, remaining: 0 });
    expect(await pendingCount()).toBe(0);
  });

  it("a 409 WITHOUT an idempotency_key is reported as failed, not silently succeeded (audit fix)", async () => {
    vi.mocked(apiClient.request).mockRejectedValue({ response: { status: 409 } });
    // e.g. a complaint-assignment or booking-decision write with no
    // idempotency_key — a 409 here is a genuine business-rule conflict,
    // not a safe duplicate.
    await enqueue("patch", "/complaints/abc/status", { status: "RESOLVED" });

    const result = await flushQueue();

    expect(result.succeeded).toBe(0);
    expect(result.failed).toBe(1);
    // Removed from the retry queue either way (retrying won't fix a
    // business-rule conflict), but NOT counted as a success.
    expect(await pendingCount()).toBe(0);
  });

  it("keeps a genuinely failed request (e.g. still offline) queued for next time", async () => {
    vi.mocked(apiClient.request).mockRejectedValue(new Error("Network Error"));
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });

    const result = await flushQueue();

    expect(result.remaining).toBe(1);
    expect(await pendingCount()).toBe(1);
  });

  it("preserves a payment proof URL through the round trip (audit fix — was a localStorage size/shape concern)", async () => {
    vi.mocked(apiClient.request).mockResolvedValue({ data: {} });
    const body = {
      maintenance_due_id: "due-1",
      idempotency_key: "key-1",
      payment_method: "MANUAL_UPI",
      proof_type: "UPI_SCREENSHOT",
      proof_file_url: "https://example.com/very/long/proof/url/with/query?token=abc123",
    };
    await enqueue("post", "/payments", body);
    await flushQueue();
    expect(apiClient.request).toHaveBeenCalledWith(expect.objectContaining({ data: body }));
  });
});

describe("offlineQueue identity isolation (audit fix)", () => {
  function fakeToken(sub: string): string {
    const payload = btoa(JSON.stringify({ sub, society_id: "soc-1" }));
    return `header.${payload}.sig`;
  }

  beforeEach(async () => {
    vi.mocked(apiClient.request).mockReset();
    await resetDb();
    localStorage.clear();
  });

  it("does not replay a different user's queued request", async () => {
    localStorage.setItem("hs_access_token", fakeToken("user-A"));
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });

    // User A logs out, User B logs in on the same device — flush runs
    // under B's identity while A's request is still sitting in the queue.
    localStorage.setItem("hs_access_token", fakeToken("user-B"));
    const result = await flushQueue();

    expect(apiClient.request).not.toHaveBeenCalled();
    expect(result).toEqual({ succeeded: 0, failed: 0, remaining: 0 });
    // A's item is still queued, just invisible to B's own pending count.
    expect(await pendingCount()).toBe(0);
  });

  it("replays a request once its own user is logged in again", async () => {
    localStorage.setItem("hs_access_token", fakeToken("user-A"));
    await enqueue("post", "/payments", { maintenance_due_id: "due-1", idempotency_key: "key-1" });

    localStorage.setItem("hs_access_token", fakeToken("user-B"));
    await flushQueue(); // no-op for B, per the test above

    localStorage.setItem("hs_access_token", fakeToken("user-A"));
    vi.mocked(apiClient.request).mockResolvedValue({ data: { id: "payment-1" } });
    const result = await flushQueue();

    expect(result).toEqual({ succeeded: 1, failed: 0, remaining: 0 });
    expect(apiClient.request).toHaveBeenCalledTimes(1);
  });

  it("only flushes the current user's items, leaving another user's interleaved request untouched", async () => {
    localStorage.setItem("hs_access_token", fakeToken("user-A"));
    await enqueue("post", "/payments", { maintenance_due_id: "due-A", idempotency_key: "key-A" });

    localStorage.setItem("hs_access_token", fakeToken("user-B"));
    await enqueue("post", "/payments", { maintenance_due_id: "due-B", idempotency_key: "key-B" });

    vi.mocked(apiClient.request).mockResolvedValue({ data: { id: "payment-B" } });
    const result = await flushQueue(); // still logged in as B

    expect(result).toEqual({ succeeded: 1, failed: 0, remaining: 0 });
    expect(apiClient.request).toHaveBeenCalledTimes(1);
    expect(apiClient.request).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ maintenance_due_id: "due-B" }) })
    );
  });
});
