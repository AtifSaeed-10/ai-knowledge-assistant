/**
 * Browser-side session identity.
 *
 * Holds the anonymous trial id and, once signed in, the access token. Kept
 * free of React imports so both the fetch layer and the auth store can use
 * it without a circular dependency.
 */

const GUEST_SESSION_KEY = "docusage_guest_session";

export const GUEST_SESSION_HEADER = "X-Guest-Session";

let cachedSessionId: string | null = null;
let accessToken: string | null = null;

function randomSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function persistSessionId(sessionId: string): void {
  cachedSessionId = sessionId;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(GUEST_SESSION_KEY, sessionId);
  } catch {
    // Private browsing: the id still works for this page lifetime.
  }
}

/** Create the trial id on first visit and reuse it afterwards. */
export function ensureGuestSession(): string {
  if (cachedSessionId) return cachedSessionId;

  if (typeof window === "undefined") {
    // Server render: never persist, never reuse across requests.
    return randomSessionId();
  }

  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(GUEST_SESSION_KEY);
  } catch {
    stored = null;
  }

  const sessionId = stored && stored.trim() ? stored.trim() : randomSessionId();
  persistSessionId(sessionId);
  return sessionId;
}

/**
 * Start a new trial identity. Used after a signed-in account claims this
 * browser's guest work, and again on sign-out, so the next person cannot
 * inherit the previous library.
 */
export function resetGuestSession(): string {
  const sessionId = randomSessionId();
  persistSessionId(sessionId);
  return sessionId;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token && token.trim() ? token.trim() : null;
}

/**
 * Headers that identify the caller. A signed-in token replaces the trial id
 * so the server never has to choose between two identities.
 */
export function sessionHeaders(): Record<string, string> {
  const token = getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return { [GUEST_SESSION_HEADER]: ensureGuestSession() };
}
