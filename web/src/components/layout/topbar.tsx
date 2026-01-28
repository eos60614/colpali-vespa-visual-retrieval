"use client";

import {
  Moon,
  Sun,
  Upload,
  Settings,
  HelpCircle,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { Project } from "@/types";

interface TopBarProps {
  project: Project | null;
  isDark: boolean;
  onToggleTheme: () => void;
}

export function TopBar({ project, isDark, onToggleTheme }: TopBarProps) {
  return (
    <header className="h-14 border-b border-[var(--border-primary)] bg-[var(--bg-secondary)] flex items-center justify-between px-4 shrink-0">
      {/* Left: Project context */}
      <div className="flex items-center gap-3">
        {project ? (
          <>
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: project.color }}
              />
              <h1 className="text-sm font-semibold text-[var(--text-primary)]">
                {project.name}
              </h1>
            </div>
            <span className="text-[11px] text-[var(--text-tertiary)] bg-[var(--bg-tertiary)] px-2 py-0.5 rounded-[var(--radius-full)]">
              {project.documentCount.toLocaleString()} documents
            </span>
          </>
        ) : (
          <span className="text-sm text-[var(--text-tertiary)]">
            Select a project to begin
          </span>
        )}
      </div>

      {/* Center: Connection status */}
      <div className="hidden md:flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--radius-full)] bg-[var(--success-bg)] border border-transparent">
          <Zap className="h-3 w-3 text-[var(--success)]" />
          <span className="text-[11px] font-medium text-[var(--success)]">
            Vespa Connected
          </span>
          <div className="status-dot active ml-0.5" />
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        <Tooltip content="Upload documents">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Upload className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip content={isDark ? "Light mode" : "Dark mode"}>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggleTheme}>
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </Tooltip>
        <Tooltip content="Settings">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Settings className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Help">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <HelpCircle className="h-4 w-4" />
          </Button>
        </Tooltip>

        {/* User avatar */}
        <div className={cn(
          "w-8 h-8 rounded-full ml-2 flex items-center justify-center text-xs font-semibold",
          "bg-gradient-to-br from-[#d97756] to-[#b85636] text-white",
          "ring-2 ring-[var(--bg-secondary)]"
        )}>
          JD
        </div>
      </div>
    </header>
  );
}
