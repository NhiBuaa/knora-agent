"use client";

import React from "react";
import Link, { useLinkStatus } from "next/link";

export function NavigationLink({
  children,
  ...props
}: React.ComponentProps<typeof Link>) {
  return (
    <Link {...props}>
      <NavigationLabel>{children}</NavigationLabel>
    </Link>
  );
}

function NavigationLabel({ children }: { children: React.ReactNode }) {
  const { pending } = useLinkStatus();
  return (
    <span
      className="kn-product-nav-label"
      aria-busy={pending || undefined}
      data-pending={pending ? "true" : undefined}
    >
      {children}
    </span>
  );
}
