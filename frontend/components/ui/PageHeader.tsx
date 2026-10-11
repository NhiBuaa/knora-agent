import React, { type HTMLAttributes, type ReactNode } from "react";

export type PageHeaderProps = Omit<HTMLAttributes<HTMLElement>, "title"> & {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
};

export function PageHeader({
  title,
  description,
  actions,
  className = "",
  ...props
}: PageHeaderProps) {
  return (
    <header
      {...props}
      className={`kn-page-header flex flex-wrap items-start justify-between gap-4 ${className}`.trim()}
    >
      <div>
        <h1>{title}</h1>
        {description && (
          <p className="text-sm text-text-muted">{description}</p>
        )}
      </div>
      {actions && <div className="kn-page-header__actions">{actions}</div>}
    </header>
  );
}
