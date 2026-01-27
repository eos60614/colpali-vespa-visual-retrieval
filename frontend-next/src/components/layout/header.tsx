"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { ProjectPicker } from "./project-picker";
import type { Project } from "@/lib/types";

interface HeaderProps {
  projects: Project[];
  selectedProjectId: string | null;
  onSelectProject: (id: string) => void;
}

export function Header({ projects, selectedProjectId, onSelectProject }: HeaderProps) {
  const pathname = usePathname();
  const projectPath = selectedProjectId ? `/projects/${selectedProjectId}` : null;

  const navLinks = projectPath
    ? [
        { href: `${projectPath}/search`, label: "Search" },
        { href: `${projectPath}/documents`, label: "Documents" },
        { href: `${projectPath}/upload`, label: "Upload" },
      ]
    : [];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center px-4 gap-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
          CoPoly
        </Link>

        <ProjectPicker
          projects={projects}
          selectedId={selectedProjectId}
          onSelect={onSelectProject}
        />

        <nav className="flex items-center gap-1 ml-auto">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "px-3 py-2 text-sm rounded-md transition-colors",
                pathname === link.href
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
