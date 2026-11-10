import * as React from "react";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  className,
  children,
  ...props
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 border-b border-card-border pb-5 md:flex-row md:items-center md:justify-between",
        className,
      )}
      {...props}
    >
      <div className="space-y-1.5">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav
            aria-label="Breadcrumb"
            className="flex items-center space-x-1.5 text-xs text-ink-muted"
          >
            {breadcrumbs.map((item, index) => {
              const isLast = index === breadcrumbs.length - 1;
              return (
                <React.Fragment key={item.label}>
                  {index > 0 && <ChevronRight className="h-3 w-3 shrink-0 opacity-40" />}
                  {item.href && !isLast ? (
                    <Link to={item.href} className="transition-colors hover:text-ink">
                      {item.label}
                    </Link>
                  ) : (
                    <span className={cn(isLast && "font-semibold text-ink")}>
                      {item.label}
                    </span>
                  )}
                </React.Fragment>
              );
            })}
          </nav>
        )}
        <h1 className="text-[27px] font-bold leading-[1.15] tracking-[-0.02em] text-ink sm:text-[30px]">
          {title}
        </h1>
        {description && <p className="text-sm text-ink-muted">{description}</p>}
      </div>

      {(actions || children) && (
        <div className="flex shrink-0 items-center gap-2.5">{actions || children}</div>
      )}
    </div>
  );
}
