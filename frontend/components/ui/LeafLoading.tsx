import React from "react";
import "./leaf-loading.css";

export function LeafLoading({
  label = "Loading",
  compact = false,
  className = "",
}: {
  label?: string;
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`kn-leaf-loading ${compact ? "kn-leaf-loading--compact" : ""} ${className}`}
    >
      <span className="kn-leaf-loading__art" aria-hidden="true">
        <svg viewBox="0 0 18 18" fill="none">
          <path
            d="M8.68 16.15C5.17 15.69 2.55 13.63 1.84 10.46C1.53 9.08 1.58 7.63 1.92 6.23C3.39 6.22 4.82 6.59 6.03 7.35C8.22 8.73 9.28 11.27 8.68 16.15ZM9.16 14.75C9.14 10.72 10.28 7.37 12.59 4.93C13.61 3.85 14.84 3.02 16.21 2.46C16.56 4.01 16.55 5.59 16.16 7.08C15.31 10.32 12.99 12.88 9.16 14.75Z"
            fill="currentColor"
          />
          <path
            d="M8.35 16.05C8.78 12.55 9.91 9.34 11.86 6.65"
            stroke="currentColor"
            strokeWidth="1.35"
            strokeLinecap="round"
          />
          <path
            d="M8.18 13.56C6.71 11.2 5.1 9.66 3.36 8.86M10.06 11.56C11.18 8.84 12.76 6.66 14.75 5.02"
            stroke="var(--surface)"
            strokeWidth=".95"
            strokeLinecap="round"
          />
        </svg>
      </span>
      <span className="sr-only">{label}</span>
    </span>
  );
}
