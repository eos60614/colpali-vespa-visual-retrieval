"use client";

import {
  X,
  Filter,
  FileText,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  type DocumentCategory,
  type Project,
} from "@/types";

interface ScopeBarProps {
  project: Project | null;
  selectedCategories: DocumentCategory[];
  selectedDocumentIds: string[];
  onToggleCategory: (category: DocumentCategory) => void;
  onClearCategories: () => void;
  onRemoveDocument: (id: string) => void;
  onClearAll: () => void;
}

export function ScopeBar({
  project,
  selectedCategories,
  selectedDocumentIds,
  onToggleCategory,
  onClearCategories,
  onRemoveDocument,
  onClearAll,
}: ScopeBarProps) {
  if (!project) return null;

  const hasFilters = selectedCategories.length > 0 || selectedDocumentIds.length > 0;

  const availableCategories = project.categories
    .filter((c) => c.count > 0)
    .map((c) => c.category);

  return (
    <div className="border-b border-[var(--border-primary)] bg-[var(--bg-primary)]">
      {/* Category filters */}
      <div className="px-4 py-2.5 flex items-center gap-2 overflow-x-auto">
        <div className="flex items-center gap-1.5 text-[var(--text-tertiary)] shrink-0">
          <Filter className="h-3.5 w-3.5" />
          <span className="text-xs font-medium">Scope</span>
        </div>

        <div className="w-px h-5 bg-[var(--border-primary)] shrink-0" />

        {/* All docs button */}
        <button
          onClick={onClearCategories}
          className={cn(
            "px-2.5 py-1 rounded-[var(--radius-full)] text-xs font-medium",
            "transition-all duration-[var(--transition-fast)] whitespace-nowrap cursor-pointer",
            selectedCategories.length === 0
              ? "bg-[var(--accent-glow)] text-[var(--accent-primary)] ring-1 ring-[var(--border-accent)]"
              : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
          )}
        >
          <span className="flex items-center gap-1.5">
            <Layers className="h-3 w-3" />
            All Documents
          </span>
        </button>

        {/* Category chips */}
        {availableCategories.map((cat) => {
          const isSelected = selectedCategories.includes(cat);
          const catInfo = project.categories.find((c) => c.category === cat);
          return (
            <button
              key={cat}
              onClick={() => onToggleCategory(cat)}
              className={cn(
                "px-2.5 py-1 rounded-[var(--radius-full)] text-xs font-medium",
                "transition-all duration-[var(--transition-fast)] whitespace-nowrap cursor-pointer",
                "border",
                isSelected
                  ? "border-[var(--border-accent)] shadow-[var(--shadow-sm)]"
                  : "border-transparent hover:bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              )}
              style={
                isSelected
                  ? {
                      backgroundColor: `${CATEGORY_COLORS[cat]}15`,
                      color: CATEGORY_COLORS[cat],
                    }
                  : undefined
              }
            >
              {CATEGORY_LABELS[cat]}
              {catInfo && (
                <span className="ml-1 opacity-60">{catInfo.count}</span>
              )}
            </button>
          );
        })}

        {/* Clear all */}
        {hasFilters && (
          <>
            <div className="w-px h-5 bg-[var(--border-primary)] shrink-0" />
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearAll}
              className="h-7 text-xs text-[var(--text-tertiary)] hover:text-[var(--error)]"
            >
              <X className="h-3 w-3 mr-1" />
              Clear
            </Button>
          </>
        )}
      </div>

      {/* Selected documents (if any) */}
      {selectedDocumentIds.length > 0 && (
        <div className="px-4 pb-2.5 flex items-center gap-2 flex-wrap">
          <FileText className="h-3.5 w-3.5 text-[var(--text-tertiary)] shrink-0" />
          <span className="text-xs text-[var(--text-tertiary)] shrink-0">Scoped to:</span>
          {selectedDocumentIds.map((id) => (
            <Badge key={id} variant="accent" className="gap-1">
              {id}
              <button
                onClick={() => onRemoveDocument(id)}
                className="hover:text-[var(--error)] transition-colors cursor-pointer"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
