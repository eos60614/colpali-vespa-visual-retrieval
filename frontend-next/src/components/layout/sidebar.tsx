"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { useSessionStore } from "@/stores/session-store";

export function Sidebar({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const recentQueries = useSessionStore((s) => s.recentQueries);
  const projectQueries = recentQueries
    .filter((q) => q.projectId === projectId)
    .slice(0, 5);

  const base = `/projects/${projectId}`;
  const links = [
    { href: `${base}/search`, label: "Search", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
    { href: `${base}/documents`, label: "Documents", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
    { href: `${base}/upload`, label: "Upload", icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" },
  ];

  return (
    <aside className="w-56 border-r bg-muted/30 hidden lg:block">
      <nav className="flex flex-col gap-1 p-3">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              pathname === link.href
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d={link.icon} />
            </svg>
            {link.label}
          </Link>
        ))}
      </nav>

      {projectQueries.length > 0 && (
        <div className="border-t p-3">
          <h4 className="text-xs font-medium text-muted-foreground mb-2 px-3">Recent Searches</h4>
          <div className="flex flex-col gap-0.5">
            {projectQueries.map((q, i) => (
              <Link
                key={i}
                href={`${base}/search?q=${encodeURIComponent(q.query)}`}
                className="truncate px-3 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {q.query}
              </Link>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
