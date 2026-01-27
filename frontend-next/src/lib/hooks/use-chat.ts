"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createChatStream } from "@/lib/api-client";

export function useChat() {
  const [content, setContent] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const stop = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setStreaming(false);
  }, []);

  const start = useCallback(
    (queryId: string, query: string, docIds: string[]) => {
      stop();
      setContent("");
      setError(null);
      setStreaming(true);

      const es = createChatStream(queryId, query, docIds);
      esRef.current = es;

      es.addEventListener("token", (e) => {
        try {
          const data = JSON.parse(e.data);
          setContent(data.content);
          if (data.done) {
            es.close();
            esRef.current = null;
            setStreaming(false);
          }
        } catch {
          // ignore parse errors
        }
      });

      es.addEventListener("done", (e) => {
        try {
          const data = JSON.parse(e.data);
          setContent(data.content);
        } catch {
          // ignore
        }
        es.close();
        esRef.current = null;
        setStreaming(false);
      });

      es.onerror = () => {
        setError("Connection lost. Please try again.");
        es.close();
        esRef.current = null;
        setStreaming(false);
      };
    },
    [stop]
  );

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  return { content, streaming, error, start, stop };
}
