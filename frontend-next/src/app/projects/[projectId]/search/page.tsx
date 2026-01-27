"use client";

import { useCallback, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useSearch } from "@/lib/hooks/use-search";
import { useSessionStore } from "@/stores/session-store";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { SearchBox } from "@/components/search/search-box";
import { ScopeControls } from "@/components/search/scope-controls";
import { SearchResults } from "@/components/search/search-results";
import { ChatPanel } from "@/components/chat/chat-panel";

export default function SearchPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const defaultQuery = searchParams.get("q") || "";

  const { results, queryId, totalCount, searchTimeMs, loading, error, search } = useSearch();
  const categories = useSessionStore((s) => s.categoryFilters);
  const setCategories = useSessionStore((s) => s.setCategories);
  const addRecentQuery = useSessionStore((s) => s.addRecentQuery);

  const [lastQuery, setLastQuery] = useState(defaultQuery);

  const handleSearch = useCallback(
    async (query: string, ranking: string) => {
      setLastQuery(query);
      addRecentQuery(query, projectId);
      await search({
        query,
        project_id: projectId,
        categories: categories.length > 0 ? categories : undefined,
        ranking: ranking as "hybrid" | "colpali" | "bm25",
        rerank: true,
      });
    },
    [projectId, categories, search, addRecentQuery]
  );

  const docIds = results.map((r) => r.doc_id);

  return (
    <div className="flex flex-col h-full">
      <Breadcrumbs items={[{ label: "Search" }]} />

      <div className="p-4 border-b space-y-3">
        <ScopeControls categories={categories} onCategoriesChange={setCategories} />
        <SearchBox
          onSearch={handleSearch}
          defaultQuery={defaultQuery}
          projectId={projectId}
        />
      </div>

      <div className="flex-1 grid grid-cols-1 md:grid-cols-[3fr_2fr] overflow-hidden">
        <div className="overflow-y-auto p-4">
          <SearchResults
            results={results}
            queryId={queryId}
            totalCount={totalCount}
            searchTimeMs={searchTimeMs}
            loading={loading}
            error={error}
            projectId={projectId}
          />
        </div>
        <div className="border-l hidden md:block overflow-y-auto">
          <ChatPanel queryId={queryId} query={lastQuery} docIds={docIds} />
        </div>
      </div>
    </div>
  );
}
