"use client";

import { useEffect, useState, useCallback } from "react";
import { listDocuments } from "@/lib/api-client";
import type { DocumentSummary, DocsQuery } from "@/lib/types";

export function useDocuments(projectId: string, initialQuery: DocsQuery = {}) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<DocsQuery>(initialQuery);

  const fetch = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listDocuments(projectId, query);
      setDocuments(data.documents);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [projectId, query]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const updateQuery = useCallback((updates: Partial<DocsQuery>) => {
    setQuery((prev) => ({ ...prev, ...updates }));
  }, []);

  return { documents, total, loading, error, updateQuery, refresh: fetch };
}
