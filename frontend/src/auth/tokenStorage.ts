/**
 * Token storage. Refresh tokens are single-use on the backend (rotation
 * via atomic Redis GETDEL) — storing in localStorage is the pragmatic
 * choice for a PWA with no backend-for-frontend to hold an httpOnly
 * cookie; the tradeoff is XSS exposure, mitigated by keeping the token
 * lifetime short and rotating on every use.
 */
import type { Role } from "@/types/enums";
import { decodeJwtPayload } from "@/auth/jwt";

const ACCESS_KEY = "hs_access_token";
const REFRESH_KEY = "hs_refresh_token";
const ACTIVE_ROLE_KEY = "hs_active_role";
const AVAILABLE_ROLES_KEY = "hs_available_roles";

interface AccessTokenClaims {
  sub: string;
  society_id: string | null;
}

export const tokenStorage = {
  getAccessToken: () => localStorage.getItem(ACCESS_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_KEY),
  getActiveRole: () => localStorage.getItem(ACTIVE_ROLE_KEY) as Role | null,
  getAvailableRoles: (): Role[] => {
    const raw = localStorage.getItem(AVAILABLE_ROLES_KEY);
    return raw ? (JSON.parse(raw) as Role[]) : [];
  },

  /** Read from the access token's own claims — avoids a second round-trip
   * just to know "who am I" (the backend already put it in the token). */
  getUserId: (): string | null => {
    const token = localStorage.getItem(ACCESS_KEY);
    if (!token) return null;
    return decodeJwtPayload<AccessTokenClaims>(token)?.sub ?? null;
  },
  getSocietyId: (): string | null => {
    const token = localStorage.getItem(ACCESS_KEY);
    if (!token) return null;
    return decodeJwtPayload<AccessTokenClaims>(token)?.society_id ?? null;
  },

  setTokens: (accessToken: string, refreshToken: string, activeRole: Role, availableRoles: Role[]) => {
    localStorage.setItem(ACCESS_KEY, accessToken);
    localStorage.setItem(REFRESH_KEY, refreshToken);
    localStorage.setItem(ACTIVE_ROLE_KEY, activeRole);
    localStorage.setItem(AVAILABLE_ROLES_KEY, JSON.stringify(availableRoles));
  },

  /** Updates just the cached role list — for when a mid-session action
   * (e.g. an Admin self-linking as a Resident) grants a new role without
   * a fresh login/switch-role response to carry it. */
  setAvailableRoles: (availableRoles: Role[]) => {
    localStorage.setItem(AVAILABLE_ROLES_KEY, JSON.stringify(availableRoles));
  },

  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(ACTIVE_ROLE_KEY);
    localStorage.removeItem(AVAILABLE_ROLES_KEY);
  },
};
