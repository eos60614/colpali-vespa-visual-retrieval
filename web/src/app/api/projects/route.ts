import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

/**
 * GET /api/projects
 *
 * Proxies to the backend Procore projects endpoint.
 * Returns real project data from the Procore database via Vespa.
 */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/procore/projects`, {
      next: { revalidate: 60 }, // Cache for 60 seconds
    });

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { projects: [], error: text || "Backend request failed" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Internal server error";
    return NextResponse.json(
      { projects: [], error: message },
      { status: 500 }
    );
  }
}
