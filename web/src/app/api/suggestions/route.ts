import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";
import { getBackendUrl } from "@/lib/config";

const logger = getLogger("api/suggestions");

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query");
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  if (!query || query.length < 2) {
    return NextResponse.json({ suggestions: [] });
  }

  try {
    const res = await fetch(
      `${getBackendUrl()}/suggestions?query=${encodeURIComponent(query)}`,
      { headers: { [CORRELATION_HEADER]: correlationId } }
    );

    if (!res.ok) {
      const text = await res.text();
      logger.error("Backend suggestions request failed", {
        status: res.status,
        body: text,
        correlationId,
      });
      return NextResponse.json(
        { error: text || "Backend suggestions failed", correlationId },
        { status: res.status, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    logger.error("Suggestions route error", { error: e, correlationId });
    const message = sanitizeErrorForClient(e);
    return NextResponse.json(
      { error: message, correlationId },
      { status: 500, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  }
}
