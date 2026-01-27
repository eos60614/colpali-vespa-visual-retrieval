"use client";

import { useParams } from "next/navigation";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { DocumentViewer } from "@/components/documents/document-viewer";

export default function DocumentViewerPage() {
  const params = useParams();
  const projectId = Number(params.projectId);
  const documentId = params.documentId as string;

  return (
    <div className="flex flex-col h-full">
      <Breadcrumbs
        items={[
          { label: "Documents", href: `/projects/${projectId}/documents` },
          { label: documentId },
        ]}
      />
      <div className="flex-1 overflow-y-auto">
        <DocumentViewer documentId={documentId} title={documentId} />
      </div>
    </div>
  );
}
