"use client";

import { useState } from "react";
import { fullImageUrl, blurImageUrl } from "@/lib/api-client";

interface DocumentViewerProps {
  documentId: string;
  title: string;
}

export function DocumentViewer({ documentId, title }: DocumentViewerProps) {
  const [imgSrc, setImgSrc] = useState(blurImageUrl(documentId));
  const [loaded, setLoaded] = useState(false);

  return (
    <div className="flex flex-col items-center gap-4 p-4">
      <h2 className="text-lg font-medium">{title}</h2>
      <div className="relative w-full max-w-4xl bg-muted rounded-lg overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgSrc}
          alt={title}
          className={`w-full transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-70"}`}
          onLoad={() => {
            if (!loaded) {
              setLoaded(true);
              const full = fullImageUrl(documentId);
              const img = new window.Image();
              img.onload = () => setImgSrc(full);
              img.src = full;
            }
          }}
        />
      </div>
    </div>
  );
}
