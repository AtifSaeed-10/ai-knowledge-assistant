import { sessionHeaders } from '@/lib/guestSession';

export const API_CONFIG = {
  // Update this to your deployed URL when moving to production
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  useMock: process.env.NEXT_PUBLIC_USE_MOCK === 'true',
};

/** Which allowance ran out, so the UI can explain the right next step. */
export type QuotaResource = 'pdfs' | 'questions';

export interface QuotaErrorInfo {
  message: string;
  resource: QuotaResource | string;
  limit: number;
  used: number;
  upgradeHint: string;
}

/** The trial or monthly allowance is spent; the caller should offer sign-in. */
export class QuotaExceededError extends Error {
  readonly info: QuotaErrorInfo;

  constructor(info: QuotaErrorInfo) {
    super(info.message);
    this.name = 'QuotaExceededError';
    this.info = info;
  }
}

/** The server needs a valid identity before it will answer. */
export class AuthRequiredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthRequiredError';
  }
}

/** Signed in, but this account is not allowed to see the resource. */
export class ForbiddenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ForbiddenError';
  }
}

type ErrorDetail = {
  code?: string;
  message?: string;
  resource?: string;
  limit?: number;
  used?: number;
  upgrade_hint?: string;
};

async function readErrorDetail(response: Response): Promise<ErrorDetail | null> {
  try {
    const body = (await response.json()) as { detail?: ErrorDetail | string };
    const detail = body?.detail;
    if (detail && typeof detail === 'object') return detail;
    if (typeof detail === 'string') return { message: detail };
  } catch {
    // Non-JSON error body; callers fall back to a status-based message.
  }
  return null;
}

type QuotaHandler = (info: QuotaErrorInfo) => void;

let quotaHandler: QuotaHandler | null = null;

/**
 * Register the app-wide reaction to a spent allowance (opening the signup
 * modal). Kept as a callback so the fetch layer does not import the store.
 */
export function setQuotaHandler(handler: QuotaHandler | null): void {
  quotaHandler = handler;
}

/** Convert a platform error response into a typed error. */
async function raiseForStatus(response: Response, fallback: string): Promise<never> {
  const detail = await readErrorDetail(response);

  if (response.status === 402 && detail?.code === 'QUOTA_EXCEEDED') {
    const info: QuotaErrorInfo = {
      message: detail.message || 'You have reached your free limit.',
      resource: detail.resource || 'questions',
      limit: typeof detail.limit === 'number' ? detail.limit : 0,
      used: typeof detail.used === 'number' ? detail.used : 0,
      upgradeHint: detail.upgrade_hint || 'sign_in',
    };
    quotaHandler?.(info);
    throw new QuotaExceededError(info);
  }

  if (response.status === 401) {
    throw new AuthRequiredError(detail?.message || 'Sign in to continue.');
  }

  if (response.status === 403) {
    throw new ForbiddenError(detail?.message || 'You do not have access.');
  }

  throw new Error(detail?.message || `${fallback} (${response.status}).`);
}

/**
 * Single entry point for API calls: attaches the session identity and turns
 * platform errors into typed errors. Paths are relative, e.g. '/documents'.
 */
export async function apiFetch(
  path: string,
  init: RequestInit & { errorMessage?: string } = {}
): Promise<Response> {
  const { errorMessage, headers, ...rest } = init;

  const response = await fetch(`${API_CONFIG.baseUrl}${path}`, {
    ...rest,
    headers: { ...sessionHeaders(), ...(headers as Record<string, string> | undefined) },
  });

  if (!response.ok) {
    await raiseForStatus(response, errorMessage || 'Request failed');
  }

  return response;
}

/** apiFetch plus JSON parsing, for the common case. */
export async function apiJson<T>(
  path: string,
  init: RequestInit & { errorMessage?: string } = {}
): Promise<T> {
  const response = await apiFetch(path, init);
  return (await response.json()) as T;
}

/**
 * Simulates network latency for mock calls
 */
export const delay = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

/**
 * Health check utility
 */
export const checkHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${API_CONFIG.baseUrl}/health`);
    return response.ok;
  } catch {
    return false;
  }
};

/** Network failures surface as TypeError; give those a human explanation. */
export function toUserMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError) {
    return "Can't reach the DocuSage server. Check that it is running and try again.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
