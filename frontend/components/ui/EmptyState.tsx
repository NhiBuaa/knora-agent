import React, { type HTMLAttributes, type ReactNode } from "react";
import "../../styles/controls.css";

export type EmptyStateProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ title, description, action, className = "", ...props }: EmptyStateProps) {
  return <div {...props} className={`kn-empty-state ${className}`.trim()}>
    <h2>{title}</h2>
    {description && <p>{description}</p>}
    {action && <div className="kn-empty-state__action">{action}</div>}
  </div>;
}
