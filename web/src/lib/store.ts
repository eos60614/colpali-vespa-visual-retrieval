import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { RecentQuery } from "@/types";

interface AppState {
  // Recent queries (max 20)
  recentQueries: RecentQuery[];
  addRecentQuery: (query: RecentQuery) => void;
  clearRecentQueries: () => void;

  // Selected project
  selectedProjectId: string;
  setSelectedProjectId: (id: string) => void;

  // Ranking preference
  ranking: "hybrid" | "colpali" | "bm25";
  setRanking: (ranking: "hybrid" | "colpali" | "bm25") => void;

  // Theme
  isDark: boolean;
  toggleTheme: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      recentQueries: [],
      addRecentQuery: (query) =>
        set((state) => {
          const filtered = state.recentQueries.filter(
            (q) => q.query !== query.query
          );
          return {
            recentQueries: [query, ...filtered].slice(0, 20),
          };
        }),
      clearRecentQueries: () => set({ recentQueries: [] }),

      selectedProjectId: "proj-harbor-tower",
      setSelectedProjectId: (id) => set({ selectedProjectId: id }),

      ranking: "hybrid",
      setRanking: (ranking) => set({ ranking }),

      isDark: true,
      toggleTheme: () => set((state) => ({ isDark: !state.isDark })),
    }),
    {
      name: "ki55-storage",
      partialize: (state) => ({
        recentQueries: state.recentQueries,
        selectedProjectId: state.selectedProjectId,
        ranking: state.ranking,
        isDark: state.isDark,
      }),
    }
  )
);
