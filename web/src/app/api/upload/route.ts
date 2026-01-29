import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";
import { getBackendUrl } from "@/lib/config";

const logger = getLogger("api/upload");

export async function POST(request: NextRequest) {
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  try {
    const formData = await request.formData();

    logger.info("Upload request received", { correlationId });

    const res = await fetch(`${getBackendUrl()}/api/upload`, {
      method: "POST",
      headers: { [CORRELATION_HEADER]: correlationId },
      body: formData,
    });

    // The backend now returns JSON directly
    const data = await res.json();

    if (data.success) {
      logger.info("Upload succeeded", { correlationId, title: data.title, pages: data.pages_indexed });
      return NextResponse.json(data, { headers: { [CORRELATION_HEADER]: correlationId } });
    }

    logger.warn("Upload returned error from backend", {
      errorMessage: data.error,
      correlationId,
    });
    return NextResponse.json(
      { success: false, error: data.error, correlationId },
      { status: res.status, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  } catch (e) {
    logger.error("Upload route error", { error: e, correlationId });
    const message = sanitizeErrorForClient(e);
    return NextResponse.json(
      { success: false, error: message, correlationId },
      { status: 500, headers: { [CORRELATION_HEADER]: correlationId } }
    );
  }
}
