"use client";

import { useEffect } from "react";
import { useChat } from "@/lib/hooks/use-chat";
import { StreamingMessage } from "./streaming-message";

interface ChatPanelProps {
  queryId: string | null;
  query: string;
  docIds: string[];
}

export function ChatPanel({ queryId, query, docIds }: ChatPanelProps) {
  const { content, streaming, error, start } = useChat();

  useEffect(() => {
    if (queryId && query && docIds.length > 0) {
      start(queryId, query, docIds);
    }
  }, [queryId, query, docIds, start]);

  if (!queryId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm p-6">
        Search to get an AI-generated answer.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium text-sm">AI Answer</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {error ? (
          <p className="text-destructive text-sm">{error}</p>
        ) : content ? (
          <StreamingMessage content={content} streaming={streaming} />
        ) : (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Generating response...
          </div>
        )}
      </div>
    </div>
  );
}
