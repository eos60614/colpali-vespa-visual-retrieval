import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";
import { getBackendUrl } from "@/lib/config";

const logger = getLogger("api/visual-search");

export async function POST(request: NextRequest) {
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  try {
    const body = await request.json();
    const { query, ranking = "hybrid", limit = 20 } = body;

    if (!query?.trim()) {
      return NextResponse.json(
        { error: "Query is required" },
        { status: 400, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    logger.info("Visual search request", { query, ranking, limit, correlationId });

    const res = await fetch(`${getBackendUrl()}/api/visual-search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [CORRELATION_HEADER]: correlationId,
      },
      body: JSON.stringify({ query, ranking, limit }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Unknown error" }));
      logger.error("Backend visual-search request failed", { status: res.status, error: err.error, correlationId });
      return NextResponse.json(
        { error: err.error || "Search failed" },
        { status: res.status, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    const data = await res.json();
    logger.info("Visual search completed", {
      resultCount: data.results?.length,
      durationMs: data.duration_ms,
      correlationId,
    });

    return NextResponse.json(data, { headers: { [CORRELATION_HEADER]: correlationId } });
  } catch (e) {
    logger.error("Visual-search route error", { error: e, correlationId });
    const message = sanitizeErrorForClient(e);
    return NextResponse.json(
      { error: message },
      { status: 500, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  }
}
