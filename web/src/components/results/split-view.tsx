"use client";

import { useReducer, useEffect } from "react";
import Image from "next/image";
import { SourcePanel } from "./source-panel";
import { AnswerPanel } from "./answer-panel";
import { getFullImage } from "@/lib/api-client";
import type { SearchResult, AIAnswer, Citation } from "@/types";

interface SplitViewProps {
  results: SearchResult[];
  answer: AIAnswer | null;
  isSearching: boolean;
  isStreaming: boolean;
  selectedResultId: string | null;
  onSelectResult: (id: string) => void;
  onPreviewResult: (id: string) => void;
  onCitationClick: (citation: Citation) => void;
  searchDuration: number | null;
  query: string;
  onRetry?: () => void;
}

export function SplitView({
  results,
  answer,
  isSearching,
  isStreaming,
  selectedResultId,
  onSelectResult,
  onPreviewResult,
  onCitationClick,
  searchDuration,
  query,
  onRetry,
}: SplitViewProps) {
  const hasResults = results.length > 0 || isSearching;

  if (!hasResults && !answer) return null;

  return (
    <div className="flex-1 flex min-h-0 animate-fade-in-up">
      {/* Left: Sources */}
      <div className="w-[420px] shrink-0 border-r border-[var(--border-primary)] bg-[var(--bg-primary)]">
        <SourcePanel
          results={results}
          isSearching={isSearching}
          selectedResultId={selectedResultId}
          onSelectResult={onSelectResult}
          onPreviewResult={onPreviewResult}
          searchDuration={searchDuration}
          query={query}
        />
      </div>

      {/* Right: Answer */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-6">
          {(answer || isStreaming) ? (
            <AnswerPanel
              answer={answer}
              isStreaming={isStreaming}
              onCitationClick={onCitationClick}
              onRetry={onRetry}
            />
          ) : isSearching ? (
            <div className="flex flex-col items-center justify-center py-12 animate-fade-in">
              <div className="w-10 h-10 rounded-[var(--radius-lg)] bg-gradient-to-br from-[#d97756] to-[#b85636] flex items-center justify-center mb-4 animate-breathe">
                <svg className="h-5 w-5 text-white animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <p className="text-sm text-[var(--text-tertiary)]">
                Retrieving relevant pages...
              </p>
            </div>
          ) : null}

          {/* Selected source preview */}
          {!isSearching && results.length > 0 && selectedResultId && (
            <SelectedSourcePreview
              result={results.find((r) => r.id === selectedResultId)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function SelectedSourcePreview({ result }: { result?: SearchResult }) {
  type ImageState = { image: string | null; loading: boolean };
  type ImageAction = { type: "loading" } | { type: "loaded"; image: string | null };
  const [imgState, dispatchImg] = useReducer(
    (_: ImageState, action: ImageAction): ImageState => {
      if (action.type === "loading") return { image: null, loading: true };
      return { image: action.image, loading: false };
    },
    { image: null, loading: false }
  );
  const docId = result?.documentId;

  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    dispatchImg({ type: "loading" });
    getFullImage(docId)
      .then((img) => { if (!cancelled) dispatchImg({ type: "loaded", image: img }); })
      .catch((e) => {
        console.error("[SplitView] Failed to load full image:", e);
        if (!cancelled) dispatchImg({ type: "loaded", image: null });
      });
    return () => { cancelled = true; };
  }, [docId]);

  const fullImage = imgState.image;
  const loading = imgState.loading;

  if (!result) return null;

  return (
    <div className="mt-6 pt-6 border-t border-[var(--border-primary)] animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
          Selected Source
        </span>
      </div>

      {/* Page preview */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-primary)] overflow-hidden bg-[var(--bg-secondary)]">
        <div className="aspect-[8.5/11] bg-[var(--bg-tertiary)] flex items-center justify-center relative">
          {loading ? (
            <div className="absolute inset-4 bg-[var(--bg-elevated)] rounded-[var(--radius-md)] shadow-[var(--shadow-md)] p-6 flex flex-col gap-3">
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-5/6" />
              <div className="mt-2 skeleton h-3 w-full" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-2/3" />
              <div className="mt-auto flex justify-between">
                <div className="skeleton h-2 w-20" />
                <div className="skeleton h-2 w-12" />
              </div>
            </div>
          ) : fullImage ? (
            <Image
              src={fullImage}
              alt={`${result.title} — Page ${result.pageNumber}`}
              fill
              className="object-contain"
              unoptimized
            />
          ) : result.blurImage ? (
            <Image
              src={result.blurImage}
              alt={`${result.title} — Page ${result.pageNumber} (preview)`}
              fill
              className="object-contain opacity-60"
              unoptimized
            />
          ) : (
            <p className="text-xs text-[var(--text-tertiary)]">Image unavailable</p>
          )}
        </div>

        {/* Source info bar */}
        <div className="px-4 py-3 border-t border-[var(--border-primary)] bg-[var(--bg-elevated)]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[var(--text-primary)]">
                {result.title}
              </p>
              <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5">
                Page {result.pageNumber} &middot; {result.documentId}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Extracted text */}
      {result.text && (
        <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-3">
          <span className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider block mb-2">
            Extracted Text
          </span>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed font-mono whitespace-pre-wrap">
            {result.text}
          </p>
        </div>
      )}
    </div>
  );
}
