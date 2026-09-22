/** Decodes a JWT's payload without verifying the signature — safe here
 * because the token was issued by our own backend and every request is
 * re-verified server-side anyway (Section 49.14: the frontend never treats
 * token contents as authoritative for authorization, only for display). */
export function decodeJwtPayload<T = Record<string, unknown>>(token: string): T | null {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}
