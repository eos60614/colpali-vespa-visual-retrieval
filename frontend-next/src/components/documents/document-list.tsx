"use client";

import type { DocumentSummary } from "@/lib/types";
import { DocumentCard } from "./document-card";
import { Skeleton } from "@/components/ui/skeleton";

interface DocumentListProps {
  documents: DocumentSummary[];
  loading: boolean;
  error: string | null;
  projectId: string;
}

export function DocumentList({ documents, loading, error, projectId }: DocumentListProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Skeleton key={i} className="h-40 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (error) {
    return <div className="p-6 text-center text-destructive">{error}</div>;
  }

  if (documents.length === 0) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        No documents found. Upload some PDFs to get started.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {documents.map((doc) => (
        <DocumentCard key={doc.doc_id} document={doc} projectId={projectId} />
      ))}
    </div>
  );
}
