"use client";

import { useState, useCallback } from "react";
import type { Project, DocumentCategory } from "@/types";

const DEMO_PROJECTS: Project[] = [
  {
    id: "proj-harbor-tower",
    name: "Harbor Tower Mixed-Use",
    description: "32-story mixed-use development at 450 Harbor Blvd",
    documentCount: 1247,
    lastAccessedAt: "2025-01-15T10:30:00Z",
    createdAt: "2024-06-01T00:00:00Z",
    categories: [
      { category: "drawing", count: 523 },
      { category: "rfi", count: 189 },
      { category: "submittal", count: 312 },
      { category: "spec", count: 97 },
      { category: "change_order", count: 43 },
      { category: "correspondence", count: 83 },
    ],
    color: "#3b82f6",
  },
  {
    id: "proj-westfield-campus",
    name: "Westfield Corporate Campus",
    description: "Phase 2 expansion — Building C and parking structure",
    documentCount: 834,
    lastAccessedAt: "2025-01-14T16:45:00Z",
    createdAt: "2024-09-15T00:00:00Z",
    categories: [
      { category: "drawing", count: 401 },
      { category: "rfi", count: 112 },
      { category: "submittal", count: 198 },
      { category: "spec", count: 67 },
      { category: "change_order", count: 21 },
      { category: "photo", count: 35 },
    ],
    color: "#8b5cf6",
  },
  {
    id: "proj-meridian-hospital",
    name: "Meridian Medical Center",
    description: "Seismic retrofit and ICU expansion wing",
    documentCount: 2156,
    lastAccessedAt: "2025-01-13T09:15:00Z",
    createdAt: "2024-03-10T00:00:00Z",
    categories: [
      { category: "drawing", count: 987 },
      { category: "rfi", count: 345 },
      { category: "submittal", count: 456 },
      { category: "spec", count: 201 },
      { category: "change_order", count: 89 },
      { category: "report", count: 78 },
    ],
    color: "#10b981",
  },
  {
    id: "proj-bayview-school",
    name: "Bayview Elementary School",
    description: "New K-5 school with multipurpose gymnasium",
    documentCount: 612,
    lastAccessedAt: "2025-01-10T14:00:00Z",
    createdAt: "2024-11-01T00:00:00Z",
    categories: [
      { category: "drawing", count: 278 },
      { category: "rfi", count: 89 },
      { category: "submittal", count: 134 },
      { category: "spec", count: 56 },
      { category: "change_order", count: 12 },
      { category: "correspondence", count: 43 },
    ],
    color: "#f59e0b",
  },
];

export function useProject() {
  const [projects] = useState<Project[]>(DEMO_PROJECTS);
  const [activeProject, setActiveProject] = useState<Project | null>(DEMO_PROJECTS[0]);

  const selectProject = useCallback((projectId: string) => {
    const project = DEMO_PROJECTS.find((p) => p.id === projectId);
    if (project) setActiveProject(project);
  }, []);

  return { projects, activeProject, selectProject };
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
