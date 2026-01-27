"use client";

import { useState, useCallback } from "react";
import { search as apiSearch } from "@/lib/api-client";
import type { SearchRequest, SearchResponse } from "@/lib/types";

export function useSearch() {
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (params: SearchRequest) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiSearch(params);
      setResponse(data);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Search failed";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setResponse(null);
    setError(null);
  }, []);

  return {
    results: response?.results ?? [],
    queryId: response?.query_id ?? null,
    totalCount: response?.total_count ?? 0,
    searchTimeMs: response?.search_time_ms ?? 0,
    loading,
    error,
    search,
    clear,
  };
}
