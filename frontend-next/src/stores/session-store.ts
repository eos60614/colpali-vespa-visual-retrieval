import { create } from "zustand";
import { persist } from "zustand/middleware";

interface RecentQuery {
  query: string;
  timestamp: number;
  projectId: string;
}

interface RecentDocument {
  docId: string;
  title: string;
  timestamp: number;
}

interface SessionStore {
  selectedProjectId: string | null;
  categoryFilters: string[];
  selectedDocumentIds: string[];
  recentQueries: RecentQuery[];
  recentDocuments: RecentDocument[];
  setProject: (id: string) => void;
  setCategories: (cats: string[]) => void;
  setDocumentIds: (ids: string[]) => void;
  addRecentQuery: (query: string, projectId: string) => void;
  addRecentDocument: (docId: string, title: string) => void;
}

export const useSessionStore = create<SessionStore>()(
  persist(
    (set) => ({
      selectedProjectId: null,
      categoryFilters: [],
      selectedDocumentIds: [],
      recentQueries: [],
      recentDocuments: [],
      setProject: (id) => set({ selectedProjectId: id }),
      setCategories: (cats) => set({ categoryFilters: cats }),
      setDocumentIds: (ids) => set({ selectedDocumentIds: ids }),
      addRecentQuery: (query, projectId) =>
        set((state) => ({
          recentQueries: [
            { query, timestamp: Date.now(), projectId },
            ...state.recentQueries.filter((q) => q.query !== query).slice(0, 19),
          ],
        })),
      addRecentDocument: (docId, title) =>
        set((state) => ({
          recentDocuments: [
            { docId, title, timestamp: Date.now() },
            ...state.recentDocuments
              .filter((d) => d.docId !== docId)
              .slice(0, 19),
          ],
        })),
    }),
    { name: "copoly-session" }
  )
);
