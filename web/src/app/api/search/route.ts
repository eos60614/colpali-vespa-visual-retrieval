import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/search
 *
 * Proxies search queries to the Python backend (ColPali + Vespa).
 * Expects a JSON body matching the QueryPayload type.
 *
 * In production, this route forwards to the Python backend.
 * Currently returns mock data for frontend development.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

interface SearchPayload {
  projectId: string;
  categories: string[];
  documentIds: string[];
  query: string;
  ranking?: "colpali" | "bm25" | "hybrid";
}

export async function POST(request: NextRequest) {
  try {
    const body: SearchPayload = await request.json();

    if (!body.query?.trim()) {
      return NextResponse.json(
        { error: "Query is required" },
        { status: 400 }
      );
    }

    // In production, forward to Python backend:
    // const res = await fetch(`${BACKEND_URL}/fetch_results`, {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   body: JSON.stringify({
    //     query: body.query,
    //     ranking: body.ranking || "colpali",
    //   }),
    // });
    // return NextResponse.json(await res.json());

    // Mock response for development
    return NextResponse.json({
      results: [],
      query: body.query,
      ranking: body.ranking || "colpali",
      duration_ms: 0,
    });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
