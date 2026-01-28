import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

/**
 * GET /api/documents?projectId=...&category=...&search=...&limit=...&offset=...
 *
 * Proxies to the backend Procore documents endpoint.
 * Returns real document data from the Procore database via Vespa.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);

    // Forward all query params to backend
    const backendParams = new URLSearchParams();
    const projectId = searchParams.get("projectId");
    const category = searchParams.get("category");
    const search = searchParams.get("search");
    const limit = searchParams.get("limit");
    const offset = searchParams.get("offset");

    if (projectId) backendParams.set("project_id", projectId);
    if (category) backendParams.set("category", category);
    if (search) backendParams.set("search", search);
    if (limit) backendParams.set("limit", limit);
    if (offset) backendParams.set("offset", offset);

    const res = await fetch(
      `${BACKEND_URL}/api/procore/documents?${backendParams.toString()}`
    );

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { documents: [], total: 0, error: text || "Backend request failed" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Internal server error";
    return NextResponse.json(
      { documents: [], total: 0, error: message },
      { status: 500 }
    );
  }
}
