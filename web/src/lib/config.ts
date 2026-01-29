/**
 * Configuration utilities with strict validation.
 * No fallbacks - missing required config throws errors for easier debugging.
 */

/**
 * Get a required environment variable. Throws if not set.
 */
export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name}. ` +
      `Set it in .env.local or your deployment environment.`
    );
  }
  return value;
}

/**
 * Get the backend URL. Throws if BACKEND_URL is not set.
 */
export function getBackendUrl(): string {
  return requireEnv("BACKEND_URL");
}
