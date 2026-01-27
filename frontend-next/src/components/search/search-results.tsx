"use client";

import type { SearchResult } from "@/lib/types";
import { ResultCard } from "./result-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatSearchTime } from "@/lib/utils/format";

interface SearchResultsProps {
  results: SearchResult[];
  queryId: string | null;
  totalCount: number;
  searchTimeMs: number;
  loading: boolean;
  error: string | null;
  projectId: string;
}

export function SearchResults({
  results,
  queryId,
  totalCount,
  searchTimeMs,
  loading,
  error,
  projectId,
}: SearchResultsProps) {
  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-destructive">
        <p>{error}</p>
      </div>
    );
  }

  if (results.length === 0 && queryId) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        <p>No results found.</p>
      </div>
    );
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="text-xs text-muted-foreground">
        {totalCount} results in {formatSearchTime(searchTimeMs)}
      </div>
      {results.map((result) => (
        <ResultCard
          key={result.doc_id}
          result={result}
          queryId={queryId || ""}
          projectId={projectId}
        />
      ))}
    </div>
  );
}
