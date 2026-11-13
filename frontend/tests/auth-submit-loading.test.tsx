import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { resolve } from "node:path";
import { afterEach, expect, it } from "vitest";

const script = readFileSync(
  resolve(
    process.cwd(),
    "../themes/knora/login/resources/js/knora-login-transition.js",
  ),
  "utf8",
);
const disposers: Array<() => void> = [];

afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
  document.body.innerHTML = "";
});

function setup(id: string) {
  document.body.innerHTML = `<form id="${id}"><button type="submit">Continue</button></form>`;
  const form = document.querySelector("form")!;
  const button = document.querySelector("button")!;
  runInNewContext(script, {
    document,
    setTimeout,
    window: {
      addEventListener: (event: string, listener: EventListener) => {
        window.addEventListener(event, listener);
        disposers.push(() => window.removeEventListener(event, listener));
      },
    },
  });
  return { form, button };
}

it.each(["kc-form-login", "kc-register-form"])(
  "marks %s busy after an accepted submit and resets on pageshow",
  async (id) => {
    const { form, button } = setup(id);
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveClass("knora-loading");
    const duplicate = new Event("submit", { bubbles: true, cancelable: true });
    form.dispatchEvent(duplicate);
    expect(duplicate.defaultPrevented).toBe(true);
    window.dispatchEvent(
      new PageTransitionEvent("pageshow", { persisted: true }),
    );
    expect(button).toBeEnabled();
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).not.toHaveClass("knora-loading");
    expect(form).not.toHaveAttribute("data-knora-pending");
  },
);

it("keeps registration usable when a later validator cancels the submission", async () => {
  const { form, button } = setup("kc-register-form");
  form.addEventListener("submit", (event) => event.preventDefault());
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(button).toBeEnabled();
  expect(button).not.toHaveAttribute("aria-busy");
  expect(button).not.toHaveClass("knora-loading");
});
