"use client";

import { useState, useRef, useCallback, type KeyboardEvent, type FormEvent } from "react";
import { Search, ArrowUp, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (query: string) => void;
  onClear: () => void;
  isSearching: boolean;
  scopeDescription: string;
  placeholder?: string;
}

const SAMPLE_QUERIES = [
  "What fire rating is required for duct penetrations?",
  "Concrete mix design for foundation piers",
  "Waterproofing details at below-grade walls",
  "Steel connection at grid line B-7",
  "Window schedule for east elevation",
  "HVAC equipment access clearances",
];

export function QueryInput({
  value,
  onChange,
  onSubmit,
  onClear,
  isSearching,
  scopeDescription,
  placeholder,
}: QueryInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(
    (e?: FormEvent) => {
      e?.preventDefault();
      if (value.trim() && !isSearching) {
        onSubmit(value.trim());
        inputRef.current?.blur();
      }
    },
    [value, isSearching, onSubmit]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleSampleQuery = useCallback(
    (q: string) => {
      onChange(q);
      onSubmit(q);
    },
    [onChange, onSubmit]
  );

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Input container */}
      <form onSubmit={handleSubmit}>
        <div
          className={cn(
            "relative rounded-[var(--radius-xl)] border transition-all duration-[var(--transition-base)]",
            isFocused
              ? "border-[var(--accent-primary)] shadow-[var(--shadow-glow)] ring-1 ring-[var(--accent-glow)]"
              : "border-[var(--border-primary)] hover:border-[var(--border-secondary)]",
            "bg-[var(--bg-elevated)]"
          )}
        >
          {/* Scope indicator */}
          <div className="flex items-center gap-1.5 px-4 pt-3 pb-1">
            <Sparkles className="h-3 w-3 text-[var(--accent-primary)]" />
            <span className="text-[11px] text-[var(--text-tertiary)]">
              Searching {scopeDescription.toLowerCase()}
            </span>
          </div>

          {/* Textarea */}
          <div className="relative flex items-end">
            <textarea
              ref={inputRef}
              value={value}
              onChange={(e) => {
                onChange(e.target.value);
                // Auto-resize
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              placeholder={
                placeholder || "Ask about your construction documents..."
              }
              rows={1}
              className={cn(
                "w-full resize-none bg-transparent text-sm text-[var(--text-primary)]",
                "placeholder:text-[var(--text-tertiary)]",
                "px-4 py-2 pr-14",
                "focus:outline-none",
                "min-h-[36px] max-h-[120px]"
              )}
            />
            <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
              {value && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    onChange("");
                    onClear();
                    inputRef.current?.focus();
                  }}
                  className="h-7 w-7"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              )}
              <Button
                type="submit"
                variant={value.trim() ? "accent" : "secondary"}
                size="icon"
                disabled={!value.trim() || isSearching}
                className={cn(
                  "h-8 w-8 rounded-[var(--radius-lg)]",
                  isSearching && "animate-pulse"
                )}
              >
                {isSearching ? (
                  <div className="typing-indicator">
                    <span /><span /><span />
                  </div>
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </form>

      {/* Sample queries */}
      {!value && (
        <div className="mt-4 animate-fade-in">
          <p className="text-[11px] text-[var(--text-tertiary)] mb-2 px-1">
            Try asking
          </p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_QUERIES.slice(0, 4).map((q) => (
              <button
                key={q}
                onClick={() => handleSampleQuery(q)}
                className={cn(
                  "px-3 py-1.5 rounded-[var(--radius-full)] text-xs",
                  "border border-[var(--border-primary)] text-[var(--text-secondary)]",
                  "hover:border-[var(--border-accent)] hover:text-[var(--accent-primary)]",
                  "hover:bg-[var(--accent-glow)]",
                  "transition-all duration-[var(--transition-fast)]",
                  "cursor-pointer"
                )}
              >
                <span className="flex items-center gap-1.5">
                  <Search className="h-3 w-3 opacity-50" />
                  {q}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
