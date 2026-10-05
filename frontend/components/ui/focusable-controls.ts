// Private focus seam shared by the menu and modal implementations.
export function focusableControls(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      "a[href], button, input, select, textarea, [tabindex]",
    ),
  ).filter(
    (element) =>
      !element.matches(
        ':disabled, [aria-disabled="true"], [hidden], [tabindex="-1"]',
      ) &&
      !element.closest("[hidden], [inert]") &&
      getComputedStyle(element).display !== "none" &&
      getComputedStyle(element).visibility !== "hidden",
  );
}
