import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    const res = await fetch(`${BACKEND_URL}/upload`, {
      method: "POST",
      body: formData,
    });

    // The backend returns HTML fragments (FastHTML); we parse the response
    // to determine success/failure and return JSON for the Next.js frontend.
    const html = await res.text();

    if (html.includes("upload-success") || html.includes("Successfully")) {
      // Extract title and page count from the HTML if possible
      const titleMatch = html.match(/font-semibold[^>]*>([^<]+)</);
      const pagesMatch = html.match(/(\d+)\s*pages?\s*indexed/i);
      return NextResponse.json({
        success: true,
        message: "Document uploaded successfully",
        title: titleMatch?.[1] || "Document",
        pages_indexed: pagesMatch ? parseInt(pagesMatch[1], 10) : 0,
      });
    }

    // Try to extract error message
    const errorMatch = html.match(/text-destructive[^>]*>([^<]+)</);
    const errorMessage = errorMatch?.[1] || "Upload failed";
    return NextResponse.json(
      { success: false, error: errorMessage },
      { status: 400 }
    );
  } catch (e) {
    const message = e instanceof Error ? e.message : "Upload failed";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
