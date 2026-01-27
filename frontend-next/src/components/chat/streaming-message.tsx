"use client";

interface StreamingMessageProps {
  content: string;
  streaming: boolean;
}

export function StreamingMessage({ content, streaming }: StreamingMessageProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <div dangerouslySetInnerHTML={{ __html: content }} />
      {streaming && (
        <span className="inline-block h-4 w-1 animate-pulse bg-foreground ml-0.5" />
      )}
    </div>
  );
}
