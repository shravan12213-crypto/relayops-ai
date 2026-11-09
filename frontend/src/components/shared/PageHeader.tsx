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
        "flex flex-col gap-4 border-b border-border/60 pb-5 md:flex-row md:items-center md:justify-between",
        className,
      )}
      {...props}
    >
      <div className="space-y-1.5">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav
            aria-label="Breadcrumb"
            className="flex items-center space-x-1.5 text-xs text-muted-foreground"
          >
            {breadcrumbs.map((item, index) => {
              const isLast = index === breadcrumbs.length - 1;
              return (
                <React.Fragment key={item.label}>
                  {index > 0 && <ChevronRight className="h-3 w-3 shrink-0 opacity-40" />}
                  {item.href && !isLast ? (
                    <Link to={item.href} className="transition-colors hover:text-foreground">
                      {item.label}
                    </Link>
                  ) : (
                    <span className={cn(isLast && "font-medium text-foreground")}>
                      {item.label}
                    </span>
                  )}
                </React.Fragment>
              );
            })}
          </nav>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>

      {(actions || children) && (
        <div className="flex shrink-0 items-center gap-2.5">{actions || children}</div>
      )}
    </div>
  );
}
