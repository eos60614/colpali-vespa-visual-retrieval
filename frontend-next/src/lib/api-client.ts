import type {
  SearchRequest,
  SearchResponse,
  Project,
  DocsQuery,
  DocsResponse,
  UploadResponse,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:7860";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function search(params: SearchRequest): Promise<SearchResponse> {
  return fetchJSON<SearchResponse>(`${API}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return fetchJSON(`${API}/api/projects`);
}

export async function getProject(id: string): Promise<Project> {
  return fetchJSON(`${API}/api/projects/${id}`);
}

export async function listDocuments(
  projectId: string,
  params: DocsQuery = {}
): Promise<DocsResponse> {
  const sp = new URLSearchParams();
  if (params.category) sp.set("category", params.category);
  if (params.search) sp.set("search", params.search);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return fetchJSON(`${API}/api/projects/${projectId}/documents?${sp}`);
}

export async function uploadDocument(
  projectId: string,
  formData: FormData
): Promise<UploadResponse> {
  const res = await fetch(`${API}/api/projects/${projectId}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export function createChatStream(
  queryId: string,
  query: string,
  docIds: string[]
): EventSource {
  const params = new URLSearchParams({
    query_id: queryId,
    query,
    doc_ids: docIds.join(","),
  });
  return new EventSource(`${API}/api/chat?${params}`);
}

export async function fetchSuggestions(
  query: string,
  projectId?: string
): Promise<string[]> {
  const sp = new URLSearchParams({ query });
  if (projectId) sp.set("project_id", projectId);
  const data = await fetchJSON<{ suggestions: string[] }>(
    `${API}/api/suggestions?${sp}`
  );
  return data.suggestions;
}

export function fullImageUrl(docId: string): string {
  return `${API}/api/images/${docId}/full`;
}

export function blurImageUrl(docId: string): string {
  return `${API}/api/images/${docId}/blur`;
}

export function simMapUrl(
  queryId: string,
  idx: number,
  tokenIdx: number
): string {
  return `${API}/api/sim-maps/${queryId}/${idx}/${tokenIdx}`;
}
