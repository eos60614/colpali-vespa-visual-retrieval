"use client";

import { X, Sparkles, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface SelectionFooterProps {
  selectedCount: number;
  onClear: () => void;
  onSynthesize: () => void;
  isSynthesizing: boolean;
}

export function SelectionFooter({
  selectedCount,
  onClear,
  onSynthesize,
  isSynthesizing,
}: SelectionFooterProps) {
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-40",
        "bg-[var(--bg-elevated)] border-t border-[var(--border-primary)]",
        "shadow-[var(--shadow-lg)]",
        "animate-slide-in-bottom"
      )}
    >
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {selectedCount} {selectedCount === 1 ? "page" : "pages"} selected
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClear}
            className="h-7 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
          >
            <X className="h-3.5 w-3.5 mr-1" />
            Clear selection
          </Button>
        </div>
        <Button
          variant="primary"
          size="lg"
          onClick={onSynthesize}
          disabled={isSynthesizing}
          className="gap-2"
        >
          {isSynthesizing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating answer...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Get Answer
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
