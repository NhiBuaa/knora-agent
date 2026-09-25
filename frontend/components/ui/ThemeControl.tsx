"use client";

import React, { useState } from "react";
import {
  readThemePreference,
  THEME_COOKIE_NAME,
  type ThemePreference,
} from "@/lib/theme";

export function ThemeControl({
  initialPreference,
}: {
  initialPreference: ThemePreference;
}) {
  const [preference, setPreference] = useState(initialPreference);

  function selectTheme(next: ThemePreference) {
    setPreference(next);
    if (next === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.dataset.theme = next;
    }
    document.cookie = `${THEME_COOKIE_NAME}=${next}; Path=/; SameSite=Lax; Max-Age=31536000`;
  }

  return (
    <label>
      Appearance{" "}
      <select
        value={preference}
        onChange={(event) =>
          selectTheme(readThemePreference(event.target.value))
        }
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
