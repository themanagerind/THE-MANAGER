import { QueryClient } from "@tanstack/react-query";

/**
 * Single shared instance (audit fix — cross-account cache leak):
 * src/auth/AuthContext.tsx calls `queryClient.clear()` on every identity
 * transition (login, multi-account selection, role switch, logout) so a
 * query key like ["complaints", "mine"] can never render one user's
 * cached data for the next authenticated identity on a shared device.
 * The backend remains the authoritative access-control boundary
 * regardless — this only prevents a stale *render*.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});
