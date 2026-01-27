"use client";

import { cn } from "@/lib/utils/cn";
import { CATEGORIES } from "@/lib/types";

interface ScopeControlsProps {
  categories: string[];
  onCategoriesChange: (cats: string[]) => void;
}

export function ScopeControls({ categories, onCategoriesChange }: ScopeControlsProps) {
  const toggle = (cat: string) => {
    if (categories.includes(cat)) {
      onCategoriesChange(categories.filter((c) => c !== cat));
    } else {
      onCategoriesChange([...categories, cat]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map((cat) => (
        <button
          key={cat}
          onClick={() => toggle(cat)}
          className={cn(
            "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
            categories.includes(cat)
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-background text-muted-foreground border-border hover:bg-accent"
          )}
        >
          {cat}
        </button>
      ))}
      {categories.length > 0 && (
        <button
          onClick={() => onCategoriesChange([])}
          className="px-3 py-1 rounded-full text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Clear
        </button>
      )}
    </div>
  );
}
