import { describe, expect, it } from "vitest";
import { NO_REFRESH_RETRY_PATHS, patchRefreshTokenInBody } from "@/api/client";

describe("NO_REFRESH_RETRY_PATHS (audit finding)", () => {
  it("does NOT exclude /auth/me — it's an authenticated endpoint that needs the refresh-retry treatment", () => {
    // The original bug: a blanket `url.includes("/auth/")` check excluded
    // every auth-prefixed path, including /auth/me, silently contradicting
    // its own comment ("401 -> the axios interceptor tries a refresh") and
    // forcing a full re-login on every reload past the access token's
    // 30-minute lifetime despite a perfectly valid 30-day refresh token.
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/me")).toBe(false);
  });

  it("does NOT exclude /auth/switch-role — it's authenticated and should retry too", () => {
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/switch-role")).toBe(false);
  });

  it("excludes unauthenticated endpoints where 401 means wrong OTP/session, not an expired token", () => {
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/otp/request")).toBe(true);
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/otp/verify")).toBe(true);
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/select-account")).toBe(true);
  });

  it("excludes /auth/token/refresh and /auth/logout to avoid loops/pointless retries", () => {
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/token/refresh")).toBe(true);
    expect(NO_REFRESH_RETRY_PATHS.has("/auth/logout")).toBe(true);
  });
});

describe("patchRefreshTokenInBody (audit finding)", () => {
  it("replaces refresh_token in a JSON body with the freshly-rotated one", () => {
    const body = JSON.stringify({ active_role: "RESIDENT", refresh_token: "stale-already-consumed" });
    const result = patchRefreshTokenInBody(body, "fresh-token-xyz");
    expect(JSON.parse(result as string)).toEqual({ active_role: "RESIDENT", refresh_token: "fresh-token-xyz" });
  });

  it("leaves a body with no refresh_token key untouched", () => {
    const body = JSON.stringify({ foo: "bar" });
    expect(patchRefreshTokenInBody(body, "fresh-token-xyz")).toBe(body);
  });

  it("leaves non-JSON string bodies untouched instead of throwing", () => {
    expect(patchRefreshTokenInBody("not json at all", "fresh-token-xyz")).toBe("not json at all");
  });

  it("leaves a non-string body (e.g. undefined, for a GET request) untouched", () => {
    expect(patchRefreshTokenInBody(undefined, "fresh-token-xyz")).toBeUndefined();
  });
});
