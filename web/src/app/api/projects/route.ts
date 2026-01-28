import { NextResponse } from "next/server";

/**
 * GET /api/projects
 *
 * Returns the list of available projects.
 * In production, this queries the Vespa backend for project metadata.
 */

export async function GET() {
  // Mock response — in production, query Vespa or project database
  return NextResponse.json({
    projects: [
      {
        id: "proj-harbor-tower",
        name: "Harbor Tower Mixed-Use",
        description: "32-story mixed-use development at 450 Harbor Blvd",
        documentCount: 1247,
        lastAccessedAt: "2025-01-15T10:30:00Z",
        createdAt: "2024-06-01T00:00:00Z",
      },
      {
        id: "proj-westfield-campus",
        name: "Westfield Corporate Campus",
        description: "Phase 2 expansion — Building C and parking structure",
        documentCount: 834,
        lastAccessedAt: "2025-01-14T16:45:00Z",
        createdAt: "2024-09-15T00:00:00Z",
      },
    ],
  });
}
