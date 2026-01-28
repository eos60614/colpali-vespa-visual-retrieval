"use client";

import { useState } from "react";
import {
  FolderOpen,
  Search,
  Clock,
  ChevronRight,
  Plus,
  Building2,
  PanelLeftClose,
  PanelLeft,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDate, truncate, getInitials, pluralize } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import type { Project, RecentQuery } from "@/types";

interface SidebarProps {
  projects: Project[];
  activeProject: Project | null;
  onSelectProject: (id: string) => void;
  recentQueries: RecentQuery[];
  onSelectQuery: (query: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({
  projects,
  activeProject,
  onSelectProject,
  recentQueries,
  onSelectQuery,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [projectFilter, setProjectFilter] = useState("");

  const filteredProjects = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(projectFilter.toLowerCase()) ||
      p.description?.toLowerCase().includes(projectFilter.toLowerCase())
  );

  if (collapsed) {
    return (
      <aside className="w-[var(--sidebar-collapsed)] h-full border-r border-[var(--border-primary)] bg-[var(--bg-secondary)] flex flex-col items-center py-3 gap-1">
        <Tooltip content="Expand sidebar" side="right">
          <Button variant="ghost" size="icon" onClick={onToggleCollapse}>
            <PanelLeft className="h-4 w-4" />
          </Button>
        </Tooltip>

        <div className="w-8 h-px bg-[var(--border-primary)] my-2" />

        {projects.map((project) => (
          <Tooltip key={project.id} content={project.name} side="right">
            <button
              onClick={() => onSelectProject(project.id)}
              className={cn(
                "w-9 h-9 rounded-[var(--radius-md)] flex items-center justify-center text-xs font-semibold",
                "transition-all duration-[var(--transition-fast)] cursor-pointer",
                activeProject?.id === project.id
                  ? "bg-[var(--accent-glow)] text-[var(--accent-primary)] ring-1 ring-[var(--border-accent)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
              )}
              style={
                activeProject?.id === project.id
                  ? {}
                  : { color: project.color }
              }
            >
              {getInitials(project.name)}
            </button>
          </Tooltip>
        ))}
      </aside>
    );
  }

  return (
    <aside className="w-[var(--sidebar-width)] h-full border-r border-[var(--border-primary)] bg-[var(--bg-secondary)] flex flex-col animate-slide-in-left">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-14 border-b border-[var(--border-primary)]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-[var(--radius-md)] bg-gradient-to-br from-[#d97756] to-[#b85636] flex items-center justify-center">
            <Layers className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="font-semibold text-sm tracking-tight">KI55</span>
          <span className="text-[10px] text-[var(--text-tertiary)] font-mono bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded">
            2025
          </span>
        </div>
        <Tooltip content="Collapse sidebar" side="right">
          <Button variant="ghost" size="icon" onClick={onToggleCollapse} className="h-7 w-7">
            <PanelLeftClose className="h-3.5 w-3.5" />
          </Button>
        </Tooltip>
      </div>

      {/* Project Search */}
      <div className="px-3 pt-3 pb-2">
        <Input
          placeholder="Find project..."
          icon={<Search className="h-3.5 w-3.5" />}
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="h-8 text-xs"
        />
      </div>

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="flex items-center justify-between px-2 py-2">
          <span className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            Projects
          </span>
          <Tooltip content="New project" side="right">
            <button className="h-5 w-5 rounded flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer">
              <Plus className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        </div>

        <div className="space-y-0.5 stagger-children">
          {filteredProjects.map((project) => (
            <ProjectItem
              key={project.id}
              project={project}
              isActive={activeProject?.id === project.id}
              onClick={() => onSelectProject(project.id)}
            />
          ))}
        </div>

        {filteredProjects.length === 0 && (
          <div className="text-center py-6 text-[var(--text-tertiary)] text-xs">
            No projects match &ldquo;{projectFilter}&rdquo;
          </div>
        )}
      </div>

      {/* Recent Queries */}
      <div className="border-t border-[var(--border-primary)] px-2 py-2">
        <div className="flex items-center gap-1.5 px-2 py-1.5">
          <Clock className="h-3 w-3 text-[var(--text-tertiary)]" />
          <span className="text-[11px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            Recent
          </span>
        </div>
        <div className="space-y-0.5 max-h-40 overflow-y-auto">
          {recentQueries.slice(0, 5).map((rq) => (
            <button
              key={rq.id}
              onClick={() => onSelectQuery(rq.query)}
              className={cn(
                "w-full text-left px-2.5 py-1.5 rounded-[var(--radius-sm)] text-xs",
                "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                "hover:bg-[var(--bg-tertiary)] transition-colors",
                "truncate block cursor-pointer"
              )}
              title={rq.query}
            >
              {truncate(rq.query, 40)}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}

function ProjectItem({
  project,
  isActive,
  onClick,
}: {
  project: Project;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left px-2.5 py-2 rounded-[var(--radius-md)] group",
        "transition-all duration-[var(--transition-fast)] cursor-pointer",
        "active-indicator",
        isActive
          ? "bg-[var(--bg-elevated)] shadow-[var(--shadow-sm)] active"
          : "hover:bg-[var(--bg-tertiary)]"
      )}
    >
      <div className="flex items-center gap-2.5">
        <div
          className={cn(
            "w-8 h-8 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0",
            "transition-colors",
            isActive
              ? "bg-[var(--accent-glow)]"
              : "bg-[var(--bg-tertiary)] group-hover:bg-[var(--bg-secondary)]"
          )}
        >
          <Building2
            className="h-3.5 w-3.5"
            style={{ color: project.color }}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span
              className={cn(
                "text-sm font-medium truncate",
                isActive ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
              )}
            >
              {project.name}
            </span>
            <ChevronRight
              className={cn(
                "h-3 w-3 shrink-0 transition-all",
                isActive
                  ? "opacity-100 text-[var(--accent-primary)]"
                  : "opacity-0 group-hover:opacity-50 text-[var(--text-tertiary)]"
              )}
            />
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <FolderOpen className="h-3 w-3 text-[var(--text-tertiary)]" />
            <span className="text-[11px] text-[var(--text-tertiary)]">
              {project.documentCount.toLocaleString()} {pluralize(project.documentCount, "doc")}
            </span>
            <span className="text-[var(--text-tertiary)]">&middot;</span>
            <span className="text-[11px] text-[var(--text-tertiary)]">
              {formatDate(project.lastAccessedAt)}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}
