"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/topbar";
import { ScopeBar } from "@/components/scope/scope-bar";
import { QueryInput } from "@/components/search/query-input";
import { FileSearch } from "@/components/search/file-search";
import { SplitView } from "@/components/results/split-view";
import { DocumentViewer } from "@/components/document/document-viewer";
import { useProject, useScope } from "@/hooks/use-project";
import { useSearch } from "@/hooks/use-search";
import type { Citation } from "@/types";

export function Workspace() {
  const [isDark, setIsDark] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showFileSearch, setShowFileSearch] = useState(false);
  const [previewResultId, setPreviewResultId] = useState<string | null>(null);

  const { projects, activeProject, selectProject } = useProject();
  const scope = useScope();
  const search = useSearch();

  const handleToggleTheme = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  }, []);

  const handleSearch = useCallback(
    (query: string) => {
      if (!activeProject) return;
      search.search(
        query,
        activeProject.id,
        scope.selectedCategories,
        scope.selectedDocumentIds
      );
    },
    [activeProject, scope.selectedCategories, scope.selectedDocumentIds, search]
  );

  const handleCitationClick = useCallback(
    (citation: Citation) => {
      search.setSelectedResultId(citation.resultId);
    },
    [search]
  );

  const handleToggleDocument = useCallback(
    (docId: string) => {
      if (scope.selectedDocumentIds.includes(docId)) {
        scope.removeDocumentId(docId);
      } else {
        scope.addDocumentId(docId);
      }
    },
    [scope]
  );

  const handleSelectQuery = useCallback(
    (query: string) => {
      search.setQuery(query);
      handleSearch(query);
    },
    [search, handleSearch]
  );

  const previewResult = previewResultId
    ? search.results.find((r) => r.id === previewResultId) ?? null
    : null;

  const hasResults = search.results.length > 0 || search.isSearching;

  return (
    <div className={cn("h-screen flex", isDark && "dark")}>
      {/* Sidebar */}
      <Sidebar
        projects={projects}
        activeProject={activeProject}
        onSelectProject={selectProject}
        recentQueries={search.recentQueries}
        onSelectQuery={handleSelectQuery}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--bg-primary)]">
        {/* Top bar */}
        <TopBar
          project={activeProject}
          isDark={isDark}
          onToggleTheme={handleToggleTheme}
        />

        {/* Scope bar */}
        <ScopeBar
          project={activeProject}
          selectedCategories={scope.selectedCategories}
          selectedDocumentIds={scope.selectedDocumentIds}
          onToggleCategory={scope.toggleCategory}
          onClearCategories={scope.clearCategories}
          onRemoveDocument={scope.removeDocumentId}
          onClearAll={scope.clearAll}
        />

        {/* Content area */}
        <div className="flex-1 flex flex-col min-h-0">
          {!hasResults ? (
            /* Landing state — centered query input */
            <div className="flex-1 flex flex-col items-center justify-center px-6">
              <div className="mb-8 text-center animate-fade-in-up">
                <div className="w-14 h-14 rounded-[var(--radius-xl)] bg-gradient-to-br from-[#d97756] to-[#b85636] flex items-center justify-center mx-auto mb-5 shadow-[var(--shadow-glow)] animate-float">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.3" />
                    <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                  What do you need to find?
                </h2>
                <p className="text-sm text-[var(--text-tertiary)] max-w-md">
                  Search across{" "}
                  {activeProject ? (
                    <>
                      <span className="text-[var(--text-secondary)] font-medium">
                        {activeProject.documentCount.toLocaleString()}
                      </span>{" "}
                      documents in{" "}
                      <span className="text-[var(--text-secondary)] font-medium">
                        {activeProject.name}
                      </span>
                    </>
                  ) : (
                    "your construction documents"
                  )}
                  . CoPoly retrieves the exact pages you need, then explains what&apos;s on them.
                </p>
              </div>
              <QueryInput
                value={search.query}
                onChange={search.setQuery}
                onSubmit={handleSearch}
                onClear={search.clearSearch}
                isSearching={search.isSearching}
                scopeDescription={scope.scopeDescription}
              />

              {/* Stats bar */}
              {activeProject && (
                <div className="mt-10 flex items-center gap-6 text-[11px] text-[var(--text-tertiary)] animate-fade-in" style={{ animationDelay: "300ms" }}>
                  {activeProject.categories.slice(0, 4).map((cat) => (
                    <span key={cat.category} className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: `var(--text-tertiary)` }}
                      />
                      {cat.count} {cat.category === "rfi" ? "RFIs" : cat.category.charAt(0).toUpperCase() + cat.category.slice(1) + "s"}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Results state — split view */
            <>
              {/* Compact query input */}
              <div className="px-4 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)]">
                <QueryInput
                  value={search.query}
                  onChange={search.setQuery}
                  onSubmit={handleSearch}
                  onClear={search.clearSearch}
                  isSearching={search.isSearching}
                  scopeDescription={scope.scopeDescription}
                />
              </div>

              <SplitView
                results={search.results}
                answer={search.answer}
                isSearching={search.isSearching}
                isStreaming={search.isStreaming}
                selectedResultId={search.selectedResultId}
                onSelectResult={search.setSelectedResultId}
                onPreviewResult={setPreviewResultId}
                onCitationClick={handleCitationClick}
                searchDuration={search.searchDuration}
                query={search.query}
              />
            </>
          )}
        </div>
      </div>

      {/* Document viewer modal */}
      <DocumentViewer
        result={previewResult}
        onClose={() => setPreviewResultId(null)}
      />
    </div>
  );
}
