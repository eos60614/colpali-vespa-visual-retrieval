"use client";

import Link from "next/link";
import type { DocumentSummary } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { blurImageUrl } from "@/lib/api-client";

interface DocumentCardProps {
  document: DocumentSummary;
  projectId: string;
}

export function DocumentCard({ document, projectId }: DocumentCardProps) {
  return (
    <Link
      href={`/projects/${projectId}/documents/${document.doc_id}`}
      className="block rounded-lg border bg-card overflow-hidden hover:shadow-md transition-shadow"
    >
      <div className="aspect-[3/2] bg-muted relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={blurImageUrl(document.doc_id)}
          alt={document.title}
          className="w-full h-full object-contain"
        />
        {document.category && (
          <Badge className="absolute top-2 right-2" variant="secondary">
            {document.category}
          </Badge>
        )}
      </div>
      <div className="p-3">
        <h3 className="font-medium text-sm truncate">{document.title}</h3>
        <p className="text-xs text-muted-foreground mt-0.5">Page {document.page_number}</p>
        {document.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {document.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
