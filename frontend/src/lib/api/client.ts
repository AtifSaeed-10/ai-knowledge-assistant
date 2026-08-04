export const API_CONFIG = {
  // Update this to your deployed URL when moving to production
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  useMock: process.env.NEXT_PUBLIC_USE_MOCK === 'false', // Default to false to use real backend
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