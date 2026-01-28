import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "accent" | "success" | "warning" | "info" | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  dot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default:
    "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border-[var(--border-primary)]",
  accent:
    "bg-[var(--accent-glow)] text-[var(--accent-primary)] border-[var(--border-accent)]",
  success:
    "bg-[var(--success-bg)] text-[var(--success)] border-transparent",
  warning:
    "bg-[var(--warning-bg)] text-[var(--warning)] border-transparent",
  info:
    "bg-[var(--info-bg)] text-[var(--info)] border-transparent",
  muted:
    "bg-transparent text-[var(--text-tertiary)] border-[var(--border-primary)]",
};

export function Badge({ children, variant = "default", dot, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-[var(--radius-full)] border",
        "transition-colors duration-[var(--transition-fast)]",
        variantStyles[variant],
        className
      )}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full bg-current opacity-80"
        />
      )}
      {children}
    </span>
  );
}
