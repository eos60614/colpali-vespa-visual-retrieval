import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  glow?: boolean;
  onClick?: () => void;
}

export function Card({ children, className, hover, glow, onClick }: CardProps) {
  return (
    <div
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={onClick ? (e) => e.key === "Enter" && onClick() : undefined}
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border-primary)]",
        "bg-[var(--bg-elevated)]",
        "transition-all duration-[var(--transition-base)]",
        hover && "hover:border-[var(--border-secondary)] hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5 cursor-pointer",
        glow && "glow-accent",
        onClick && "cursor-pointer",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("px-4 pt-4 pb-2", className)}>
      {children}
    </div>
  );
}

export function CardContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("px-4 pb-4", className)}>
      {children}
    </div>
  );
}
