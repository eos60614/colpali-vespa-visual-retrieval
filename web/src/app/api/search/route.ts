import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";

const logger = getLogger("api/search");
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

export async function POST(request: NextRequest) {
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  try {
    const body = await request.json();

    if (!body.query?.trim()) {
      return NextResponse.json(
        { error: "Query is required", correlationId },
        { status: 400, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    logger.info("Search request received", {
      query: body.query,
      ranking: body.ranking || "hybrid",
      correlationId,
    });

    const res = await fetch(`${BACKEND_URL}/api/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [CORRELATION_HEADER]: correlationId,
      },
      body: JSON.stringify({
        query: body.query,
        ranking: body.ranking || "hybrid",
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      logger.error("Backend search failed", {
        status: res.status,
        correlationId,
      });
      return NextResponse.json(
        { error: text || "Backend search failed", correlationId },
        { status: res.status, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, {
      headers: { [CORRELATION_HEADER]: correlationId },
    });
  } catch (e) {
    logger.error("Search route error", { error: e, correlationId });
    const message = sanitizeErrorForClient(e);
    return NextResponse.json(
      { error: message, correlationId },
      { status: 500, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  }
}
