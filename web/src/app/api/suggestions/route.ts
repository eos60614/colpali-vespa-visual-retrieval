import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER } from "@/lib/logger";

const logger = getLogger("api/suggestions");
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query");
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  if (!query || query.length < 2) {
    return NextResponse.json({ suggestions: [] });
  }

  try {
    const res = await fetch(
      `${BACKEND_URL}/suggestions?query=${encodeURIComponent(query)}`,
      { headers: { [CORRELATION_HEADER]: correlationId } }
    );

    if (!res.ok) {
      logger.warn("Backend suggestions request failed", {
        status: res.status,
        correlationId,
      });
      return NextResponse.json({ suggestions: [] });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    logger.error("Suggestions route error", { error: e, correlationId });
    return NextResponse.json({ suggestions: [] });
  }
}
