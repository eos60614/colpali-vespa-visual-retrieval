"use client";

import { useState, useCallback, useRef, type DragEvent, type ChangeEvent } from "react";
import { Upload, FileText, X, Check, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { uploadDocument } from "@/lib/api-client";

type UploadState = "idle" | "uploading" | "success" | "error";

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      setFile(dropped);
      if (!title) setTitle(dropped.name.replace(/\.pdf$/i, ""));
    }
  }, [title]);

  const handleFileChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) {
        setFile(selected);
        if (!title) setTitle(selected.name.replace(/\.pdf$/i, ""));
      }
    },
    [title]
  );

  const handleSubmit = useCallback(async () => {
    if (!file) return;

    setState("uploading");
    setMessage("");

    const formData = new FormData();
    formData.append("pdf_file", file);
    formData.append("title", title);
    formData.append("description", description);
    formData.append("tags", tags);

    try {
      const result = await uploadDocument(formData);
      if (result.success) {
        setState("success");
        setMessage(result.message || "Document uploaded and indexed successfully.");
      } else {
        setState("error");
        setMessage("Upload failed. Please try again.");
      }
    } catch (e) {
      setState("error");
      setMessage(e instanceof Error ? e.message : "Upload failed");
    }
  }, [file, title, description, tags]);

  const handleReset = useCallback(() => {
    setFile(null);
    setTitle("");
    setDescription("");
    setTags("");
    setState("idle");
    setMessage("");
  }, []);

  if (state === "success") {
    return (
      <div className="rounded-[var(--radius-xl)] border border-[var(--border-primary)] bg-[var(--bg-elevated)] p-8 text-center animate-fade-in-up">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
          <Check className="h-6 w-6 text-emerald-500" />
        </div>
        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">
          Upload Complete
        </h3>
        <p className="text-sm text-[var(--text-secondary)] mb-6">{message}</p>
        <div className="flex gap-3 justify-center">
          <Button variant="secondary" onClick={handleReset}>
            Upload Another
          </Button>
          <Button variant="accent" onClick={() => (window.location.href = "/")}>
            Search Documents
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          "rounded-[var(--radius-xl)] border-2 border-dashed p-10 text-center cursor-pointer",
          "transition-all duration-[var(--transition-base)]",
          isDragging
            ? "border-[var(--accent-primary)] bg-[var(--accent-glow)]"
            : file
              ? "border-[var(--border-accent)] bg-[var(--bg-elevated)]"
              : "border-[var(--border-primary)] bg-[var(--bg-secondary)] hover:border-[var(--border-secondary)]"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />

        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileText className="h-8 w-8 text-[var(--accent-primary)]" />
            <div className="text-left">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {file.name}
              </p>
              <p className="text-xs text-[var(--text-tertiary)]">
                {(file.size / 1024 / 1024).toFixed(1)} MB
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setFile(null);
              }}
              className="p-1 rounded hover:bg-[var(--bg-tertiary)] cursor-pointer"
            >
              <X className="h-4 w-4 text-[var(--text-tertiary)]" />
            </button>
          </div>
        ) : (
          <>
            <Upload className="h-10 w-10 text-[var(--text-tertiary)] mx-auto mb-3" />
            <p className="text-sm text-[var(--text-secondary)] mb-1">
              Drop a PDF here, or click to browse
            </p>
            <p className="text-xs text-[var(--text-tertiary)]">
              Maximum file size: 250 MB
            </p>
          </>
        )}
      </div>

      {/* Form fields */}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1.5">
            Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Document title (auto-filled from filename)"
            maxLength={200}
            className={cn(
              "w-full px-3 py-2 rounded-[var(--radius-md)] border border-[var(--border-primary)]",
              "bg-[var(--bg-elevated)] text-sm text-[var(--text-primary)]",
              "placeholder:text-[var(--text-tertiary)]",
              "focus:outline-none focus:border-[var(--accent-primary)] focus:ring-1 focus:ring-[var(--accent-glow)]",
              "transition-all"
            )}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1.5">
            Description
            <span className="text-[var(--text-tertiary)] font-normal ml-1">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description of the document content"
            maxLength={1000}
            rows={3}
            className={cn(
              "w-full px-3 py-2 rounded-[var(--radius-md)] border border-[var(--border-primary)]",
              "bg-[var(--bg-elevated)] text-sm text-[var(--text-primary)]",
              "placeholder:text-[var(--text-tertiary)]",
              "focus:outline-none focus:border-[var(--accent-primary)] focus:ring-1 focus:ring-[var(--accent-glow)]",
              "transition-all resize-none"
            )}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-[var(--text-secondary)] block mb-1.5">
            Tags
            <span className="text-[var(--text-tertiary)] font-normal ml-1">(comma-separated, optional)</span>
          </label>
          <input
            type="text"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g. structural, foundation, Level 2"
            className={cn(
              "w-full px-3 py-2 rounded-[var(--radius-md)] border border-[var(--border-primary)]",
              "bg-[var(--bg-elevated)] text-sm text-[var(--text-primary)]",
              "placeholder:text-[var(--text-tertiary)]",
              "focus:outline-none focus:border-[var(--accent-primary)] focus:ring-1 focus:ring-[var(--accent-glow)]",
              "transition-all"
            )}
          />
        </div>
      </div>

      {/* Error message */}
      {state === "error" && message && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-[var(--radius-md)] bg-red-500/10 border border-red-500/20 animate-fade-in">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-500">{message}</p>
        </div>
      )}

      {/* Submit */}
      <Button
        variant="accent"
        onClick={handleSubmit}
        disabled={!file || state === "uploading"}
        className="w-full h-11"
      >
        {state === "uploading" ? (
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Uploading & processing...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Upload & Index
          </span>
        )}
      </Button>
    </div>
  );
}
