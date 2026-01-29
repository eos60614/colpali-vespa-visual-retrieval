"use client";

import { useRef, useEffect } from "react";
import Image from "next/image";
import { X, Loader2, AlertCircle, RotateCcw, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { VisualSearchResult, SynthesisState } from "@/types";

interface AnswerPanelProps {
  synthesis: SynthesisState;
  selectedResults: VisualSearchResult[];
  onClose: () => void;
  onRefine: () => void;
}

export function AnswerPanel({
  synthesis,
  selectedResults,
  onClose,
  onRefine,
}: AnswerPanelProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom as streaming content arrives
  useEffect(() => {
    if (contentRef.current && synthesis.isStreaming) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [synthesis.text, synthesis.isStreaming]);

  if (!synthesis.text && !synthesis.isStreaming && !synthesis.error) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 animate-fade-in">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-[var(--bg-overlay)] backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="absolute inset-4 md:inset-8 lg:left-1/4 lg:right-8 bg-[var(--bg-elevated)] rounded-[var(--radius-xl)] shadow-[var(--shadow-lg)] flex flex-col overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              AI Answer
            </h2>
            {synthesis.isStreaming && (
              <div className="flex items-center gap-1.5 text-[var(--accent-primary)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span className="text-xs">Generating...</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onRefine}
              className="h-7 text-xs gap-1.5"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Refine selection
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex min-h-0">
          {/* Answer text */}
          <div
            ref={contentRef}
            className="flex-1 overflow-y-auto p-6"
          >
            {synthesis.error ? (
              <div className="flex items-start gap-3 p-4 rounded-lg bg-[var(--status-error)]/10 border border-[var(--status-error)]/20">
                <AlertCircle className="h-5 w-5 text-[var(--status-error)] shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-[var(--status-error)]">Error</p>
                  <p className="text-sm text-[var(--text-secondary)] mt-1">{synthesis.error}</p>
                </div>
              </div>
            ) : (
              <div
                className="prose prose-sm max-w-none text-[var(--text-primary)]"
                dangerouslySetInnerHTML={{ __html: synthesis.text }}
              />
            )}
            {synthesis.isStreaming && (
              <span className="inline-block w-2 h-4 bg-[var(--accent-primary)] animate-pulse ml-1" />
            )}
          </div>

          {/* Source thumbnails sidebar */}
          <div className="w-64 border-l border-[var(--border-primary)] bg-[var(--bg-secondary)] overflow-y-auto shrink-0">
            <div className="p-3 border-b border-[var(--border-primary)]">
              <h3 className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                Sources ({selectedResults.length})
              </h3>
            </div>
            <div className="p-3 space-y-3">
              {selectedResults.map((result, index) => (
                <div
                  key={result.id}
                  className="rounded-lg border border-[var(--border-primary)] overflow-hidden bg-[var(--bg-elevated)]"
                >
                  <div className="aspect-[4/3] relative bg-[var(--bg-tertiary)]">
                    {result.blurImage ? (
                      <Image
                        src={result.blurImage}
                        alt={`Source ${index + 1}: ${result.title}`}
                        fill
                        className="object-contain"
                        unoptimized
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <FileText className="h-8 w-8 text-[var(--text-tertiary)]" />
                      </div>
                    )}
                    <div className="absolute top-1 left-1 bg-[var(--bg-elevated)]/90 rounded px-1.5 py-0.5">
                      <span className="text-[10px] font-medium">{index + 1}</span>
                    </div>
                  </div>
                  <div className="p-2">
                    <p className="text-[10px] font-medium text-[var(--text-primary)] line-clamp-1">
                      {result.title}
                    </p>
                    <p className="text-[9px] text-[var(--text-tertiary)]">
                      Page {result.pageNumber + 1}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
