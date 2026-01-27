"use client";

import { useState, useRef, useEffect } from "react";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils/cn";

interface ProjectPickerProps {
  projects: Project[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ProjectPicker({ projects, selectedId, onSelect }: ProjectPickerProps) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const selected = projects.find((p) => p.id === selectedId);
  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(filter.toLowerCase()) ||
    p.project_number.toLowerCase().includes(filter.toLowerCase())
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent transition-colors min-w-[220px]"
      >
        <span className="truncate">
          {selected
            ? `${selected.project_number ? selected.project_number + " - " : ""}${selected.name}`
            : "Select project..."}
        </span>
        <svg
          className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-180")}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-80 rounded-md border bg-popover shadow-lg z-50">
          <div className="p-2">
            <input
              type="text"
              placeholder="Search projects..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full rounded-md border px-2 py-1 text-sm bg-background"
              autoFocus
            />
          </div>
          <div className="max-h-72 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">No projects found</div>
            ) : (
              filtered.map((project) => (
                <button
                  key={project.id}
                  onClick={() => {
                    onSelect(project.id);
                    setOpen(false);
                    setFilter("");
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 hover:bg-accent transition-colors",
                    project.id === selectedId && "bg-accent font-medium"
                  )}
                >
                  <div className="text-sm font-medium">
                    {project.project_number ? `${project.project_number} - ` : ""}
                    {project.name}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {project.document_count} documents
                    {project.city ? ` \u00b7 ${project.city}${project.state_code ? `, ${project.state_code}` : ""}` : ""}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
