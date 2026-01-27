"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useDocuments } from "@/lib/hooks/use-documents";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { DocumentList } from "@/components/documents/document-list";
import { Input } from "@/components/ui/input";
import { ScopeControls } from "@/components/search/scope-controls";

export default function DocumentsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [searchTerm, setSearchTerm] = useState("");
  const [categories, setCategories] = useState<string[]>([]);

  const { documents, total, loading, error, updateQuery } = useDocuments(projectId, {
    page: 1,
    page_size: 50,
  });

  const handleSearchChange = (value: string) => {
    setSearchTerm(value);
    updateQuery({ search: value || undefined });
  };

  const handleCategoriesChange = (cats: string[]) => {
    setCategories(cats);
    updateQuery({ category: cats[0] || undefined });
  };

  return (
    <div className="flex flex-col h-full">
      <Breadcrumbs items={[{ label: "Documents" }]} />

      <div className="p-4 border-b space-y-3">
        <ScopeControls categories={categories} onCategoriesChange={handleCategoriesChange} />
        <Input
          placeholder="Search documents by name..."
          value={searchTerm}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
        <div className="text-xs text-muted-foreground">{total} documents</div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <DocumentList
          documents={documents}
          loading={loading}
          error={error}
          projectId={projectId}
        />
      </div>
    </div>
  );
}
