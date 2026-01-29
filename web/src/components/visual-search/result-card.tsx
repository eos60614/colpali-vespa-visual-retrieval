"use client";

import Image from "next/image";
import { Check, FileText, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { VisualSearchResult } from "@/types";

interface VisualSearchResultCardProps {
  result: VisualSearchResult;
  index: number;
  isSelected: boolean;
  onToggleSelect: () => void;
  onOpenDetail?: () => void;
  maxRelevance: number;
}

export function VisualSearchResultCard({
  result,
  index,
  isSelected,
  onToggleSelect,
  onOpenDetail,
  maxRelevance,
}: VisualSearchResultCardProps) {
  const normalizedScore = maxRelevance > 0 ? (result.relevance / maxRelevance) * 100 : 0;

  return (
    <div
      className={cn(
        "group relative rounded-[var(--radius-lg)] border overflow-hidden",
        "transition-all duration-[var(--transition-fast)] cursor-pointer",
        "hover:shadow-[var(--shadow-md)]",
        isSelected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/30 bg-[var(--accent-glow)]"
          : "border-[var(--border-primary)] bg-[var(--bg-elevated)] hover:border-[var(--border-accent)]"
      )}
      onClick={onToggleSelect}
    >
      {/* Selection checkbox overlay */}
      <div
        className={cn(
          "absolute top-2 left-2 z-10 w-6 h-6 rounded-full flex items-center justify-center",
          "transition-all duration-[var(--transition-fast)]",
          isSelected
            ? "bg-[var(--accent-primary)] text-white"
            : "bg-[var(--bg-elevated)]/90 border border-[var(--border-primary)] text-transparent group-hover:text-[var(--text-tertiary)]"
        )}
      >
        {isSelected ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <span className="text-xs font-medium">{index + 1}</span>
        )}
      </div>

      {/* Relevance badge */}
      <div className="absolute top-2 right-2 z-10">
        <Badge
          variant={normalizedScore > 80 ? "default" : "muted"}
          className={cn(
            "text-[10px] font-mono",
            normalizedScore > 80 && "bg-[var(--status-success)]/20 text-[var(--status-success)] border-[var(--status-success)]/30"
          )}
        >
          {normalizedScore.toFixed(0)}%
        </Badge>
      </div>

      {/* Image thumbnail */}
      <div className="aspect-[3/4] relative bg-[var(--bg-tertiary)]">
        {result.blurImage ? (
          <Image
            src={result.blurImage}
            alt={`${result.title} - Page ${result.pageNumber}`}
            fill
            className={cn(
              "object-contain transition-opacity",
              isSelected ? "opacity-100" : "opacity-90 group-hover:opacity-100"
            )}
            unoptimized
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <FileText className="h-12 w-12 text-[var(--text-tertiary)]" />
          </div>
        )}
      </div>

      {/* Info footer */}
      <div className="p-3 space-y-1.5 border-t border-[var(--border-primary)]">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-xs font-medium text-[var(--text-primary)] line-clamp-1" title={result.title}>
            {result.title}
          </h3>
          {onOpenDetail && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onOpenDetail();
              }}
              className="shrink-0 p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
        </div>
        <p className="text-[10px] text-[var(--text-tertiary)]">
          Page {result.pageNumber + 1}
        </p>
        {result.snippet && (
          <p className="text-[10px] text-[var(--text-secondary)] line-clamp-2">
            {result.snippet}
          </p>
        )}
      </div>
    </div>
  );
}
