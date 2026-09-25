import React, { type HTMLAttributes, type ReactNode } from "react";
import "../../styles/controls.css";

export type NoticeProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  kind: "error" | "warning" | "success" | "info";
  title: ReactNode;
};

const kindLabels = { error: "Error", warning: "Warning", success: "Success", info: "Information" } as const;

export function Notice({ kind, title, children, className = "", ...props }: NoticeProps) {
  return <div {...props} role={kind === "error" ? "alert" : undefined} data-kind={kind}
    className={`kn-notice ${className}`.trim()}>
    <span className="kn-notice__kind">{kindLabels[kind]}</span>
    <strong className="kn-notice__title">{title}</strong>
    {children && <div>{children}</div>}
  </div>;
}
