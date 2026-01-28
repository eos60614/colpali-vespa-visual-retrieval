import type { SearchResult, Project, Document } from "@/types";

// ---------------------------------------------------------------------------
// Backend search response shape (mirrors Python /api/search JSON output)
// ---------------------------------------------------------------------------
export interface BackendSearchResult {
  id: string;
  title: string;
  page_number: number;
  snippet: string;
  text: string;
  blur_image: string;
  relevance: number;
  url: string;
}

export interface SearchResponse {
  results: BackendSearchResult[];
  query: string;
  query_id: string;
  doc_ids: string[];
  ranking: string;
  duration_ms: number;
  total_count: number;
}

// ---------------------------------------------------------------------------
// Transform backend result → frontend SearchResult type
// ---------------------------------------------------------------------------
export function transformResult(
  raw: BackendSearchResult,
  index: number,
  maxRelevance: number
): SearchResult {
  // Normalize relevance relative to the top result (0–1 range)
  const normalizedScore = maxRelevance > 0 ? raw.relevance / maxRelevance : 0;

  return {
    id: raw.id,
    documentId: raw.id,
    title: raw.title,
    pageNumber: raw.page_number,
    snippet: raw.snippet,
    relevanceScore: Math.min(normalizedScore, 1),
    category: "other",
    blurImage: raw.blur_image
      ? `data:image/jpeg;base64,${raw.blur_image}`
      : undefined,
    text: raw.text || undefined,
  };
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

export async function searchDocuments(
  query: string,
  ranking: string = "hybrid",
  signal?: AbortSignal
): Promise<SearchResponse> {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, ranking }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Search failed" }));
    throw new Error(err.error || "Search failed");
  }
  return res.json();
}

export async function getSuggestions(
  query: string,
  signal?: AbortSignal
): Promise<string[]> {
  const res = await fetch(
    `/api/suggestions?query=${encodeURIComponent(query)}`,
    { signal }
  );
  if (!res.ok) return [];
  const data = await res.json();
  return data.suggestions ?? [];
}

export async function getFullImage(docId: string): Promise<string> {
  const res = await fetch(
    `/api/image?doc_id=${encodeURIComponent(docId)}`
  );
  if (!res.ok) throw new Error("Failed to load image");
  const data = await res.json();
  return data.image;
}

/**
 * Returns the URL for the SSE chat stream.
 * The caller should open an EventSource on this URL.
 */
export function getChatStreamUrl(
  queryId: string,
  query: string,
  docIds: string[]
): string {
  const params = new URLSearchParams({
    query_id: queryId,
    query,
    doc_ids: docIds.join(","),
  });
  return `/api/chat?${params.toString()}`;
}

// ---------------------------------------------------------------------------
// Procore data APIs
// ---------------------------------------------------------------------------

export async function getProjects(
  signal?: AbortSignal
): Promise<{ projects: Project[] }> {
  const res = await fetch("/api/projects", { signal });
  if (!res.ok) {
    return { projects: [] };
  }
  return res.json();
}

export interface GetDocumentsParams {
  projectId?: string;
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export async function getDocuments(
  params: GetDocumentsParams = {},
  signal?: AbortSignal
): Promise<{ documents: Document[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params.projectId) searchParams.set("projectId", params.projectId);
  if (params.category) searchParams.set("category", params.category);
  if (params.search) searchParams.set("search", params.search);
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));

  const res = await fetch(`/api/documents?${searchParams.toString()}`, {
    signal,
  });
  if (!res.ok) {
    return { documents: [], total: 0 };
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export async function uploadDocument(
  formData: FormData,
  signal?: AbortSignal
): Promise<{ success: boolean; message: string }> {
  const res = await fetch("/api/upload", {
    method: "POST",
    body: formData,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Upload failed" }));
    throw new Error(err.error || "Upload failed");
  }
  return res.json();
}
