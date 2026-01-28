"use client";

import { useState, useMemo, useEffect } from "react";
import { Search, FileText, Hash, Loader2, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, CATEGORY_COLORS, type Document } from "@/types";
import { getDocuments } from "@/lib/api-client";

interface FileSearchProps {
  selectedDocumentIds: string[];
  onToggleDocument: (id: string) => void;
  projectId?: string;
}

export function FileSearch({ selectedDocumentIds, onToggleDocument, projectId }: FileSearchProps) {
  const [filter, setFilter] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch documents from the backend when projectId or filter changes
  useEffect(() => {
    let cancelled = false;

    const params: { projectId?: string; search?: string; limit?: number } = {
      limit: 50,
    };
    if (projectId) params.projectId = projectId;
    if (filter.trim()) params.search = filter.trim();

    const fetchDocs = () => {
      if (cancelled) return;
      setLoading(true);
      getDocuments(params)
        .then((data) => {
          if (!cancelled) {
            setDocuments(data.documents || []);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            console.error("Failed to fetch documents:", err);
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };

    // Debounce when search filter is active
    const timeoutId = setTimeout(fetchDocs, filter.trim() ? 300 : 0);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [projectId, filter]);

  // Client-side filtering for instant name/number/tag matching
  const filteredDocs = useMemo(() => {
    if (!filter.trim()) return documents;
    const q = filter.toLowerCase();
    return documents.filter(
      (d) =>
        d.title.toLowerCase().includes(q) ||
        d.documentNumber?.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [filter, documents]);

  return (
    <div className="border-t border-[var(--border-primary)] bg-[var(--bg-primary)]">
      <div className="px-4 pt-3 pb-2">
        <Input
          placeholder="Search by file name, document number, or tag..."
          icon={<Search className="h-3.5 w-3.5" />}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 text-xs"
        />
      </div>
      <div className="max-h-48 overflow-y-auto px-2 pb-2 space-y-0.5">
        {loading && (
          <div className="flex items-center justify-center py-4 text-xs text-[var(--text-tertiary)]">
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" />
            Loading documents...
          </div>
        )}
        {!loading && filteredDocs.map((doc) => {
          const isSelected = selectedDocumentIds.includes(doc.id);
          return (
            <button
              key={doc.id}
              onClick={() => onToggleDocument(doc.id)}
              className={cn(
                "w-full text-left flex items-center gap-3 px-3 py-2 rounded-[var(--radius-md)]",
                "transition-all duration-[var(--transition-fast)] group cursor-pointer",
                isSelected
                  ? "bg-[var(--accent-glow)] ring-1 ring-[var(--border-accent)]"
                  : "hover:bg-[var(--bg-tertiary)]"
              )}
            >
              <div
                className={cn(
                  "w-5 h-5 rounded-[var(--radius-sm)] border flex items-center justify-center shrink-0",
                  "transition-all duration-[var(--transition-fast)]",
                  isSelected
                    ? "bg-[var(--accent-primary)] border-[var(--accent-primary)]"
                    : "border-[var(--border-secondary)] group-hover:border-[var(--accent-primary)]"
                )}
              >
                {isSelected && <Check className="h-3 w-3 text-white" />}
              </div>
              <FileText className="h-4 w-4 shrink-0" style={{ color: CATEGORY_COLORS[doc.category] }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-[var(--text-primary)] truncate">
                    {doc.title}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  {doc.documentNumber && (
                    <span className="text-[10px] text-[var(--text-tertiary)] flex items-center gap-0.5">
                      <Hash className="h-2.5 w-2.5" />
                      {doc.documentNumber}
                    </span>
                  )}
                  {doc.pageCount > 0 && (
                    <span className="text-[10px] text-[var(--text-tertiary)]">
                      {doc.pageCount}p
                    </span>
                  )}
                </div>
              </div>
              <Badge variant="default" className="text-[10px] shrink-0">
                {CATEGORY_LABELS[doc.category] || doc.category}
              </Badge>
            </button>
          );
        })}
        {!loading && filteredDocs.length === 0 && (
          <div className="text-center py-4 text-xs text-[var(--text-tertiary)]">
            {filter.trim()
              ? <>No documents match &ldquo;{filter}&rdquo;</>
              : "No documents found for this project"
            }
          </div>
        )}
      </div>
    </div>
  );
}
