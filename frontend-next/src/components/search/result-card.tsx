"use client";

import { useState } from "react";
import Link from "next/link";
import type { SearchResult } from "@/lib/types";
import { fullImageUrl, blurImageUrl } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { formatScore } from "@/lib/utils/format";

interface ResultCardProps {
  result: SearchResult;
  queryId: string;
  projectId: string;
}

export function ResultCard({ result, queryId, projectId }: ResultCardProps) {
  const [imgSrc, setImgSrc] = useState(blurImageUrl(result.doc_id));
  const [loaded, setLoaded] = useState(false);

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="relative aspect-[4/3] bg-muted">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgSrc}
          alt={result.title}
          className={`w-full h-full object-contain transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-70"}`}
          onLoad={() => {
            if (!loaded) {
              setLoaded(true);
              // Swap to full image after blur loads
              const fullUrl = fullImageUrl(result.doc_id);
              const img = new Image();
              img.onload = () => setImgSrc(fullUrl);
              img.src = fullUrl;
            }
          }}
        />
        <div className="absolute top-2 right-2 flex gap-1">
          {result.category && <Badge variant="secondary">{result.category}</Badge>}
          <Badge variant="outline">{formatScore(result.relevance_score)}</Badge>
        </div>
        {result.is_region && (
          <Badge className="absolute top-2 left-2" variant="secondary">Region</Badge>
        )}
      </div>
      <div className="p-3">
        <div className="flex items-center justify-between mb-1">
          <Link
            href={`/projects/${projectId}/documents/${result.doc_id}`}
            className="font-medium text-sm hover:underline truncate"
          >
            {result.title}
          </Link>
          <span className="text-xs text-muted-foreground shrink-0 ml-2">
            Page {result.page_number}
          </span>
        </div>
        {result.snippet && (
          <p className="text-xs text-muted-foreground line-clamp-2">{result.snippet}</p>
        )}
        {result.sim_map_tokens.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {result.sim_map_tokens.slice(0, 5).map((token) => (
              <span key={token} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {token}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
