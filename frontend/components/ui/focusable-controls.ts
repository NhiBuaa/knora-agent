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
      isDisplayed(element) &&
      getComputedStyle(element).visibility !== "hidden",
  );
}

function isDisplayed(element: HTMLElement): boolean {
  // A descendant's computed display does not reflect a display:none ancestor.
  // Check ancestry directly so the same rule works without a layout engine in jsdom.
  for (
    let current: HTMLElement | null = element;
    current;
    current = current.parentElement
  ) {
    if (getComputedStyle(current).display === "none") return false;
  }
  return true;
}
