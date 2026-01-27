"use client";

import { useParams } from "next/navigation";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { UploadForm } from "@/components/upload/upload-form";

export default function UploadPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <div className="flex flex-col h-full">
      <Breadcrumbs items={[{ label: "Upload" }]} />
      <div className="flex-1 overflow-y-auto p-6">
        <h2 className="text-lg font-medium mb-4">Upload Document</h2>
        <UploadForm projectId={projectId} />
      </div>
    </div>
  );
}
