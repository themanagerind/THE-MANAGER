import { describe, expect, it } from "vitest";
import { decodeJwtPayload } from "@/auth/jwt";

function makeFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

describe("decodeJwtPayload", () => {
  it("decodes a well-formed token's payload", () => {
    const token = makeFakeJwt({ sub: "user-123", society_id: "soc-456", active_role: "RESIDENT" });
    const payload = decodeJwtPayload<{ sub: string; society_id: string; active_role: string }>(token);
    expect(payload?.sub).toBe("user-123");
    expect(payload?.society_id).toBe("soc-456");
    expect(payload?.active_role).toBe("RESIDENT");
  });

  it("handles a NULL society_id (Platform Owner)", () => {
    const token = makeFakeJwt({ sub: "user-1", society_id: null });
    const payload = decodeJwtPayload<{ society_id: string | null }>(token);
    expect(payload?.society_id).toBeNull();
  });

  it("returns null for a malformed token instead of throwing", () => {
    expect(decodeJwtPayload("not-a-jwt")).toBeNull();
    expect(decodeJwtPayload("")).toBeNull();
  });
});
