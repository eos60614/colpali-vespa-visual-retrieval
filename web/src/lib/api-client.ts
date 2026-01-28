import type { SearchResult } from "@/types";
import { correlationHeaders, getLogger } from "@/lib/logger";

const logger = getLogger("api-client");

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
// API helpers — all requests include x-correlation-id
// ---------------------------------------------------------------------------

export async function searchDocuments(
  query: string,
  ranking: string = "hybrid",
  signal?: AbortSignal
): Promise<SearchResponse> {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...correlationHeaders() },
    body: JSON.stringify({ query, ranking }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Search failed" }));
    logger.error("Search request failed", { status: res.status, error: err.error });
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
    { signal, headers: { ...correlationHeaders() } }
  );
  if (!res.ok) return [];
  const data = await res.json();
  return data.suggestions ?? [];
}

export async function getFullImage(docId: string): Promise<string> {
  const res = await fetch(
    `/api/image?doc_id=${encodeURIComponent(docId)}`,
    { headers: { ...correlationHeaders() } }
  );
  if (!res.ok) {
    logger.error("Failed to load image", { docId, status: res.status });
    throw new Error("Failed to load image");
  }
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

export async function uploadDocument(
  formData: FormData,
  signal?: AbortSignal
): Promise<{ success: boolean; message: string }> {
  const res = await fetch("/api/upload", {
    method: "POST",
    headers: { ...correlationHeaders() },
    body: formData,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Upload failed" }));
    logger.error("Upload request failed", { status: res.status, error: err.error });
    throw new Error(err.error || "Upload failed");
  }
  return res.json();
}
