"use client";

import { Sparkles, BookOpen, Copy, ThumbsUp, ThumbsDown, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { AIAnswer, Citation } from "@/types";

interface AnswerPanelProps {
  answer: AIAnswer | null;
  isStreaming: boolean;
  onCitationClick: (citation: Citation) => void;
  onRetry?: () => void;
}

export function AnswerPanel({ answer, isStreaming, onCitationClick, onRetry }: AnswerPanelProps) {
  if (!answer) return null;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className={cn(
            "w-6 h-6 rounded-[var(--radius-md)] flex items-center justify-center",
            "bg-gradient-to-br from-[#d97756] to-[#b85636]",
            isStreaming && "animate-breathe"
          )}
        >
          <Sparkles className="h-3 w-3 text-white" />
        </div>
        <span className="text-sm font-semibold text-[var(--text-primary)]">
          CoPoly
        </span>
        {isStreaming && (
          <span className="text-[11px] text-[var(--accent-primary)] animate-pulse">
            Analyzing sources...
          </span>
        )}
      </div>

      {/* Answer content */}
      <div
        className={cn(
          "text-sm text-[var(--text-secondary)] leading-relaxed",
          "[&_b]:text-[var(--text-primary)] [&_b]:font-semibold",
          "[&_p]:mb-2 [&_p]:last:mb-0",
          "[&_ul]:pl-4 [&_ul]:mb-2 [&_ul]:space-y-1",
          "[&_li]:text-[var(--text-secondary)]",
          "[&_sup]:text-[var(--accent-primary)] [&_sup]:text-[10px] [&_sup]:font-bold [&_sup]:cursor-pointer [&_sup]:hover:underline",
          isStreaming && "after:content-['▊'] after:text-[var(--accent-primary)] after:animate-pulse after:ml-0.5"
        )}
        dangerouslySetInnerHTML={{ __html: answer.text }}
      />

      {/* Citations */}
      {!isStreaming && answer.citations.length > 0 && (
        <div className="mt-4 pt-3 border-t border-[var(--border-primary)]">
          <div className="flex items-center gap-1.5 mb-2">
            <BookOpen className="h-3 w-3 text-[var(--text-tertiary)]" />
            <span className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Sources
            </span>
          </div>
          <div className="space-y-1">
            {answer.citations.map((cite, i) => (
              <button
                key={i}
                onClick={() => onCitationClick(cite)}
                className={cn(
                  "w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-[var(--radius-sm)]",
                  "hover:bg-[var(--accent-glow)] transition-colors",
                  "group cursor-pointer"
                )}
              >
                <span className="w-5 h-5 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[10px] font-bold text-[var(--text-secondary)] shrink-0 group-hover:bg-[var(--accent-primary)] group-hover:text-white transition-colors">
                  {cite.sourceIndex + 1}
                </span>
                <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--accent-primary)] truncate transition-colors">
                  {cite.documentTitle}
                </span>
                <span className="text-[10px] text-[var(--text-tertiary)] shrink-0">
                  p. {cite.pageNumber}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {!isStreaming && (
        <div className="flex items-center gap-1 mt-4 animate-fade-in">
          <Button variant="ghost" size="sm" className="h-7 text-xs text-[var(--text-tertiary)] gap-1">
            <Copy className="h-3 w-3" />
            Copy
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-xs text-[var(--text-tertiary)] gap-1">
            <ThumbsUp className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-xs text-[var(--text-tertiary)] gap-1">
            <ThumbsDown className="h-3 w-3" />
          </Button>
          {onRetry && (
            <Button variant="ghost" size="sm" onClick={onRetry} className="h-7 text-xs text-[var(--text-tertiary)] gap-1 ml-auto">
              <RotateCcw className="h-3 w-3" />
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
