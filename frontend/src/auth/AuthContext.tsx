import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi, type AccountChoice } from "@/api/auth";
import { tokenStorage } from "@/auth/tokenStorage";
import { attachAutoFlush, type FlushResult } from "@/api/offlineQueue";
import { queryClient } from "@/queryClient";
import type { Role } from "@/types/enums";

/** Must match vite.config.ts workbox.runtimeCaching[].options.cacheName —
 * the ONLY Cache Storage bucket this app writes authenticated/user-scoped
 * responses into. Deleting it on every identity transition closes the
 * cross-user leak (audit finding #16/#18) without nuking Workbox's own
 * precache buckets, which would otherwise force a full asset re-download
 * and briefly break the offline app shell on every login/logout. */
const API_READ_CACHE_NAME = "api-read-cache";

const OFFLINE_QUEUE_EVENT = "hs:offline-queue-flushed";

const OTP_SESSION_KEY = "hs_otp_session_token";

interface AuthState {
  isAuthenticated: boolean;
  activeRole: Role | null;
  availableRoles: Role[];
  userId: string | null;
  societyId: string | null;
  /** True until the startup /auth/me check resolves — fix #3: previously
   * `isAuthenticated` was decided from localStorage alone, so an
   * expired/revoked token could render protected UI for a moment before
   * the first API call 401'd. Consumers should show a loading state (or
   * nothing) while this is true. */
  isBootstrapping: boolean;
}

interface AuthContextValue extends AuthState {
  requestOtp: (mobile: string) => Promise<string | null | undefined>;
  verifyOtp: (mobile: string, otp: string) => Promise<AccountChoice[] | null>;
  selectAccount: (userId: string) => Promise<void>;
  switchRole: (role: Role) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-pulls available_roles from GET /auth/me (always fresh from the
   * DB — see CurrentUser's docstring) and updates local state/storage.
   * Needed because a mid-session action can grant a new role (e.g. an
   * Admin self-linking as a Resident) without a login/switch-role
   * response to carry the update. */
  refreshAvailableRoles: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Fix #7 (narrowed per audit #18): deletes only the named runtime cache
 * this app writes authenticated API responses into, not every Cache
 * Storage bucket — Workbox's own precache (app shell, JS/CSS bundles)
 * stays intact, so login/logout no longer forces a full offline-shell
 * rebuild. Called on every identity transition. */
async function clearPwaCaches(): Promise<void> {
  if (!("caches" in window)) return;
  await caches.delete(API_READ_CACHE_NAME);
}

/** Cross-account cache isolation (audit #16 — CRITICAL): React Query keys
 * like ["complaints", "mine"] don't encode userId/societyId, so without
 * this, a second account logging in on the same device/tab could
 * momentarily render the first account's cached data before its own
 * request resolves. Called on every identity transition — login,
 * multi-account selection, role switch, and logout. */
function resetQueryCache(): void {
  queryClient.cancelQueries().finally(() => queryClient.clear());
}

/** Audit #15: flushQueue()'s succeeded/failed/remaining result previously
 * went nowhere the user could see — a failed offline payment could vanish
 * silently. Broadcast it as a DOM event; components/OfflineQueueBanner.tsx
 * listens and surfaces failures (registration is idempotent inside
 * attachAutoFlush, so this callback is safe to pass from every call site). */
function broadcastFlushResult(result: FlushResult): void {
  if (result.succeeded === 0 && result.failed === 0) return;
  window.dispatchEvent(new CustomEvent<FlushResult>(OFFLINE_QUEUE_EVENT, { detail: result }));
  if (result.failed > 0 || result.succeeded > 0) {
    // A payment (or other queued write) just resolved — the screens
    // showing it are almost certainly now stale.
    void queryClient.invalidateQueries();
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: !!tokenStorage.getAccessToken(),
    activeRole: tokenStorage.getActiveRole(),
    availableRoles: tokenStorage.getAvailableRoles(),
    userId: tokenStorage.getUserId(),
    societyId: tokenStorage.getSocietyId(),
    isBootstrapping: true,
  });
  // Fix #4: sessionStorage (not just React state) so a page reload mid
  // multi-account selection doesn't force restarting the OTP flow. The
  // token itself is short-lived (10 min server-side) so this is safe to
  // persist for the tab's lifetime only.
  const [pendingOtpSessionToken, setPendingOtpSessionTokenState] = useState<string | null>(
    () => sessionStorage.getItem(OTP_SESSION_KEY)
  );
  const setPendingOtpSessionToken = useCallback((token: string | null) => {
    setPendingOtpSessionTokenState(token);
    if (token) sessionStorage.setItem(OTP_SESSION_KEY, token);
    else sessionStorage.removeItem(OTP_SESSION_KEY);
  }, []);

  // Fix #3: validate the stored token against the server once on startup.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!tokenStorage.getAccessToken()) {
        if (!cancelled) setState((prev) => ({ ...prev, isBootstrapping: false }));
        return;
      }
      try {
        await authApi.me(); // 401 -> the axios interceptor tries a refresh;
        // if that also fails it clears tokens and redirects to /login itself.
        if (!cancelled) {
          setState({
            isAuthenticated: true,
            activeRole: tokenStorage.getActiveRole(),
            availableRoles: tokenStorage.getAvailableRoles(),
            userId: tokenStorage.getUserId(),
            societyId: tokenStorage.getSocietyId(),
            isBootstrapping: false,
          });
          attachAutoFlush(broadcastFlushResult);
        }
      } catch {
        if (!cancelled) {
          tokenStorage.clear();
          setState({ isAuthenticated: false, activeRole: null, availableRoles: [], userId: null, societyId: null, isBootstrapping: false });
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const requestOtp = useCallback(async (mobile: string) => {
    const { data } = await authApi.requestOtp(mobile);
    return data.dev_otp;
  }, []);

  const verifyOtp = useCallback(
    async (mobile: string, otp: string) => {
      const { data } = await authApi.verifyOtp(mobile, otp);
      if (data.tokens) {
        await clearPwaCaches();
        resetQueryCache();
        tokenStorage.setTokens(
          data.tokens.access_token, data.tokens.refresh_token,
          data.tokens.active_role, data.tokens.available_roles
        );
        setState({
          isAuthenticated: true, activeRole: data.tokens.active_role,
          availableRoles: data.tokens.available_roles,
          userId: tokenStorage.getUserId(), societyId: tokenStorage.getSocietyId(),
          isBootstrapping: false,
        });
        attachAutoFlush(broadcastFlushResult);
        return null;
      }
      // Multiple accounts share this mobile (Section 2.1) — caller must show
      // a picker and call selectAccount().
      setPendingOtpSessionToken(data.otp_session_token);
      return data.accounts;
    },
    [setPendingOtpSessionToken]
  );

  const selectAccount = useCallback(
    async (userId: string) => {
      if (!pendingOtpSessionToken) throw new Error("No pending OTP session");
      const { data } = await authApi.selectAccount(pendingOtpSessionToken, userId);
      await clearPwaCaches();
      resetQueryCache();
      tokenStorage.setTokens(data.access_token, data.refresh_token, data.active_role, data.available_roles);
      setState({
        isAuthenticated: true, activeRole: data.active_role,
        availableRoles: data.available_roles,
        userId: tokenStorage.getUserId(), societyId: tokenStorage.getSocietyId(),
        isBootstrapping: false,
      });
      setPendingOtpSessionToken(null);
      attachAutoFlush(broadcastFlushResult);
    },
    [pendingOtpSessionToken, setPendingOtpSessionToken]
  );

  const switchRole = useCallback(async (role: Role) => {
    const { data } = await authApi.switchRole(role);
    tokenStorage.setTokens(data.access_token, data.refresh_token, data.active_role, data.available_roles);
    // Same account, but a different role can see an entirely different
    // slice of data (e.g. ADMIN vs RESIDENT) — reset so no query keyed
    // like ["dues", propertyId] from the old role's screens can flash
    // stale content on the new role's dashboard (audit #22).
    resetQueryCache();
    setState((prev) => ({ ...prev, activeRole: data.active_role }));
    // Route transition to the new role's home happens in the caller
    // (RoleSwitcher) right after this resolves — fix #6, confirmed intact.
  }, []);

  const refreshAvailableRoles = useCallback(async () => {
    const { data } = await authApi.me();
    tokenStorage.setAvailableRoles(data.available_roles);
    setState((prev) => ({ ...prev, availableRoles: data.available_roles }));
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Best-effort — clear local state regardless of server response.
      }
    }
    tokenStorage.clear();
    await clearPwaCaches();
    resetQueryCache();
    setState({ isAuthenticated: false, activeRole: null, availableRoles: [], userId: null, societyId: null, isBootstrapping: false });
  }, []);

  const value = useMemo(
    () => ({ ...state, requestOtp, verifyOtp, selectAccount, switchRole, logout, refreshAvailableRoles }),
    [state, requestOtp, verifyOtp, selectAccount, switchRole, logout, refreshAvailableRoles]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
