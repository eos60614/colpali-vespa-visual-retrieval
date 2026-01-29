"use client";

import { useState, useCallback, useRef } from "react";
import type { SearchResult, AIAnswer, DocumentCategory, RecentQuery } from "@/types";
import {
  searchDocuments,
  transformResult,
  getChatStreamUrl,
  type SearchResponse,
} from "@/lib/api-client";
import { getLogger } from "@/lib/logger";

const logger = getLogger("useSearch");

export function useSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<AIAnswer | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [recentQueries, setRecentQueries] = useState<RecentQuery[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      return JSON.parse(localStorage.getItem("ki55_recent_queries") || "[]");
    } catch (e) {
      console.error("[useSearch] Failed to parse recent queries from localStorage:", e);
      return [];
    }
  });
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [searchDuration, setSearchDuration] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const addRecentQuery = useCallback(
    (q: string, projectId: string, resultCount: number) => {
      setRecentQueries((prev) => {
        const newEntry: RecentQuery = {
          id: `rq-${Date.now()}`,
          query: q,
          projectId,
          timestamp: new Date().toISOString(),
          resultCount,
        };
        const filtered = prev.filter((rq) => rq.query !== q);
        const updated = [newEntry, ...filtered].slice(0, 20);
        try {
          localStorage.setItem("ki55_recent_queries", JSON.stringify(updated));
        } catch (e) {
          console.error("[useSearch] Failed to save recent queries to localStorage:", e);
        }
        return updated;
      });
    },
    []
  );

  const search = useCallback(
    async (
      searchQuery: string,
      projectId: string,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      categories: DocumentCategory[],
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      documentIds: string[]
    ) => {
      if (!searchQuery.trim()) return;

      // Abort previous search & SSE
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      eventSourceRef.current?.close();
      eventSourceRef.current = null;

      setQuery(searchQuery);
      setResults([]);
      setAnswer(null);
      setIsSearching(true);
      setIsStreaming(false);
      setSelectedResultId(null);
      setSearchDuration(null);

      try {
        const data: SearchResponse = await searchDocuments(
          searchQuery,
          "hybrid",
          abortRef.current.signal
        );

        // Transform backend results to frontend types
        const maxRelevance =
          data.results.length > 0
            ? Math.max(...data.results.map((r) => r.relevance))
            : 1;

        const transformed = data.results.map((r, i) =>
          transformResult(r, i, maxRelevance)
        );

        setResults(transformed);
        setSearchDuration(data.duration_ms);
        setIsSearching(false);

        if (transformed.length > 0) {
          setSelectedResultId(transformed[0].id);
        }

        addRecentQuery(searchQuery, projectId, transformed.length);

        // Start SSE chat streaming if we have results
        if (data.doc_ids.length > 0) {
          setIsStreaming(true);
          setAnswer({ text: "", citations: [], isStreaming: true });

          const url = getChatStreamUrl(
            data.query_id,
            searchQuery,
            data.doc_ids
          );

          const es = new EventSource(url);
          eventSourceRef.current = es;

          es.addEventListener("message", (event) => {
            const text = event.data;
            setAnswer({
              text,
              citations: transformed.map((r, i) => ({
                sourceIndex: i,
                resultId: r.id,
                text: r.title,
                pageNumber: r.pageNumber,
                documentTitle: r.title,
              })),
              isStreaming: true,
            });
          });

          es.addEventListener("close", () => {
            setAnswer((prev) =>
              prev ? { ...prev, isStreaming: false } : null
            );
            setIsStreaming(false);
            es.close();
            eventSourceRef.current = null;
          });

          es.addEventListener("error", (event) => {
            console.error("[useSearch] SSE stream error:", event);
            setAnswer((prev) =>
              prev ? { ...prev, isStreaming: false } : null
            );
            setIsStreaming(false);
            es.close();
            eventSourceRef.current = null;
          });
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        console.error("[useSearch] Search failed:", e);
        logger.error("Search failed", { error: e });
        setIsSearching(false);
        // Re-throw so error boundaries can catch it
        throw e;
      }
    },
    [addRecentQuery]
  );

  const clearSearch = useCallback(() => {
    abortRef.current?.abort();
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setQuery("");
    setResults([]);
    setAnswer(null);
    setIsSearching(false);
    setIsStreaming(false);
    setSelectedResultId(null);
    setSearchDuration(null);
  }, []);

  return {
    query,
    setQuery,
    results,
    answer,
    isSearching,
    isStreaming,
    recentQueries,
    selectedResultId,
    setSelectedResultId,
    searchDuration,
    search,
    clearSearch,
  };
}
