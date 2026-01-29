"use client";

import { useEffect } from "react";
import { ErrorBoundary } from "@/components/error-boundary";
import { getLogger, getCorrelationId } from "@/lib/logger";

const logger = getLogger("GlobalErrorHandler");

/**
 * Client-side error boundary wrapper that also installs
 * global handlers for unhandled promise rejections and errors.
 */
export function ClientErrorBoundary({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    // Catch unhandled promise rejections globally
    function handleUnhandledRejection(event: PromiseRejectionEvent) {
      logger.error("Unhandled promise rejection", {
        error: event.reason,
        correlationId: getCorrelationId(),
      });
    }

    // Catch global uncaught errors
    function handleError(event: ErrorEvent) {
      logger.error("Uncaught global error", {
        error: event.error,
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      });
    }

    window.addEventListener("unhandledrejection", handleUnhandledRejection);
    window.addEventListener("error", handleError);

    return () => {
      window.removeEventListener(
        "unhandledrejection",
        handleUnhandledRejection
      );
      window.removeEventListener("error", handleError);
    };
  }, []);

  return <ErrorBoundary>{children}</ErrorBoundary>;
}
