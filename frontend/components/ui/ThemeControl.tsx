"use client";

import React, { useState } from "react";
import { THEME_COOKIE_NAME, type ThemePreference } from "@/lib/theme";

export function ThemeControl({
  initialPreference,
  onPreferenceChange,
}: {
  initialPreference: ThemePreference;
  onPreferenceChange?: (preference: ThemePreference) => void;
}) {
  const [preference, setPreference] = useState(initialPreference);

  function selectTheme(next: ThemePreference) {
    setPreference(next);
    onPreferenceChange?.(next);
    if (next === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.dataset.theme = next;
    }
    document.cookie = `${THEME_COOKIE_NAME}=${next}; Path=/; SameSite=Lax; Max-Age=31536000`;
  }

  return (
    <fieldset className="kn-theme-choices">
      <legend>Appearance</legend>
      <p>Choose how Knora looks on this device.</p>
      <div className="kn-theme-options">
        {(["light", "dark", "system"] as const).map((value) => (
          <label
            key={value}
            className="kn-theme-option"
            data-selected={preference === value}
          >
            <input
              type="radio"
              name="knora-appearance"
              value={value}
              checked={preference === value}
              onChange={() => selectTheme(value)}
            />
            <span
              className={`kn-theme-preview kn-theme-preview--${value}`}
              aria-hidden="true"
            >
              <span />
              <span />
              <span />
            </span>
            <span>
              {value === "light"
                ? "Light"
                : value === "dark"
                  ? "Dark"
                  : "System"}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
