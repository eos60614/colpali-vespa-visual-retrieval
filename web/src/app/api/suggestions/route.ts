import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/suggestions?query=...
 *
 * Returns autocomplete suggestions from the Vespa backend.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query");

  if (!query || query.length < 2) {
    return NextResponse.json({ suggestions: [] });
  }

  // In production, forward to Python backend:
  // const res = await fetch(`${BACKEND_URL}/suggestions?query=${encodeURIComponent(query)}`);
  // return NextResponse.json(await res.json());

  return NextResponse.json({ suggestions: [] });
}
