import { describe, expect, it } from "vitest";
import { tokenStorage } from "@/auth/tokenStorage";

function makeFakeAccessToken(sub: string, societyId: string | null): string {
  const header = btoa(JSON.stringify({ alg: "HS256" }));
  const body = btoa(JSON.stringify({ sub, society_id: societyId, active_role: "RESIDENT" }));
  return `${header}.${body}.sig`;
}

describe("tokenStorage", () => {
  it("returns null for everything before any tokens are set", () => {
    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getUserId()).toBeNull();
    expect(tokenStorage.getSocietyId()).toBeNull();
    expect(tokenStorage.getAvailableRoles()).toEqual([]);
  });

  it("setTokens stores access/refresh/role state, and getUserId/getSocietyId read from the JWT itself", () => {
    const access = makeFakeAccessToken("user-abc", "soc-xyz");
    tokenStorage.setTokens(access, "refresh-token-1", "RESIDENT", ["RESIDENT"]);

    expect(tokenStorage.getAccessToken()).toBe(access);
    expect(tokenStorage.getRefreshToken()).toBe("refresh-token-1");
    expect(tokenStorage.getActiveRole()).toBe("RESIDENT");
    expect(tokenStorage.getAvailableRoles()).toEqual(["RESIDENT"]);
    expect(tokenStorage.getUserId()).toBe("user-abc");
    expect(tokenStorage.getSocietyId()).toBe("soc-xyz");
  });

  it("clear() removes everything", () => {
    tokenStorage.setTokens(makeFakeAccessToken("u", "s"), "r", "ADMIN", ["ADMIN", "RESIDENT"]);
    tokenStorage.clear();
    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getRefreshToken()).toBeNull();
    expect(tokenStorage.getActiveRole()).toBeNull();
    expect(tokenStorage.getUserId()).toBeNull();
  });

  it("Platform Owner: getSocietyId is null (Section 2.1 identity model)", () => {
    tokenStorage.setTokens(makeFakeAccessToken("owner-1", null), "r", "PLATFORM_OWNER", ["PLATFORM_OWNER"]);
    expect(tokenStorage.getSocietyId()).toBeNull();
    expect(tokenStorage.getUserId()).toBe("owner-1");
  });
});
