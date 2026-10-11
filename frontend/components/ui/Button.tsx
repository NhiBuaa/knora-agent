import React, { type ButtonHTMLAttributes } from "react";
import { LeafLoading } from "./LeafLoading";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "signature" | "ghost";
  loading?: boolean;
};

const variants = {
  primary:
    "border-transparent bg-action text-action-foreground hover:enabled:bg-action-hover active:enabled:bg-action-active",
  secondary:
    "border-control-border bg-surface text-text-primary hover:enabled:bg-surface-subtle",
  signature: "border-transparent bg-signature text-signature-foreground",
  ghost:
    "border-transparent bg-transparent text-text-primary hover:enabled:bg-surface-subtle",
} as const;

export function Button({
  variant = "primary",
  type = "button",
  className = "",
  loading = false,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      data-variant={variant}
      className={`kn-button inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-semibold ${variants[variant]} ${className}`.trim()}
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && <LeafLoading compact label="Working" />}
      {children}
    </button>
  );
}
