export interface SearchRequest {
  query: string;
  project_id: string;
  categories?: string[];
  document_ids?: string[];
  ranking?: "hybrid" | "colpali" | "bm25";
  rerank?: boolean;
}

export interface SearchResponse {
  query_id: string;
  results: SearchResult[];
  total_count: number;
  search_time_ms: number;
}

export interface SearchResult {
  doc_id: string;
  title: string;
  page_number: number;
  snippet: string;
  text: string;
  blur_image_url: string;
  full_image_url: string;
  relevance_score: number;
  category: string;
  is_region: boolean;
  sim_map_tokens: string[];
}

export interface DocumentCounts {
  Drawing: number;
  Photo: number;
  Submittal: number;
  RFI: number;
  "Change Order": number;
  Spec: number;
}

export interface Project {
  id: string; // string to avoid JS bigint precision loss
  name: string;
  display_name: string;
  project_number: string;
  address: string;
  city: string;
  state_code: string;
  active: boolean;
  document_count: number;
  document_counts: DocumentCounts;
}

export interface DocumentSummary {
  doc_id: string;
  title: string;
  category: string;
  page_number: number;
  tags: string[];
}

export interface DocsQuery {
  category?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface DocsResponse {
  documents: DocumentSummary[];
  total: number;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  pages_indexed: number;
}

export interface ChatToken {
  content: string;
  done: boolean;
}

export const CATEGORIES = [
  "Drawing",
  "Photo",
  "Submittal",
  "RFI",
  "Change Order",
  "Spec",
] as const;

export type Category = (typeof CATEGORIES)[number];
