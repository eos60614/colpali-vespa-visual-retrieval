"use client";

import { useState, useRef, useCallback, useEffect, useReducer, type KeyboardEvent, type FormEvent } from "react";
import { Search, ArrowUp, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { getSuggestions } from "@/lib/api-client";

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
  const [selectedSuggestionIdx, setSelectedSuggestionIdx] = useState(-1);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsAbortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  type SuggestState = { items: string[]; visible: boolean };
  type SuggestAction =
    | { type: "clear" }
    | { type: "show"; items: string[] }
    | { type: "hide" };
  const [suggestState, dispatchSuggest] = useReducer(
    (_: SuggestState, action: SuggestAction): SuggestState => {
      if (action.type === "clear") return { items: [], visible: false };
      if (action.type === "show") return { items: action.items, visible: action.items.length > 0 };
      return { ..._,  visible: false };
    },
    { items: [], visible: false }
  );
  const suggestions = suggestState.items;
  const showSuggestions = suggestState.visible;

  // Debounced suggestion fetching
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    suggestionsAbortRef.current?.abort();

    if (!value || value.length < 2) {
      dispatchSuggest({ type: "clear" });
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const ctrl = new AbortController();
      suggestionsAbortRef.current = ctrl;
      try {
        const results = await getSuggestions(value, ctrl.signal);
        if (!ctrl.signal.aborted) {
          dispatchSuggest({ type: "show", items: results.slice(0, 6) });
          setSelectedSuggestionIdx(-1);
        }
      } catch {
        // aborted or failed
      }
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value]);

  const handleSubmit = useCallback(
    (e?: FormEvent) => {
      e?.preventDefault();
      if (value.trim() && !isSearching) {
        dispatchSuggest({ type: "hide" });
        onSubmit(value.trim());
        inputRef.current?.blur();
      }
    },
    [value, isSearching, onSubmit]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (showSuggestions && suggestions.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedSuggestionIdx((prev) =>
            prev < suggestions.length - 1 ? prev + 1 : 0
          );
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedSuggestionIdx((prev) =>
            prev > 0 ? prev - 1 : suggestions.length - 1
          );
          return;
        }
        if (e.key === "Escape") {
          dispatchSuggest({ type: "hide" });
          return;
        }
        if (e.key === "Enter" && !e.shiftKey && selectedSuggestionIdx >= 0) {
          e.preventDefault();
          const selected = suggestions[selectedSuggestionIdx];
          onChange(selected);
          dispatchSuggest({ type: "hide" });
          onSubmit(selected);
          inputRef.current?.blur();
          return;
        }
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, showSuggestions, suggestions, selectedSuggestionIdx, onChange, onSubmit]
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
              onFocus={() => {
                setIsFocused(true);
                if (suggestions.length > 0) dispatchSuggest({ type: "show", items: suggestions });
              }}
              onBlur={() => {
                setIsFocused(false);
                // Delay hiding so click on suggestion registers
                setTimeout(() => dispatchSuggest({ type: "hide" }), 200);
              }}
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

        {/* Autocomplete suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && isFocused && (
          <div className="absolute left-0 right-0 top-full mt-1 z-50 rounded-[var(--radius-lg)] border border-[var(--border-primary)] bg-[var(--bg-elevated)] shadow-[var(--shadow-md)] overflow-hidden">
            {suggestions.map((s, i) => (
              <button
                key={s}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(s);
                  dispatchSuggest({ type: "hide" });
                  onSubmit(s);
                }}
                className={cn(
                  "w-full text-left px-4 py-2 text-sm flex items-center gap-2 cursor-pointer",
                  "transition-colors",
                  i === selectedSuggestionIdx
                    ? "bg-[var(--accent-glow)] text-[var(--accent-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                )}
              >
                <Search className="h-3 w-3 opacity-40 shrink-0" />
                <span className="truncate">{s}</span>
              </button>
            ))}
          </div>
        )}
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
