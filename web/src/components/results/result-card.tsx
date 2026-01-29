"use client";

import Image from "next/image";
import { FileText, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, CATEGORY_COLORS, type SearchResult } from "@/types";

interface ResultCardProps {
  result: SearchResult;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
  onPreview: () => void;
}

export function ResultCard({ result, index, isSelected, onSelect, onPreview }: ResultCardProps) {
  const scorePercent = Math.round(result.relevanceScore * 100);

  return (
    <div
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      className={cn(
        "group relative rounded-[var(--radius-lg)] border p-4",
        "transition-all duration-[var(--transition-base)] cursor-pointer",
        "animate-fade-in-up",
        isSelected
          ? "border-[var(--border-accent)] bg-[var(--accent-glow)] shadow-[var(--shadow-md)] glow-accent"
          : "border-[var(--border-primary)] bg-[var(--bg-elevated)] hover:border-[var(--border-secondary)] hover:shadow-[var(--shadow-sm)]"
      )}
      style={{ animationDelay: `${index * 80}ms` }}
    >
      {/* Source index badge */}
      <div className="absolute -top-2 -left-2 z-10">
        <div
          className={cn(
            "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
            "shadow-[var(--shadow-sm)]",
            isSelected
              ? "bg-[var(--accent-primary)] text-white"
              : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
          )}
        >
          {index + 1}
        </div>
      </div>

      {/* Content row with optional thumbnail */}
      <div className="flex gap-3">
        {/* Blur thumbnail */}
        {result.blurImage && (
          <div className="shrink-0 w-20 h-[106px] rounded-[var(--radius-md)] overflow-hidden bg-[var(--bg-tertiary)] border border-[var(--border-primary)] relative">
            <Image
              src={result.blurImage}
              alt={`Page ${result.pageNumber}`}
              fill
              className="object-cover"
              unoptimized
            />
          </div>
        )}

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Badge
                  variant="default"
                  className="shrink-0"
                  dot
                >
                  <span style={{ color: CATEGORY_COLORS[result.category] }}>
                    {CATEGORY_LABELS[result.category]}
                  </span>
                </Badge>
                <span className="text-[11px] text-[var(--text-tertiary)]">
                  p. {result.pageNumber}
                </span>
              </div>
              <h3 className="text-sm font-medium text-[var(--text-primary)] line-clamp-1 group-hover:text-[var(--accent-primary)] transition-colors">
                {result.title}
              </h3>
            </div>

            {/* Relevance score */}
            <div className="flex items-center gap-1 shrink-0">
              <div className="relative w-8 h-8">
                <svg className="w-8 h-8 -rotate-90" viewBox="0 0 36 36">
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="var(--bg-tertiary)"
                    strokeWidth="3"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="var(--accent-primary)"
                    strokeWidth="3"
                    strokeDasharray={`${scorePercent}, 100`}
                    strokeLinecap="round"
                    className="transition-all duration-[var(--transition-slow)]"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-[var(--text-secondary)]">
                  {scorePercent}
                </span>
              </div>
            </div>
          </div>

          {/* Snippet */}
          <p className="text-xs text-[var(--text-secondary)] line-clamp-3 leading-relaxed mb-3">
            {result.snippet}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <FileText className="h-3 w-3 text-[var(--text-tertiary)]" />
          <span className="text-[11px] text-[var(--text-tertiary)] truncate max-w-[200px]">
            {result.documentId}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPreview();
          }}
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-[var(--radius-sm)] text-[11px]",
            "text-[var(--text-tertiary)] hover:text-[var(--accent-primary)]",
            "hover:bg-[var(--accent-glow)]",
            "transition-all duration-[var(--transition-fast)]",
            "opacity-0 group-hover:opacity-100",
            "cursor-pointer"
          )}
        >
          <Eye className="h-3 w-3" />
          Preview
        </button>
      </div>
    </div>
  );
}
