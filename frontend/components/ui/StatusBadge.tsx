import React, { type HTMLAttributes } from "react";

export type StatusBadgeProps = HTMLAttributes<HTMLSpanElement> & {
  kind: "success" | "warning" | "error" | "info";
};

const icons = { success: "✓", warning: "!", error: "×", info: "i" } as const;

export function StatusBadge({
  kind,
  children,
  className = "",
  ...props
}: StatusBadgeProps) {
  return (
    <span
      {...props}
      data-kind={kind}
      className={`kn-status-badge inline-flex items-center rounded-full text-xs ${className}`.trim()}
    >
      <span aria-hidden="true" className="kn-status-badge__icon">
        {icons[kind]}
      </span>
      <span>{children}</span>
    </span>
  );
}
