"use client";

import { cn } from "@/lib/utils/cn";

const RANKINGS = [
  { value: "hybrid", label: "Hybrid" },
  { value: "colpali", label: "ColPali" },
  { value: "bm25", label: "BM25" },
] as const;

interface RankingSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export function RankingSelector({ value, onChange }: RankingSelectorProps) {
  return (
    <div className="flex rounded-md border">
      {RANKINGS.map((r) => (
        <button
          key={r.value}
          type="button"
          onClick={() => onChange(r.value)}
          className={cn(
            "px-3 py-2 text-sm transition-colors border-r last:border-r-0",
            value === r.value
              ? "bg-primary text-primary-foreground"
              : "hover:bg-accent text-muted-foreground"
          )}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
