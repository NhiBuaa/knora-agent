import React, { type HTMLAttributes, type ReactNode } from "react";
import "../../styles/controls.css";

export type NoticeProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  kind: "info" | "warning" | "error" | "system";
  title: ReactNode;
};

const kindLabels = {
  error: "Error",
  warning: "Warning",
  info: "Information",
  system: "In progress",
} as const;

export function Notice({
  kind,
  title,
  children,
  role,
  className = "",
  ...props
}: NoticeProps) {
  return (
    <div
      {...props}
      role={role ?? (kind === "system" ? "status" : undefined)}
      data-kind={kind}
      className={`kn-notice ${className}`.trim()}
    >
      <span className="kn-notice__kind">{kindLabels[kind]}</span>
      <strong className="kn-notice__title">{title}</strong>
      {children && <div>{children}</div>}
    </div>
  );
}
