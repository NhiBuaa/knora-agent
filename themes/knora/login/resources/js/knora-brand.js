// A distinct asset URL avoids the inherited favicon URL's browser cache.
const icon = document.querySelector('link[rel="icon"]');
if (icon) {
  icon.href = icon.href.replace(/\/favicon\.ico(?:\?.*)?$/, "/knora-leaf.svg");
  icon.type = "image/svg+xml";
}

// Match the app's preference cookie; cookies also work across local dev ports.
let theme = "system";
try {
  const saved = document.cookie.split("; ").find((item) => item.startsWith("knora_theme="))?.split("=")[1];
  if (saved === "light" || saved === "dark") theme = saved;
} catch {
  // The selector still works when browser storage is unavailable.
}
const applyTheme = () => {
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = theme;
};
applyTheme();

document.addEventListener("DOMContentLoaded", () => {
  const choices = document.createElement("fieldset");
  choices.className = "knora-theme-choices";
  const legend = document.createElement("legend");
  legend.className = "knora-visually-hidden";
  legend.textContent = "Appearance";
  choices.append(legend);
  for (const value of ["light", "dark", "system"]) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "knora-appearance";
    input.value = value;
    input.checked = theme === value;
    input.addEventListener("change", () => {
      theme = value;
      applyTheme();
      try {
        document.cookie = `knora_theme=${value}; Path=/; SameSite=Lax; Max-Age=31536000`;
      } catch {
        // Keep the current page usable even when preferences cannot persist.
      }
    });
    const text = document.createElement("span");
    text.textContent = value[0].toUpperCase() + value.slice(1);
    label.append(input, text);
    choices.append(label);
  }
  document.body.append(choices);
});
