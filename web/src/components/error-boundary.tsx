"use client";

import React from "react";
import { getLogger } from "@/lib/logger";

const logger = getLogger("ErrorBoundary");

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * React Error Boundary that catches rendering errors,
 * logs them through the centralized logger, and shows
 * a fallback UI.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    logger.error("Unhandled React rendering error", {
      error,
      componentStack: errorInfo.componentStack ?? undefined,
    });
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex items-center justify-center min-h-[200px] p-6">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-[var(--text-tertiary)] mb-4">
              An unexpected error occurred. Please try refreshing the page.
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 text-sm rounded-md bg-[var(--bg-tertiary)] text-[var(--text-primary)] hover:opacity-80"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
