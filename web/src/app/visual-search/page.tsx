"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Search, ArrowRight, Sparkles, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { useVisualSearch } from "@/hooks/use-visual-search";
import { VisualSearchResultGrid } from "@/components/visual-search/result-grid";
import { SelectionFooter } from "@/components/visual-search/selection-footer";
import { AnswerPanel } from "@/components/visual-search/answer-panel";
import { DocumentViewer } from "@/components/document/document-viewer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { VisualSearchResult, SearchResult } from "@/types";

const SAMPLE_QUERIES = [
  "What percentage of funds were in real estate investments in 2023?",
  "Gender balance at level 4 or above in NY office?",
  "Number of graduate applications trend 2021-2023",
  "Total amount of fixed salaries paid in 2023?",
  "Proportion of female new hires 2021-2023?",
];

export default function VisualSearchPage() {
  const {
    query,
    setQuery,
    results,
    isSearching,
    searchError,
    durationMs,
    totalCount,
    selectedIds,
    toggleSelection,
    selectTopN,
    clearSelection,
    search,
    synthesis,
    synthesize,
    cancelSynthesis,
  } = useVisualSearch();

  const [showAnswerPanel, setShowAnswerPanel] = useState(false);
  const [detailResult, setDetailResult] = useState<VisualSearchResult | null>(null);

  const handleSearch = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      search();
    },
    [search]
  );

  const handleSampleQuery = useCallback(
    (sampleQuery: string) => {
      setQuery(sampleQuery);
      search(sampleQuery);
    },
    [setQuery, search]
  );

  const handleSynthesize = useCallback(() => {
    setShowAnswerPanel(true);
    synthesize();
  }, [synthesize]);

  const handleCloseAnswer = useCallback(() => {
    setShowAnswerPanel(false);
    cancelSynthesis();
  }, [cancelSynthesis]);

  const handleRefine = useCallback(() => {
    setShowAnswerPanel(false);
  }, []);

  const handleOpenDetail = useCallback((result: VisualSearchResult) => {
    setDetailResult(result);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setDetailResult(null);
  }, []);

  // Convert VisualSearchResult to SearchResult for DocumentViewer
  const detailSearchResult: SearchResult | null = detailResult
    ? {
        id: detailResult.id,
        documentId: detailResult.id,
        title: detailResult.title,
        pageNumber: detailResult.pageNumber,
        snippet: detailResult.snippet,
        relevanceScore: detailResult.relevance,
        category: "other",
        blurImage: detailResult.blurImage,
        text: detailResult.text,
      }
    : null;

  const selectedResults = results.filter((r) => selectedIds.has(r.id));
  const hasSearched = results.length > 0 || searchError !== null;

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* Header */}
      <header className="border-b border-[var(--border-primary)] bg-[var(--bg-secondary)]">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#d97756] to-[#b85636] flex items-center justify-center">
              <Layers className="h-4 w-4 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-[var(--text-primary)]">Visual Search</h1>
              <p className="text-xs text-[var(--text-tertiary)]">Search documents visually with ColPali</p>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <Link
              href="/"
              className={cn(
                "h-8 px-3 text-xs inline-flex items-center justify-center font-medium rounded-[var(--radius-md)]",
                "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]",
                "transition-all duration-[var(--transition-fast)]"
              )}
            >
              Search
            </Link>
            <Link
              href="/upload"
              className={cn(
                "h-8 px-3 text-xs inline-flex items-center justify-center font-medium rounded-[var(--radius-md)]",
                "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]",
                "transition-all duration-[var(--transition-fast)]"
              )}
            >
              Upload
            </Link>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className={cn("max-w-7xl mx-auto px-4 py-8", selectedIds.size > 0 && "pb-24")}>
        {/* Search form */}
        <form onSubmit={handleSearch} className="mb-8">
          <div className="relative max-w-2xl mx-auto">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-[var(--text-tertiary)]" />
            <Input
              type="text"
              placeholder="Enter your search query..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-12 pr-32 h-14 text-base rounded-full border-2 focus:border-[var(--accent-primary)]"
            />
            <Button
              type="submit"
              variant="primary"
              disabled={isSearching || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full px-6"
            >
              {isSearching ? "Searching..." : "Search"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </form>

        {/* Sample queries (shown when no search has been done) */}
        {!hasSearched && (
          <div className="max-w-2xl mx-auto text-center mb-12">
            <p className="text-sm text-[var(--text-tertiary)] mb-4">Try a sample query:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SAMPLE_QUERIES.map((sampleQuery) => (
                <button
                  key={sampleQuery}
                  onClick={() => handleSampleQuery(sampleQuery)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs",
                    "bg-[var(--bg-secondary)] border border-[var(--border-primary)]",
                    "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                    "hover:border-[var(--border-accent)] transition-all cursor-pointer"
                  )}
                >
                  {sampleQuery}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error message */}
        {searchError && (
          <div className="max-w-2xl mx-auto mb-8 p-4 rounded-lg bg-[var(--status-error)]/10 border border-[var(--status-error)]/20 text-center">
            <p className="text-sm text-[var(--status-error)]">{searchError}</p>
          </div>
        )}

        {/* Results grid */}
        {(results.length > 0 || isSearching) && (
          <VisualSearchResultGrid
            results={results}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelection}
            onSelectTopN={selectTopN}
            onClearSelection={clearSelection}
            onOpenDetail={handleOpenDetail}
            isLoading={isSearching}
            durationMs={durationMs}
            totalCount={totalCount}
          />
        )}

        {/* Instructions when results are shown but nothing selected */}
        {results.length > 0 && selectedIds.size === 0 && !isSearching && (
          <div className="mt-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--accent-glow)] text-[var(--accent-primary)] text-sm">
              <Sparkles className="h-4 w-4" />
              Select pages to get an AI-generated answer
            </div>
          </div>
        )}
      </main>

      {/* Selection footer */}
      <SelectionFooter
        selectedCount={selectedIds.size}
        onClear={clearSelection}
        onSynthesize={handleSynthesize}
        isSynthesizing={synthesis.isStreaming}
      />

      {/* Answer panel modal */}
      {showAnswerPanel && (
        <AnswerPanel
          synthesis={synthesis}
          selectedResults={selectedResults}
          onClose={handleCloseAnswer}
          onRefine={handleRefine}
        />
      )}

      {/* Document detail viewer */}
      {detailSearchResult && (
        <DocumentViewer result={detailSearchResult} onClose={handleCloseDetail} />
      )}
    </div>
  );
}
