import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/documents?projectId=...&category=...&search=...
 *
 * Returns documents for file-level search (non-semantic).
 * Supports filtering by project, category, and text search.
 */

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId");
  const category = searchParams.get("category");
  const search = searchParams.get("search");

  // Mock response — in production, query Vespa
  return NextResponse.json({
    documents: [],
    total: 0,
    projectId,
    category,
    search,
  });
}
