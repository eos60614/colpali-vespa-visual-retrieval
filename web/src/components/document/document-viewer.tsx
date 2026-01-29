"use client";

import { useState, useReducer, useEffect } from "react";
import Image from "next/image";
import {
  X,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Download,
  Copy,
  FileText,
  Tag,
  Database,
  Link2,
  ExternalLink,
  BookmarkPlus,
  Share2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { getFullImage } from "@/lib/api-client";
import {
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  type SearchResult,
  type DocumentMetadata,
} from "@/types";

interface DocumentViewerProps {
  result: SearchResult | null;
  onClose: () => void;
  onOpenRelated?: (docId: string) => void;
}

export function DocumentViewer({ result, onClose, onOpenRelated }: DocumentViewerProps) {
  const [activeTab, setActiveTab] = useState<"details" | "metadata" | "related">("details");
  type ImgState = { image: string | null; loading: boolean };
  type ImgAction = { type: "loading" } | { type: "loaded"; image: string | null };
  const [imgState, dispatchImg] = useReducer(
    (_: ImgState, action: ImgAction): ImgState => {
      if (action.type === "loading") return { image: null, loading: true };
      return { image: action.image, loading: false };
    },
    { image: null, loading: false }
  );
  const docId = result?.documentId;

  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    dispatchImg({ type: "loading" });
    getFullImage(docId)
      .then((img) => { if (!cancelled) dispatchImg({ type: "loaded", image: img }); })
      .catch((e) => {
        console.error("[DocumentViewer] Failed to load full image:", e);
        if (!cancelled) dispatchImg({ type: "loaded", image: null });
      });
    return () => { cancelled = true; };
  }, [docId]);

  const fullImage = imgState.image;
  const imageLoading = imgState.loading;

  if (!result) return null;

  const metadata: DocumentMetadata | null = null;

  return (
    <div className="fixed inset-0 z-50 animate-fade-in">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-[var(--bg-overlay)] backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Viewer panel */}
      <div className="absolute inset-4 md:inset-8 bg-[var(--bg-elevated)] rounded-[var(--radius-xl)] shadow-[var(--shadow-lg)] flex flex-col overflow-hidden animate-scale-in">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 h-12 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] shrink-0">
          <div className="flex items-center gap-3">
            <FileText className="h-4 w-4" style={{ color: CATEGORY_COLORS[result.category] }} />
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              {result.title}
            </h2>
            <Badge variant="default" className="text-[10px]">
              {CATEGORY_LABELS[result.category]}
            </Badge>
            <span className="text-xs text-[var(--text-tertiary)]">
              Page {result.pageNumber}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-xs text-[var(--text-tertiary)] w-12 text-center">100%</span>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ZoomIn className="h-4 w-4" />
            </Button>
            <div className="w-px h-5 bg-[var(--border-primary)] mx-1" />
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ChevronRight className="h-4 w-4" />
            </Button>
            <div className="w-px h-5 bg-[var(--border-primary)] mx-1" />
            <Tooltip content="Bookmark page">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <BookmarkPlus className="h-4 w-4" />
              </Button>
            </Tooltip>
            <Tooltip content="Share">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Share2 className="h-4 w-4" />
              </Button>
            </Tooltip>
            <Tooltip content="Download">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Download className="h-4 w-4" />
              </Button>
            </Tooltip>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex min-h-0">
          {/* Page viewport */}
          <div className="flex-1 overflow-auto p-8 bg-[var(--bg-tertiary)] flex items-center justify-center">
            {imageLoading ? (
              <div className="bg-white shadow-[var(--shadow-lg)] rounded-sm flex items-center justify-center" style={{ width: "612px", height: "792px" }}>
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs text-gray-400">Loading page...</p>
                </div>
              </div>
            ) : fullImage ? (
              <div className="bg-white shadow-[var(--shadow-lg)] rounded-sm overflow-hidden max-h-full relative" style={{ width: "612px", height: "792px" }}>
                <Image
                  src={fullImage}
                  alt={`${result.title} — Page ${result.pageNumber}`}
                  fill
                  className="object-contain"
                  unoptimized
                />
              </div>
            ) : result.blurImage ? (
              <div className="bg-white shadow-[var(--shadow-lg)] rounded-sm overflow-hidden relative" style={{ width: "612px", height: "792px" }}>
                <Image
                  src={result.blurImage}
                  alt={`${result.title} — Page ${result.pageNumber} (preview)`}
                  fill
                  className="object-contain opacity-60"
                  unoptimized
                />
              </div>
            ) : (
              <div className="bg-white shadow-[var(--shadow-lg)] rounded-sm flex items-center justify-center" style={{ width: "612px", height: "792px" }}>
                <p className="text-xs text-gray-400">Image unavailable</p>
              </div>
            )}
          </div>

          {/* Right panel — tabbed metadata */}
          <div className="w-96 border-l border-[var(--border-primary)] bg-[var(--bg-primary)] flex flex-col">
            {/* Tabs */}
            <div className="flex border-b border-[var(--border-primary)] px-2 shrink-0">
              {(["details", "metadata", "related"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "px-3 py-2.5 text-xs font-medium capitalize transition-all cursor-pointer",
                    "border-b-2 -mb-px",
                    activeTab === tab
                      ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                      : "border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
                  )}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto p-4">
              {activeTab === "details" && (
                <DetailsTab result={result} metadata={metadata} />
              )}
              {activeTab === "metadata" && (
                <MetadataTab result={result} metadata={metadata} />
              )}
              {activeTab === "related" && (
                <RelatedTab metadata={metadata} onOpenRelated={onOpenRelated} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailsTab({ result, metadata }: { result: SearchResult; metadata: DocumentMetadata | null }) {
  return (
    <div className="space-y-4 animate-fade-in">
      <InfoRow label="Document" value={result.title} />
      <InfoRow label="Page" value={String(result.pageNumber)} />
      <InfoRow label="Category" value={CATEGORY_LABELS[result.category]} color={CATEGORY_COLORS[result.category]} />
      <InfoRow label="Relevance" value={`${Math.round(result.relevanceScore * 100)}%`} />

      {metadata?.documentNumber && (
        <InfoRow label="Document Number" value={metadata.documentNumber} mono />
      )}
      {metadata?.author && (
        <InfoRow label="Author" value={metadata.author} />
      )}
      {metadata?.revision && (
        <InfoRow label="Revision" value={metadata.revision} />
      )}
      {metadata?.fileSize && (
        <InfoRow label="File Size" value={metadata.fileSize} />
      )}
      {metadata?.pageCount && (
        <InfoRow label="Total Pages" value={String(metadata.pageCount)} />
      )}

      {/* Tags */}
      {metadata?.tags && metadata.tags.length > 0 && (
        <div>
          <label className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider block mb-2">
            Tags
          </label>
          <div className="flex flex-wrap gap-1.5">
            {metadata.tags.map((tag) => (
              <Badge key={tag} variant="default" className="text-[10px]">
                <Tag className="h-2.5 w-2.5 mr-1 opacity-50" />
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Extracted text */}
      {result.text && (
        <div>
          <label className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider block mb-2">
            Extracted Text
          </label>
          <div className="bg-[var(--bg-secondary)] rounded-[var(--radius-md)] p-3 relative group">
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
              {result.text}
            </p>
            <button className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] cursor-pointer">
              <Copy className="h-3 w-3 text-[var(--text-tertiary)]" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MetadataTab({ result, metadata }: { result: SearchResult; metadata: DocumentMetadata | null }) {
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-2">
        <Database className="h-4 w-4 text-[var(--accent-primary)]" />
        <span className="text-xs font-semibold text-[var(--text-primary)]">
          Index Metadata
        </span>
      </div>

      <p className="text-[11px] text-[var(--text-tertiary)] -mt-2 mb-3">
        Internal metadata for retrieval and agent use.
      </p>

      {metadata?.vespaDocId && (
        <InfoRow label="Vespa Document ID" value={metadata.vespaDocId} mono copyable />
      )}
      {metadata?.embeddingModel && (
        <InfoRow label="Embedding Model" value={metadata.embeddingModel} />
      )}
      {metadata?.indexedAt && (
        <InfoRow label="Indexed At" value={new Date(metadata.indexedAt).toLocaleString()} />
      )}
      {metadata?.extractedTextLength !== undefined && (
        <InfoRow label="Extracted Text" value={`${metadata.extractedTextLength.toLocaleString()} characters`} />
      )}
      {metadata?.hasRegions !== undefined && (
        <InfoRow
          label="Regions Detected"
          value={metadata.hasRegions ? `Yes (${metadata.regionCount} regions)` : "No"}
        />
      )}
      {metadata?.source && (
        <InfoRow label="Source System" value={metadata.source} />
      )}
      {metadata?.uploadedAt && (
        <InfoRow label="Uploaded" value={new Date(metadata.uploadedAt).toLocaleString()} />
      )}
      {metadata?.modifiedAt && (
        <InfoRow label="Last Modified" value={new Date(metadata.modifiedAt).toLocaleString()} />
      )}

      {/* Raw JSON view */}
      <div className="mt-4 pt-4 border-t border-[var(--border-primary)]">
        <label className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider block mb-2">
          Raw Metadata (JSON)
        </label>
        <div className="bg-[var(--bg-secondary)] rounded-[var(--radius-md)] p-3 relative group">
          <pre className="text-[10px] text-[var(--text-secondary)] font-mono whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
            {JSON.stringify(
              {
                id: result.id,
                documentId: result.documentId,
                pageNumber: result.pageNumber,
                category: result.category,
                relevanceScore: result.relevanceScore,
                ...(metadata && {
                  documentNumber: metadata.documentNumber,
                  vespaDocId: metadata.vespaDocId,
                  embeddingModel: metadata.embeddingModel,
                  source: metadata.source,
                  author: metadata.author,
                  revision: metadata.revision,
                  fileSize: metadata.fileSize,
                  pageCount: metadata.pageCount,
                  extractedTextLength: metadata.extractedTextLength,
                  hasRegions: metadata.hasRegions,
                  regionCount: metadata.regionCount,
                  tags: metadata.tags,
                }),
              },
              null,
              2
            )}
          </pre>
          <button className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] cursor-pointer">
            <Copy className="h-3 w-3 text-[var(--text-tertiary)]" />
          </button>
        </div>
      </div>
    </div>
  );
}

function RelatedTab({
  metadata,
  onOpenRelated,
}: {
  metadata: DocumentMetadata | null;
  onOpenRelated?: (docId: string) => void;
}) {
  if (!metadata?.relatedDocuments || metadata.relatedDocuments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
        <Link2 className="h-8 w-8 text-[var(--text-tertiary)] mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">No related documents</p>
        <p className="text-xs text-[var(--text-tertiary)] mt-1">
          Related documents will appear here when cross-references are detected.
        </p>
      </div>
    );
  }

  const relationLabels: Record<string, string> = {
    references: "References",
    referenced_by: "Referenced by",
    supersedes: "Supersedes",
    superseded_by: "Superseded by",
    related: "Related",
  };

  return (
    <div className="space-y-2 animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <Link2 className="h-4 w-4 text-[var(--accent-primary)]" />
        <span className="text-xs font-semibold text-[var(--text-primary)]">
          Related Documents
        </span>
        <Badge variant="muted" className="text-[10px]">
          {metadata.relatedDocuments.length}
        </Badge>
      </div>

      {metadata.relatedDocuments.map((rel) => (
        <button
          key={rel.id}
          onClick={() => onOpenRelated?.(rel.id)}
          className={cn(
            "w-full text-left flex items-center gap-3 p-3 rounded-[var(--radius-md)]",
            "border border-[var(--border-primary)]",
            "hover:border-[var(--border-accent)] hover:bg-[var(--accent-glow)]",
            "transition-all duration-[var(--transition-fast)]",
            "group cursor-pointer"
          )}
        >
          <FileText className="h-4 w-4 text-[var(--text-tertiary)] shrink-0 group-hover:text-[var(--accent-primary)] transition-colors" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-[var(--text-primary)] truncate group-hover:text-[var(--accent-primary)] transition-colors">
              {rel.title}
            </p>
            <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
              {relationLabels[rel.relationship] || rel.relationship}
            </p>
          </div>
          <ExternalLink className="h-3 w-3 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
        </button>
      ))}
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono,
  color,
  copyable,
}: {
  label: string;
  value: string;
  mono?: boolean;
  color?: string;
  copyable?: boolean;
}) {
  return (
    <div className="group">
      <label className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider block mb-1">
        {label}
      </label>
      <div className="flex items-center gap-1.5">
        <p
          className={cn(
            "text-sm",
            mono ? "font-mono text-xs" : "",
            color ? "" : "text-[var(--text-primary)]"
          )}
          style={color ? { color } : undefined}
        >
          {value}
        </p>
        {copyable && (
          <button className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bg-tertiary)] cursor-pointer">
            <Copy className="h-3 w-3 text-[var(--text-tertiary)]" />
          </button>
        )}
      </div>
    </div>
  );
}
