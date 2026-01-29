/**
 * Centralized frontend logger for the Next.js application.
 *
 * Provides structured logging with correlation ID support,
 * environment-aware behavior, and secret redaction.
 *
 * Usage:
 *   import { logger } from "@/lib/logger";
 *   logger.info("Search started", { query: "test" });
 *   logger.error("Search failed", { error: err });
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type LogLevel = "debug" | "info" | "warn" | "error" | "fatal";

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  service: string;
  context: string;
  correlationId: string | null;
  message: string;
  data?: Record<string, unknown>;
  stackTrace?: string;
}

// ---------------------------------------------------------------------------
// Correlation ID management
// ---------------------------------------------------------------------------
let _correlationId: string | null = null;

export const CORRELATION_HEADER = "x-correlation-id";

export function generateCorrelationId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getCorrelationId(): string {
  if (!_correlationId) {
    _correlationId = generateCorrelationId();
  }
  return _correlationId;
}

export function setCorrelationId(id: string): void {
  _correlationId = id;
}

/**
 * Build headers that include the correlation ID for backend requests.
 */
export function correlationHeaders(): Record<string, string> {
  return {
    [CORRELATION_HEADER]: getCorrelationId(),
  };
}

// ---------------------------------------------------------------------------
// Environment detection
// ---------------------------------------------------------------------------
function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}

function isServer(): boolean {
  return typeof window === "undefined";
}

// ---------------------------------------------------------------------------
// Secret redaction
// ---------------------------------------------------------------------------
const SECRET_PATTERNS = [
  /api[_-]?key\s*[:=]\s*['"]?[\w\-]{10,}['"]?/gi,
  /token\s*[:=]\s*['"]?[\w\-]{10,}['"]?/gi,
  /password\s*[:=]\s*['"]?[^\s'"]{4,}['"]?/gi,
  /Bearer\s+[\w\-.]{10,}/gi,
];

function redactSecrets(message: string): string {
  let result = message;
  for (const pattern of SECRET_PATTERNS) {
    result = result.replace(pattern, (match) => {
      const colonIdx = match.search(/[:=]/);
      if (colonIdx >= 0) {
        return match.substring(0, colonIdx + 1) + " [REDACTED]";
      }
      // Bearer token
      const bearerIdx = match.toLowerCase().indexOf("bearer ");
      if (bearerIdx >= 0) {
        return match.substring(0, bearerIdx + 7) + "[REDACTED]";
      }
      return "[REDACTED]";
    });
  }
  return result;
}

// ---------------------------------------------------------------------------
// Sanitize error payloads for client exposure
// ---------------------------------------------------------------------------
export function sanitizeErrorForClient(error: unknown): string {
  if (isProduction()) {
    return "An unexpected error occurred. Please try again.";
  }
  if (error instanceof Error) {
    return redactSecrets(error.message);
  }
  if (typeof error === "string") {
    return redactSecrets(error);
  }
  return "An unexpected error occurred.";
}

// ---------------------------------------------------------------------------
// Logger implementation
// ---------------------------------------------------------------------------
const SERVICE_NAME = "copoly-web";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  fatal: 4,
};

function getMinLevel(): LogLevel {
  if (isProduction()) return "info";
  return "debug";
}

function shouldLog(level: LogLevel): boolean {
  return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[getMinLevel()];
}

function formatEntry(
  level: LogLevel,
  message: string,
  context: string,
  data?: Record<string, unknown>,
  error?: unknown
): LogEntry {
  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE_NAME,
    context,
    correlationId: _correlationId,
    message: redactSecrets(message),
  };

  if (data) {
    entry.data = data;
  }

  if (error instanceof Error && error.stack) {
    entry.stackTrace = redactSecrets(error.stack);
  }

  return entry;
}

function emit(entry: LogEntry): void {
  // In production: always output structured JSON
  // In development: use readable console methods
  if (isProduction() || isServer()) {
    const output = JSON.stringify(entry);
    switch (entry.level) {
      case "error":
      case "fatal":
        console.error(output);
        break;
      case "warn":
        console.warn(output);
        break;
      default:
        console.log(output);
    }
  } else {
    // Development browser: use console methods with readable output
    const prefix = `[${entry.level.toUpperCase()}] ${entry.context}`;
    const cid = entry.correlationId
      ? ` [${entry.correlationId.slice(0, 8)}]`
      : "";
    switch (entry.level) {
      case "error":
      case "fatal":
        console.error(`${prefix}${cid}:`, entry.message, entry.data ?? "");
        if (entry.stackTrace) console.error(entry.stackTrace);
        break;
      case "warn":
        console.warn(`${prefix}${cid}:`, entry.message, entry.data ?? "");
        break;
      case "debug":
        console.debug(`${prefix}${cid}:`, entry.message, entry.data ?? "");
        break;
      default:
        console.log(`${prefix}${cid}:`, entry.message, entry.data ?? "");
    }
  }
}

function createLogger(context: string) {
  return {
    debug(message: string, data?: Record<string, unknown>): void {
      if (!shouldLog("debug")) return;
      emit(formatEntry("debug", message, context, data));
    },

    info(message: string, data?: Record<string, unknown>): void {
      if (!shouldLog("info")) return;
      emit(formatEntry("info", message, context, data));
    },

    warn(message: string, data?: Record<string, unknown>): void {
      if (!shouldLog("warn")) return;
      emit(formatEntry("warn", message, context, data));
    },

    error(
      message: string,
      data?: Record<string, unknown> & { error?: unknown }
    ): void {
      if (!shouldLog("error")) return;
      const error = data?.error;
      emit(formatEntry("error", message, context, data, error));
    },

    fatal(
      message: string,
      data?: Record<string, unknown> & { error?: unknown }
    ): void {
      // Fatal is always logged regardless of level
      const error = data?.error;
      emit(formatEntry("fatal", message, context, data, error));
    },
  };
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/** Default application-wide logger */
export const logger = createLogger("app");

/** Create a logger with a specific context name */
export function getLogger(context: string) {
  return createLogger(context);
}
