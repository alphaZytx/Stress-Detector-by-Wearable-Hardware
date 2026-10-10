/** Minimal client-side JWT helpers. We decode (not verify) only to check expiry
 * for routing - the server is the real authority on token validity. */

interface JwtPayload {
  sub?: string;
  email?: string;
  exp?: number; // seconds since epoch
  iat?: number;
}

export function decodeJwt(token: string): JwtPayload | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

/** True if the token is missing, malformed, or past its exp. */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const payload = decodeJwt(token);
  if (!payload?.exp) return true;
  return payload.exp * 1000 <= Date.now();
}
