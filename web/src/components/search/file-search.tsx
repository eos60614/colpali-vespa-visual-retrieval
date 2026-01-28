"use client";

import { useState, useMemo } from "react";
import { Search, FileText, Hash, Tag, ChevronRight, Plus, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, CATEGORY_COLORS, type Document, type DocumentCategory } from "@/types";

const DEMO_DOCUMENTS: Document[] = [
  { id: "doc-1", title: "MEP Drawings — Fire Protection", documentNumber: "M-401", category: "drawing", pageCount: 24, uploadedAt: "2025-01-05", tags: ["MEP", "fire protection"] },
  { id: "doc-2", title: "Structural Steel Connection Details", documentNumber: "S-302", category: "drawing", pageCount: 18, uploadedAt: "2025-01-04", tags: ["structural", "steel"] },
  { id: "doc-3", title: "RFI #287 — Fire Damper Installation", documentNumber: "RFI-287", category: "rfi", pageCount: 3, uploadedAt: "2025-01-10", tags: ["fire damper", "mechanical"] },
  { id: "doc-4", title: "RFI #312 — Concrete Pour Sequence", documentNumber: "RFI-312", category: "rfi", pageCount: 2, uploadedAt: "2025-01-12", tags: ["concrete", "schedule"] },
  { id: "doc-5", title: "Specification Section 23 33 00 — Ductwork", documentNumber: "23-33-00", category: "spec", pageCount: 15, uploadedAt: "2024-12-20", tags: ["ductwork", "HVAC"] },
  { id: "doc-6", title: "Submittal #145 — Ruskin FSD60 Fire Damper", documentNumber: "SUB-145", category: "submittal", pageCount: 8, uploadedAt: "2025-01-08", tags: ["fire damper", "Ruskin"] },
  { id: "doc-7", title: "Change Order #19 — Foundation Redesign", documentNumber: "CO-019", category: "change_order", pageCount: 5, uploadedAt: "2025-01-11", tags: ["foundation", "redesign"] },
  { id: "doc-8", title: "Architectural Floor Plan — Level 3", documentNumber: "A-103", category: "drawing", pageCount: 1, uploadedAt: "2024-11-15", tags: ["floor plan", "Level 3"] },
];

interface FileSearchProps {
  selectedDocumentIds: string[];
  onToggleDocument: (id: string) => void;
}

export function FileSearch({ selectedDocumentIds, onToggleDocument }: FileSearchProps) {
  const [filter, setFilter] = useState("");

  const filteredDocs = useMemo(() => {
    if (!filter.trim()) return DEMO_DOCUMENTS;
    const q = filter.toLowerCase();
    return DEMO_DOCUMENTS.filter(
      (d) =>
        d.title.toLowerCase().includes(q) ||
        d.documentNumber?.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [filter]);

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
        {filteredDocs.map((doc) => {
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
                  <span className="text-[10px] text-[var(--text-tertiary)]">
                    {doc.pageCount}p
                  </span>
                </div>
              </div>
              <Badge variant="default" className="text-[10px] shrink-0">
                {CATEGORY_LABELS[doc.category]}
              </Badge>
            </button>
          );
        })}
        {filteredDocs.length === 0 && (
          <div className="text-center py-4 text-xs text-[var(--text-tertiary)]">
            No documents match &ldquo;{filter}&rdquo;
          </div>
        )}
      </div>
    </div>
  );
}
