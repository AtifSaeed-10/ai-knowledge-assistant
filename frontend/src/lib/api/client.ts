export const API_CONFIG = {
  // Update this to your deployed URL when moving to production
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  useMock: process.env.NEXT_PUBLIC_USE_MOCK === 'true',
};

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
