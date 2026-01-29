import { NextRequest, NextResponse } from "next/server";
import { getLogger, CORRELATION_HEADER, sanitizeErrorForClient } from "@/lib/logger";
import { getBackendUrl } from "@/lib/config";

const logger = getLogger("api/upload");

export async function POST(request: NextRequest) {
  const correlationId = request.headers.get(CORRELATION_HEADER) || "";

  try {
    const formData = await request.formData();

    logger.info("Upload request received", { correlationId });

    const res = await fetch(`${getBackendUrl()}/upload`, {
      method: "POST",
      headers: { [CORRELATION_HEADER]: correlationId },
      body: formData,
    });

    // The backend returns HTML fragments (FastHTML); we parse the response
    // to determine success/failure and return JSON for the Next.js frontend.
    const html = await res.text();

    if (html.includes("upload-success") || html.includes("Successfully")) {
      // Extract title and page count from the HTML if possible
      const titleMatch = html.match(/font-semibold[^>]*>([^<]+)</);
      const pagesMatch = html.match(/(\d+)\s*pages?\s*indexed/i);
      logger.info("Upload succeeded", { correlationId });
      return NextResponse.json(
        {
          success: true,
          message: "Document uploaded successfully",
          title: titleMatch?.[1] || "Document",
          pages_indexed: pagesMatch ? parseInt(pagesMatch[1], 10) : 0,
        },
        { headers: { [CORRELATION_HEADER]: correlationId } }
      );
    }

    // Try to extract error message
    const errorMatch = html.match(/text-destructive[^>]*>([^<]+)</);
    const errorMessage = errorMatch?.[1] || "Upload failed";
    logger.warn("Upload returned error from backend", {
      errorMessage,
      correlationId,
    });
    return NextResponse.json(
      { success: false, error: errorMessage, correlationId },
      { status: 400, headers: { [CORRELATION_HEADER]: correlationId } }
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
