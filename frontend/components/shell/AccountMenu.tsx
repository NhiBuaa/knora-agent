"use client";

import React from "react";
import { ThemeControl } from "@/components/ui/ThemeControl";
import type { ThemePreference } from "@/lib/theme";

export function AccountMenu({
  subject,
  themePreference,
}: {
  subject: string;
  themePreference: ThemePreference;
}) {
  return (
    <div className="account-menu">
      <span>{subject}</span>
      <ThemeControl initialPreference={themePreference} />
      <form action="/api/auth/logout" method="post">
        <button type="submit">Log out</button>
      </form>
    </div>
  );
}
