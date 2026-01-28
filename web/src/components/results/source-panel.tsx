"use client";

import { FileSearch, Layers, Clock, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { ResultCard } from "./result-card";
import { SkeletonResultCard } from "@/components/ui/skeleton";
import type { SearchResult } from "@/types";

interface SourcePanelProps {
  results: SearchResult[];
  isSearching: boolean;
  selectedResultId: string | null;
  onSelectResult: (id: string) => void;
  onPreviewResult: (id: string) => void;
  searchDuration: number | null;
  query: string;
}

export function SourcePanel({
  results,
  isSearching,
  selectedResultId,
  onSelectResult,
  onPreviewResult,
  searchDuration,
  query,
}: SourcePanelProps) {
  if (!query && !isSearching && results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6 py-12">
        <div className="w-12 h-12 rounded-[var(--radius-xl)] bg-[var(--bg-tertiary)] flex items-center justify-center mb-4 animate-float">
          <FileSearch className="h-6 w-6 text-[var(--text-tertiary)]" />
        </div>
        <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-1">
          Ready to search
        </h3>
        <p className="text-xs text-[var(--text-tertiary)] max-w-[240px]">
          Ask a question above and CoPoly will find the most relevant document pages.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)] shrink-0">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-[var(--accent-primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">
            Sources
          </span>
          {results.length > 0 && (
            <span className="text-xs text-[var(--text-tertiary)] bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded-[var(--radius-full)]">
              {results.length}
            </span>
          )}
        </div>
        {searchDuration !== null && (
          <div className="flex items-center gap-1 text-[11px] text-[var(--text-tertiary)]">
            <Zap className="h-3 w-3 text-[var(--success)]" />
            {searchDuration}ms
          </div>
        )}
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {isSearching ? (
          <>
            <div className="flex items-center gap-2 px-1 mb-2 animate-fade-in">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
              <span className="text-xs text-[var(--text-tertiary)]">
                Searching documents...
              </span>
            </div>
            {[0, 1, 2].map((i) => (
              <SkeletonResultCard key={i} />
            ))}
          </>
        ) : (
          results.map((result, index) => (
            <ResultCard
              key={result.id}
              result={result}
              index={index}
              isSelected={selectedResultId === result.id}
              onSelect={() => onSelectResult(result.id)}
              onPreview={() => onPreviewResult(result.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
