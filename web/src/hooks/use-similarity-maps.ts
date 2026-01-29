"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { correlationHeaders, getLogger } from "@/lib/logger";
import type { TokenInfo, SimilarityMapState } from "@/types";

const logger = getLogger("use-similarity-maps");

interface UseSimilarityMapsOptions {
  queryId: string | null;
  resultIndex: number;
  tokenMap: TokenInfo[];
  enabled?: boolean;
}

interface UseSimilarityMapsReturn {
  simMaps: Map<number, SimilarityMapState>;
  activeTokenIdx: number | null;
  setActiveTokenIdx: (idx: number | null) => void;
  getSimMap: (tokenIdx: number) => SimilarityMapState | undefined;
  isLoading: boolean;
}

const POLL_INTERVAL = 500; // ms

export function useSimilarityMaps({
  queryId,
  resultIndex,
  tokenMap,
  enabled = true,
}: UseSimilarityMapsOptions): UseSimilarityMapsReturn {
  const [simMaps, setSimMaps] = useState<Map<number, SimilarityMapState>>(new Map());
  const [activeTokenIdx, setActiveTokenIdx] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize sim map states when tokenMap changes
  useEffect(() => {
    if (!queryId || tokenMap.length === 0) {
      setSimMaps(new Map());
      return;
    }

    const initialMaps = new Map<number, SimilarityMapState>();
    tokenMap.forEach(({ tokenIdx }) => {
      initialMaps.set(tokenIdx, {
        queryId,
        resultIndex,
        tokenIdx,
        ready: false,
        loading: false,
      });
    });
    setSimMaps(initialMaps);
  }, [queryId, resultIndex, tokenMap]);

  // Poll for sim maps that are not ready
  const pollSimMaps = useCallback(async () => {
    if (!queryId || !enabled) return;

    const pendingMaps = Array.from(simMaps.entries()).filter(
      ([, state]) => !state.ready && !state.loading
    );

    if (pendingMaps.length === 0) return;

    setIsLoading(true);

    // Mark maps as loading
    setSimMaps((prev) => {
      const next = new Map(prev);
      pendingMaps.forEach(([tokenIdx, state]) => {
        next.set(tokenIdx, { ...state, loading: true });
      });
      return next;
    });

    // Fetch each pending map
    await Promise.all(
      pendingMaps.map(async ([tokenIdx, state]) => {
        try {
          const params = new URLSearchParams({
            query_id: queryId,
            idx: String(resultIndex),
            token_idx: String(tokenIdx),
          });

          const res = await fetch(`/api/sim-map?${params}`, {
            headers: { ...correlationHeaders() },
          });

          if (!res.ok) {
            throw new Error(`Failed to fetch sim map: ${res.status}`);
          }

          const data = await res.json();

          setSimMaps((prev) => {
            const next = new Map(prev);
            next.set(tokenIdx, {
              ...state,
              ready: data.ready,
              image: data.image,
              loading: false,
            });
            return next;
          });
        } catch (error) {
          logger.error("Failed to fetch sim map", { tokenIdx, error });
          setSimMaps((prev) => {
            const next = new Map(prev);
            next.set(tokenIdx, {
              ...state,
              loading: false,
            });
            return next;
          });
        }
      })
    );

    setIsLoading(false);
  }, [queryId, resultIndex, simMaps, enabled]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled || !queryId) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    // Check if all maps are ready
    const allReady = Array.from(simMaps.values()).every((state) => state.ready);
    if (allReady && simMaps.size > 0) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    // Start polling
    pollIntervalRef.current = setInterval(pollSimMaps, POLL_INTERVAL);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [enabled, queryId, simMaps, pollSimMaps]);

  // Initial poll
  useEffect(() => {
    if (enabled && queryId && simMaps.size > 0) {
      pollSimMaps();
    }
  }, [enabled, queryId, simMaps.size, pollSimMaps]);

  const getSimMap = useCallback(
    (tokenIdx: number) => simMaps.get(tokenIdx),
    [simMaps]
  );

  return {
    simMaps,
    activeTokenIdx,
    setActiveTokenIdx,
    getSimMap,
    isLoading,
  };
}
