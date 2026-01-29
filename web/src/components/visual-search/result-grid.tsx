"use client";

import { VisualSearchResultCard } from "./result-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";
import type { VisualSearchResult } from "@/types";

interface VisualSearchResultGridProps {
  results: VisualSearchResult[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onSelectTopN: (n: number) => void;
  onClearSelection: () => void;
  onOpenDetail?: (result: VisualSearchResult) => void;
  isLoading: boolean;
  durationMs: number | null;
  totalCount: number;
}

export function VisualSearchResultGrid({
  results,
  selectedIds,
  onToggleSelect,
  onSelectTopN,
  onClearSelection,
  onOpenDetail,
  isLoading,
  durationMs,
  totalCount,
}: VisualSearchResultGridProps) {
  const maxRelevance = results.length > 0 ? Math.max(...results.map((r) => r.relevance)) : 0;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="aspect-[3/4] rounded-lg" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-16 h-16 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center mb-4">
          <Search className="h-8 w-8 text-[var(--text-tertiary)]" />
        </div>
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">
          No results found
        </h3>
        <p className="text-sm text-[var(--text-secondary)] max-w-md">
          Try adjusting your search query or broadening your search terms.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with stats and quick select buttons */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">{totalCount.toLocaleString()}</span> results
            {durationMs !== null && (
              <span className="text-[var(--text-tertiary)]"> in {(durationMs / 1000).toFixed(2)}s</span>
            )}
          </span>
          {selectedIds.size > 0 && (
            <>
              <span className="text-[var(--text-tertiary)]">|</span>
              <span className="text-sm text-[var(--accent-primary)] font-medium">
                {selectedIds.size} selected
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-tertiary)] mr-1">Quick select:</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSelectTopN(3)}
            className="h-7 text-xs"
          >
            Top 3
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSelectTopN(5)}
            className="h-7 text-xs"
          >
            Top 5
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSelectTopN(10)}
            className="h-7 text-xs"
          >
            Top 10
          </Button>
          {selectedIds.size > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="h-7 text-xs text-[var(--status-error)]"
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Results grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {results.map((result, index) => (
          <VisualSearchResultCard
            key={result.id}
            result={result}
            index={index}
            isSelected={selectedIds.has(result.id)}
            onToggleSelect={() => onToggleSelect(result.id)}
            onOpenDetail={onOpenDetail ? () => onOpenDetail(result) : undefined}
            maxRelevance={maxRelevance}
          />
        ))}
      </div>
    </div>
  );
}
