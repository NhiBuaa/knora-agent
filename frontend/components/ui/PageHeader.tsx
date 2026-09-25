import React, { type HTMLAttributes, type ReactNode } from "react";
import "../../styles/controls.css";

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
    <header {...props} className={`kn-page-header ${className}`.trim()}>
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="kn-page-header__actions">{actions}</div>}
    </header>
  );
}
