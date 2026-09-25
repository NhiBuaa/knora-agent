import React, { type HTMLAttributes, type ReactNode } from "react";
import "../../styles/controls.css";

export type NoticeProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  kind: "error" | "warning" | "success" | "info";
  title: ReactNode;
};

export function Notice({ kind, title, children, className = "", ...props }: NoticeProps) {
  return <div {...props} role={kind === "error" ? "alert" : undefined} data-kind={kind}
    className={`kn-notice ${className}`.trim()}>
    <strong className="kn-notice__title">{title}</strong>
    {children && <div>{children}</div>}
  </div>;
}
