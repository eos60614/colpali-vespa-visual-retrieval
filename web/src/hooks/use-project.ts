"use client";

import { useState, useCallback, useEffect } from "react";
import type { Project, DocumentCategory } from "@/types";
import { getProjects } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";

export function useProject() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  const { selectedProjectId, setSelectedProjectId } = useAppStore();

  // Fetch projects from the backend on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getProjects()
      .then((data) => {
        if (cancelled) return;
        const fetched = data.projects || [];
        setProjects(fetched);

        // Select the previously-stored project if it exists in the list,
        // otherwise fall back to the first project
        if (fetched.length > 0) {
          const stored = fetched.find((p) => p.id === selectedProjectId);
          const initial = stored || fetched[0];
          setActiveProject(initial);
          if (!stored) {
            setSelectedProjectId(initial.id);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to fetch projects:", err);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // Only run on mount — selectedProjectId is read once for initial selection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectProject = useCallback(
    (projectId: string) => {
      const project = projects.find((p) => p.id === projectId);
      if (project) {
        setActiveProject(project);
        setSelectedProjectId(projectId);
      }
    },
    [projects, setSelectedProjectId]
  );

  return { projects, activeProject, selectProject, loading };
}

export function useScope() {
  const [selectedCategories, setSelectedCategories] = useState<DocumentCategory[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);

  const toggleCategory = useCallback((category: DocumentCategory) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  }, []);

  const clearCategories = useCallback(() => setSelectedCategories([]), []);

  const addDocumentId = useCallback((id: string) => {
    setSelectedDocumentIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }, []);

  const removeDocumentId = useCallback((id: string) => {
    setSelectedDocumentIds((prev) => prev.filter((d) => d !== id));
  }, []);

  const clearDocuments = useCallback(() => setSelectedDocumentIds([]), []);

  const clearAll = useCallback(() => {
    setSelectedCategories([]);
    setSelectedDocumentIds([]);
  }, []);

  const scopeDescription = (() => {
    const parts: string[] = [];
    if (selectedCategories.length > 0) {
      parts.push(`${selectedCategories.length} categories`);
    }
    if (selectedDocumentIds.length > 0) {
      parts.push(`${selectedDocumentIds.length} documents`);
    }
    return parts.length > 0 ? parts.join(", ") : "All documents";
  })();

  return {
    selectedCategories,
    selectedDocumentIds,
    toggleCategory,
    clearCategories,
    addDocumentId,
    removeDocumentId,
    clearDocuments,
    clearAll,
    scopeDescription,
  };
}
