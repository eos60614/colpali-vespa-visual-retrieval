"use client";

import { useState } from "react";
import Image from "next/image";
import { Loader2, RotateCcw, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useSimilarityMaps } from "@/hooks/use-similarity-maps";
import type { TokenInfo } from "@/types";

interface SimilarityMapViewerProps {
  queryId: string | null;
  resultIndex: number;
  tokenMap: TokenInfo[];
  originalImage?: string;
  className?: string;
}

export function SimilarityMapViewer({
  queryId,
  resultIndex,
  tokenMap,
  originalImage,
  className,
}: SimilarityMapViewerProps) {
  const [showOverlay, setShowOverlay] = useState(true);
  const {
    activeTokenIdx,
    setActiveTokenIdx,
    getSimMap,
  } = useSimilarityMaps({
    queryId,
    resultIndex,
    tokenMap,
    enabled: !!queryId,
  });

  const activeSimMap = activeTokenIdx !== null ? getSimMap(activeTokenIdx) : null;
  const activeToken = activeTokenIdx !== null
    ? tokenMap.find(t => t.tokenIdx === activeTokenIdx)?.token
    : null;

  const handleTokenClick = (tokenIdx: number) => {
    if (activeTokenIdx === tokenIdx) {
      setActiveTokenIdx(null);
    } else {
      setActiveTokenIdx(tokenIdx);
    }
  };

  const handleReset = () => {
    setActiveTokenIdx(null);
  };

  if (!queryId || tokenMap.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center py-8 text-center", className)}>
        <p className="text-sm text-[var(--text-tertiary)]">
          No similarity maps available.
        </p>
        <p className="text-xs text-[var(--text-tertiary)] mt-1">
          Perform a search to generate token-level similarity maps.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Token buttons */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            Query Tokens
          </label>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowOverlay(!showOverlay)}
              className="h-6 text-[10px] gap-1"
            >
              {showOverlay ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              {showOverlay ? "Hide overlay" : "Show overlay"}
            </Button>
            {activeTokenIdx !== null && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                className="h-6 text-[10px] gap-1"
              >
                <RotateCcw className="h-3 w-3" />
                Reset
              </Button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {tokenMap.map(({ token, tokenIdx }) => {
            const simMap = getSimMap(tokenIdx);
            const isActive = activeTokenIdx === tokenIdx;
            const isReady = simMap?.ready ?? false;
            const isLoadingToken = simMap?.loading ?? false;

            return (
              <button
                key={tokenIdx}
                onClick={() => handleTokenClick(tokenIdx)}
                disabled={isLoadingToken && !isReady}
                className={cn(
                  "px-2 py-1 text-xs font-mono rounded-sm transition-all cursor-pointer",
                  "border",
                  isActive
                    ? "bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]"
                    : isReady
                    ? "bg-[var(--bg-secondary)] text-[var(--text-secondary)] border-[var(--border-primary)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                    : "bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] border-[var(--border-primary)] cursor-wait",
                  isLoadingToken && !isReady && "animate-pulse"
                )}
              >
                {isLoadingToken && !isReady ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  token
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Image display */}
      <div className="relative aspect-[3/4] bg-[var(--bg-tertiary)] rounded-lg overflow-hidden">
        {/* Original image */}
        {originalImage && (
          <Image
            src={originalImage}
            alt="Document page"
            fill
            className="object-contain"
            unoptimized
          />
        )}

        {/* Similarity map overlay */}
        {showOverlay && activeSimMap?.ready && activeSimMap.image && (
          <div className="absolute inset-0 transition-opacity duration-200">
            <Image
              src={activeSimMap.image}
              alt={`Similarity map for token: ${activeToken}`}
              fill
              className="object-contain"
              unoptimized
            />
          </div>
        )}

        {/* Loading indicator */}
        {activeTokenIdx !== null && !activeSimMap?.ready && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20">
            <div className="flex flex-col items-center gap-2 bg-[var(--bg-elevated)] rounded-lg px-4 py-3 shadow-lg">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--accent-primary)]" />
              <span className="text-xs text-[var(--text-secondary)]">Loading similarity map...</span>
            </div>
          </div>
        )}

        {/* Active token indicator */}
        {activeToken && (
          <div className="absolute bottom-2 left-2">
            <Badge variant="default" className="bg-[var(--bg-elevated)]/90 text-[var(--text-primary)]">
              Token: &quot;{activeToken}&quot;
            </Badge>
          </div>
        )}
      </div>

      {/* Help text */}
      <p className="text-[10px] text-[var(--text-tertiary)] text-center">
        Click a token to see where it matches in the document. Heatmap shows relevance intensity.
      </p>
    </div>
  );
}
