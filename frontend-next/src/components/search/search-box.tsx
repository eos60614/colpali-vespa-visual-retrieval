"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RankingSelector } from "./ranking-selector";
import { fetchSuggestions } from "@/lib/api-client";

interface SearchBoxProps {
  onSearch: (query: string, ranking: string) => void;
  defaultQuery?: string;
  defaultRanking?: string;
  projectId?: string;
}

export function SearchBox({
  onSearch,
  defaultQuery = "",
  defaultRanking = "hybrid",
  projectId,
}: SearchBoxProps) {
  const [query, setQuery] = useState(defaultQuery);
  const [ranking, setRanking] = useState(defaultRanking);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (query.trim()) {
        onSearch(query.trim(), ranking);
        setShowSuggestions(false);
      }
    },
    [query, ranking, onSearch]
  );

  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (value.trim().length >= 2) {
        debounceRef.current = setTimeout(async () => {
          try {
            const results = await fetchSuggestions(value, projectId);
            setSuggestions(results);
            setShowSuggestions(results.length > 0);
          } catch {
            setSuggestions([]);
          }
        }, 300);
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    },
    [projectId]
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex gap-2" ref={containerRef}>
        <div className="relative flex-1">
          <Input
            type="text"
            placeholder="Search documents..."
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          />
          {showSuggestions && (
            <div className="absolute top-full left-0 right-0 mt-1 rounded-md border bg-popover shadow-lg z-50 max-h-48 overflow-y-auto">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setQuery(s);
                    setShowSuggestions(false);
                    onSearch(s, ranking);
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        <RankingSelector value={ranking} onChange={setRanking} />
        <Button type="submit">Search</Button>
      </div>
    </form>
  );
}
