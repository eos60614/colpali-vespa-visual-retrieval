import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";
import { getBackendUrl } from "@/lib/config";

const logger = getLogger("api/sim-map");

export async function GET(request: NextRequest) {
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  try {
    const { searchParams } = new URL(request.url);
    const queryId = searchParams.get("query_id");
    const idx = searchParams.get("idx");
    const tokenIdx = searchParams.get("token_idx");

    if (!queryId || idx === null || tokenIdx === null) {
      return NextResponse.json(
        { error: "Missing required parameters: query_id, idx, token_idx" },
        { status: 400, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    const params = new URLSearchParams({
      query_id: queryId,
      idx: idx,
      token_idx: tokenIdx,
    });

    const res = await fetch(`${getBackendUrl()}/api/sim-map?${params}`, {
      headers: { [CORRELATION_HEADER]: correlationId },
    });

    if (!res.ok) {
      logger.error("Backend sim-map request failed", { status: res.status, correlationId });
      return NextResponse.json(
        { ready: false, error: "Failed to fetch similarity map" },
        { status: res.status, headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { headers: { [CORRELATION_HEADER]: correlationId } });
  } catch (e) {
    logger.error("Sim-map route error", { error: e, correlationId });
    const message = sanitizeErrorForClient(e);
    return NextResponse.json(
      { ready: false, error: message },
      { status: 500, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  }
}
