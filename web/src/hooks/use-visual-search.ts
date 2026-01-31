"use client";

import { useState, useCallback, useRef } from "react";
import { correlationHeaders, getLogger } from "@/lib/logger";
import type { VisualSearchResult, TokenInfo, SynthesisState, MatchType } from "@/types";

const logger = getLogger("use-visual-search");

interface UseVisualSearchReturn {
  // Search state
  query: string;
  setQuery: (query: string) => void;
  results: VisualSearchResult[];
  queryId: string | null;
  tokenMap: TokenInfo[];
  isSearching: boolean;
  searchError: string | null;
  durationMs: number | null;
  totalCount: number;

  // Selection state
  selectedIds: Set<string>;
  toggleSelection: (id: string) => void;
  selectTopN: (n: number) => void;
  clearSelection: () => void;
  selectAll: () => void;

  // Actions
  search: (searchQuery?: string, ranking?: string) => Promise<void>;

  // Synthesis state
  synthesis: SynthesisState;
  synthesize: () => void;
  cancelSynthesis: () => void;
}

export function useVisualSearch(): UseVisualSearchReturn {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VisualSearchResult[]>([]);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [tokenMap, setTokenMap] = useState<TokenInfo[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [synthesis, setSynthesis] = useState<SynthesisState>({
    isStreaming: false,
    text: "",
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const search = useCallback(async (searchQuery?: string, ranking = "hybrid") => {
    const q = searchQuery ?? query;
    if (!q.trim()) return;

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsSearching(true);
    setSearchError(null);
    setResults([]);
    setSelectedIds(new Set());
    setSynthesis({ isStreaming: false, text: "" });

    try {
      const res = await fetch("/api/visual-search", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...correlationHeaders() },
        body: JSON.stringify({ query: q, ranking, limit: 20 }),
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Search failed" }));
        throw new Error(err.error || `Search failed with status ${res.status}`);
      }

      const data = await res.json();

      // Transform backend response to frontend format
      const transformedResults: VisualSearchResult[] = data.results.map((r: {
        id: string;
        title: string;
        page_number: number;
        snippet: string;
        text?: string;
        blur_image?: string;
        relevance: number;
        url?: string;
        has_original_pdf: boolean;
        match_type?: MatchType;
      }) => ({
        id: r.id,
        title: r.title,
        pageNumber: r.page_number,
        snippet: r.snippet,
        text: r.text,
        blurImage: r.blur_image ? `data:image/jpeg;base64,${r.blur_image}` : undefined,
        relevance: r.relevance,
        url: r.url,
        hasOriginalPdf: r.has_original_pdf,
        selected: false,
        matchType: r.match_type,
      }));

      const transformedTokenMap: TokenInfo[] = (data.token_map || []).map((t: { token: string; token_idx: number }) => ({
        token: t.token,
        tokenIdx: t.token_idx,
      }));

      setResults(transformedResults);
      setQueryId(data.query_id);
      setTokenMap(transformedTokenMap);
      setDurationMs(data.duration_ms);
      setTotalCount(data.total_count);

      logger.info("Visual search completed", {
        resultCount: transformedResults.length,
        durationMs: data.duration_ms,
      });
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") {
        return; // Request was cancelled
      }
      const message = e instanceof Error ? e.message : "Search failed";
      setSearchError(message);
      logger.error("Visual search failed", { error: e });
    } finally {
      setIsSearching(false);
    }
  }, [query]);

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectTopN = useCallback((n: number) => {
    setSelectedIds(new Set(results.slice(0, n).map((r) => r.id)));
  }, [results]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(results.map((r) => r.id)));
  }, [results]);

  const synthesize = useCallback(() => {
    if (selectedIds.size === 0 || !queryId) return;

    // Cancel any existing synthesis
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setSynthesis({ isStreaming: true, text: "" });

    // Get selected doc IDs in order
    const selectedDocIds = results
      .filter((r) => selectedIds.has(r.id))
      .map((r) => r.id);

    const params = new URLSearchParams({
      query_id: queryId,
      query: query,
      doc_ids: selectedDocIds.join(","),
    });

    const eventSource = new EventSource(`/api/synthesize?${params}`);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener("message", (event) => {
      setSynthesis((prev) => ({
        ...prev,
        text: event.data,
      }));
    });

    eventSource.addEventListener("close", () => {
      setSynthesis((prev) => ({
        ...prev,
        isStreaming: false,
      }));
      eventSource.close();
      eventSourceRef.current = null;
    });

    eventSource.onerror = (error) => {
      logger.error("Synthesis SSE error", { error });
      setSynthesis((prev) => ({
        ...prev,
        isStreaming: false,
        error: "Failed to generate response",
      }));
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [selectedIds, queryId, query, results]);

  const cancelSynthesis = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setSynthesis((prev) => ({
      ...prev,
      isStreaming: false,
    }));
  }, []);

  return {
    query,
    setQuery,
    results,
    queryId,
    tokenMap,
    isSearching,
    searchError,
    durationMs,
    totalCount,
    selectedIds,
    toggleSelection,
    selectTopN,
    clearSelection,
    selectAll,
    search,
    synthesis,
    synthesize,
    cancelSynthesis,
  };
}
