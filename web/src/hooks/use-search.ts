"use client";

import { useState, useCallback, useRef } from "react";
import type { SearchResult, AIAnswer, DocumentCategory, RecentQuery } from "@/types";

const DEMO_RESULTS: SearchResult[] = [
  {
    id: "res-1",
    documentId: "doc-fire-protection",
    title: "Fire Protection — MEP Drawings Sheet M-401",
    pageNumber: 12,
    snippet:
      "All duct penetrations through fire-rated assemblies shall maintain a minimum 2-hour fire rating. Install UL-listed fire dampers at each penetration point per NFPA 90A Section 5.3. Damper sleeves shall extend the full depth of the rated assembly plus 6 inches on each side.",
    relevanceScore: 0.94,
    category: "drawing",
    text: "Fire Protection Requirements for Mechanical Systems. Section 5.3 Duct Penetrations. All duct penetrations through fire-rated assemblies shall maintain a minimum 2-hour fire rating...",
  },
  {
    id: "res-2",
    documentId: "doc-rfi-287",
    title: "RFI #287 — Fire Damper Installation at Level 3 Corridor",
    pageNumber: 1,
    snippet:
      "Response: Per specification Section 23 33 00, fire dampers shall be UL 555 listed and installed per manufacturer instructions. The 2-hour rating is required for all corridor wall penetrations on Levels 2 through 15.",
    relevanceScore: 0.89,
    category: "rfi",
    text: "RFI #287 Response. Fire Damper Installation at Level 3 Corridor. Question: What rating is required for duct penetrations at the Level 3 corridor wall?",
  },
  {
    id: "res-3",
    documentId: "doc-spec-23",
    title: "Specification Section 23 33 00 — Ductwork Accessories",
    pageNumber: 8,
    snippet:
      "2.03 FIRE DAMPERS: A. Manufacturers: Ruskin Model FSD60. B. Rating: UL 555, 1.5-hour minimum, 2-hour where indicated on drawings. C. Closure rating: Class I leakage. D. Mounting: In-sleeve with breakaway connection.",
    relevanceScore: 0.86,
    category: "spec",
    text: "Section 23 33 00 — Ductwork Accessories. Part 2 — Products. 2.03 Fire Dampers...",
  },
  {
    id: "res-4",
    documentId: "doc-submittal-145",
    title: "Submittal #145 — Ruskin FSD60 Fire Damper",
    pageNumber: 3,
    snippet:
      "Product Data: UL 555 listed, 1.5 and 2-hour ratings available. Galvanized steel sleeve, integral mounting angles. Fusible link rated at 165\u00b0F standard. Certified for installation in concrete block, drywall, and poured concrete assemblies.",
    relevanceScore: 0.82,
    category: "submittal",
    text: "Submittal #145. Ruskin FSD60 Fire Damper product data...",
  },
];

const DEMO_ANSWER: AIAnswer = {
  text: `Based on the project documents, <b>duct penetrations through fire-rated assemblies require a minimum 2-hour fire rating</b>.

<p>This requirement is established across multiple documents:</p>

<ul>
<li><b>MEP Drawing M-401</b> (Sheet 12) specifies that all duct penetrations through fire-rated assemblies must maintain a 2-hour rating, with UL-listed fire dampers installed per NFPA 90A Section 5.3. <sup>[1]</sup></li>
<li><b>RFI #287</b> confirms the 2-hour rating applies to all corridor wall penetrations on Levels 2 through 15. <sup>[2]</sup></li>
<li><b>Specification Section 23 33 00</b> details the product requirements: UL 555 listed dampers with a minimum 1.5-hour rating, upgraded to 2-hour where indicated on drawings. <sup>[3]</sup></li>
</ul>

<p>The approved product is the <b>Ruskin FSD60</b>, per Submittal #145, which carries both 1.5-hour and 2-hour UL ratings. <sup>[4]</sup></p>`,
  citations: [
    { sourceIndex: 0, resultId: "res-1", text: "MEP Drawing M-401", pageNumber: 12, documentTitle: "Fire Protection — MEP Drawings Sheet M-401" },
    { sourceIndex: 1, resultId: "res-2", text: "RFI #287", pageNumber: 1, documentTitle: "RFI #287 — Fire Damper Installation at Level 3 Corridor" },
    { sourceIndex: 2, resultId: "res-3", text: "Spec Section 23 33 00", pageNumber: 8, documentTitle: "Specification Section 23 33 00 — Ductwork Accessories" },
    { sourceIndex: 3, resultId: "res-4", text: "Submittal #145", pageNumber: 3, documentTitle: "Submittal #145 — Ruskin FSD60 Fire Damper" },
  ],
  isStreaming: false,
};

const DEMO_RECENT_QUERIES: RecentQuery[] = [
  { id: "rq-1", query: "What fire rating is required for duct penetrations?", projectId: "proj-harbor-tower", timestamp: "2025-01-15T10:30:00Z", resultCount: 4 },
  { id: "rq-2", query: "Concrete mix design specifications for foundation", projectId: "proj-harbor-tower", timestamp: "2025-01-15T09:15:00Z", resultCount: 6 },
  { id: "rq-3", query: "Elevator shaft dimensions Level 1 to Level 32", projectId: "proj-harbor-tower", timestamp: "2025-01-14T16:00:00Z", resultCount: 3 },
  { id: "rq-4", query: "Waterproofing membrane below grade walls", projectId: "proj-harbor-tower", timestamp: "2025-01-14T14:30:00Z", resultCount: 5 },
  { id: "rq-5", query: "Structural steel connection details at grid B-7", projectId: "proj-harbor-tower", timestamp: "2025-01-14T11:00:00Z", resultCount: 2 },
];

export function useSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<AIAnswer | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [recentQueries] = useState<RecentQuery[]>(DEMO_RECENT_QUERIES);
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [searchDuration, setSearchDuration] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(
    async (
      searchQuery: string,
      _projectId: string,
      _categories: DocumentCategory[],
      _documentIds: string[]
    ) => {
      if (!searchQuery.trim()) return;

      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setQuery(searchQuery);
      setResults([]);
      setAnswer(null);
      setIsSearching(true);
      setIsStreaming(false);
      setSelectedResultId(null);
      setSearchDuration(null);

      const start = performance.now();

      // Simulate retrieval phase
      await new Promise((r) => setTimeout(r, 800));
      setResults(DEMO_RESULTS);
      setSelectedResultId(DEMO_RESULTS[0].id);
      setSearchDuration(Math.round(performance.now() - start));
      setIsSearching(false);

      // Simulate streaming answer
      setIsStreaming(true);
      const fullText = DEMO_ANSWER.text;
      const words = fullText.split(/(\s+)/);
      let accumulated = "";

      for (let i = 0; i < words.length; i++) {
        if (abortRef.current?.signal.aborted) return;
        accumulated += words[i];
        setAnswer({
          ...DEMO_ANSWER,
          text: accumulated,
          isStreaming: true,
        });
        await new Promise((r) => setTimeout(r, 12 + Math.random() * 18));
      }

      setAnswer({ ...DEMO_ANSWER, isStreaming: false });
      setIsStreaming(false);
    },
    []
  );

  const clearSearch = useCallback(() => {
    abortRef.current?.abort();
    setQuery("");
    setResults([]);
    setAnswer(null);
    setIsSearching(false);
    setIsStreaming(false);
    setSelectedResultId(null);
    setSearchDuration(null);
  }, []);

  return {
    query,
    setQuery,
    results,
    answer,
    isSearching,
    isStreaming,
    recentQueries,
    selectedResultId,
    setSelectedResultId,
    searchDuration,
    search,
    clearSearch,
  };
}
