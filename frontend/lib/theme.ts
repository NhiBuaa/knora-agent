export type ThemePreference = "system" | "light" | "dark";

export const THEME_COOKIE_NAME = "knora_theme";

export function readThemePreference(
  value: string | undefined,
): ThemePreference {
  return value === "light" || value === "dark" ? value : "system";
}

export function resolveTheme(
  preference: ThemePreference,
  dark: boolean,
): "light" | "dark" {
  return preference === "system" ? (dark ? "dark" : "light") : preference;
}
