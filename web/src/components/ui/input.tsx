"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  suffix?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, suffix, ...props }, ref) => {
    return (
      <div className="relative flex items-center">
        {icon && (
          <div className="absolute left-3 text-[var(--text-tertiary)] pointer-events-none">
            {icon}
          </div>
        )}
        <input
          ref={ref}
          className={cn(
            "w-full h-10 rounded-[var(--radius-md)] border border-[var(--border-primary)]",
            "bg-[var(--bg-elevated)] text-[var(--text-primary)] text-sm",
            "placeholder:text-[var(--text-tertiary)]",
            "transition-all duration-[var(--transition-fast)]",
            "focus:outline-none focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-glow)]",
            "hover:border-[var(--border-secondary)]",
            icon ? "pl-10" : "pl-3",
            suffix ? "pr-10" : "pr-3",
            className
          )}
          {...props}
        />
        {suffix && (
          <div className="absolute right-3 text-[var(--text-tertiary)]">
            {suffix}
          </div>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
