// ============================================================
// KI55 Type Definitions
// ============================================================

export interface Project {
  id: string;
  name: string;
  description?: string;
  documentCount: number;
  lastAccessedAt: string;
  createdAt: string;
  categories: CategoryCount[];
  color?: string;
}

export interface CategoryCount {
  category: DocumentCategory;
  count: number;
}

export type DocumentCategory =
  | "rfi"
  | "drawing"
  | "submittal"
  | "spec"
  | "change_order"
  | "photo"
  | "report"
  | "correspondence"
  | "other";

export const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  rfi: "RFIs",
  drawing: "Drawings",
  submittal: "Submittals",
  spec: "Specifications",
  change_order: "Change Orders",
  photo: "Photos",
  report: "Reports",
  correspondence: "Correspondence",
  other: "Other",
};

export const CATEGORY_COLORS: Record<DocumentCategory, string> = {
  rfi: "#3b82f6",
  drawing: "#8b5cf6",
  submittal: "#10b981",
  spec: "#f59e0b",
  change_order: "#ef4444",
  photo: "#06b6d4",
  report: "#6366f1",
  correspondence: "#ec4899",
  other: "#6b7280",
};

export interface Document {
  id: string;
  title: string;
  documentNumber?: string;
  category: DocumentCategory;
  pageCount: number;
  uploadedAt: string;
  tags: string[];
  url?: string;
}

export interface DocumentMetadata {
  id: string;
  title: string;
  documentNumber?: string;
  category: DocumentCategory;
  pageCount: number;
  fileSize?: string;
  uploadedAt: string;
  modifiedAt?: string;
  tags: string[];
  url?: string;
  // Provenance
  source?: string;
  author?: string;
  revision?: string;
  // Relationships
  relatedDocuments?: RelatedDocument[];
  // Agent-useful fields
  vespaDocId?: string;
  embeddingModel?: string;
  indexedAt?: string;
  extractedTextLength?: number;
  hasRegions?: boolean;
  regionCount?: number;
}

export interface RelatedDocument {
  id: string;
  title: string;
  relationship: "references" | "referenced_by" | "supersedes" | "superseded_by" | "related";
}

export interface SearchScope {
  projectId: string;
  categories: DocumentCategory[];
  documentIds: string[];
}

export interface QueryPayload {
  projectId: string;
  categories: DocumentCategory[];
  documentIds: string[];
  query: string;
  ranking?: "colpali" | "bm25" | "hybrid";
}

export interface SearchResult {
  id: string;
  documentId: string;
  title: string;
  pageNumber: number;
  snippet: string;
  relevanceScore: number;
  category: DocumentCategory;
  blurImage?: string;
  fullImage?: string;
  text?: string;
  highlights?: BoundingBox[];
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
}

export interface AIAnswer {
  text: string;
  citations: Citation[];
  isStreaming: boolean;
}

export interface Citation {
  sourceIndex: number;
  resultId: string;
  text: string;
  pageNumber: number;
  documentTitle: string;
}

export interface RecentQuery {
  id: string;
  query: string;
  projectId: string;
  timestamp: string;
  resultCount: number;
}

export interface RecentDocument {
  id: string;
  title: string;
  pageNumber: number;
  accessedAt: string;
}

// ============================================================
// Visual Search Types
// ============================================================

export interface VisualSearchResult {
  id: string;
  title: string;
  pageNumber: number;
  snippet: string;
  text?: string;
  blurImage?: string;
  relevance: number;
  url?: string;
  hasOriginalPdf: boolean;
  selected?: boolean;
}

export interface VisualSearchResponse {
  results: VisualSearchResult[];
  query: string;
  queryId: string;
  docIds: string[];
  ranking: string;
  durationMs: number;
  totalCount: number;
  tokenMap: TokenInfo[];
}

export interface TokenInfo {
  token: string;
  tokenIdx: number;
}

export interface SimilarityMapState {
  queryId: string;
  resultIndex: number;
  tokenIdx: number;
  ready: boolean;
  image?: string;
  loading: boolean;
}

export interface SynthesisState {
  isStreaming: boolean;
  text: string;
  error?: string;
}
