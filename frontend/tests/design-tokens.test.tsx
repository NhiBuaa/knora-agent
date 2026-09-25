// @vitest-environment node

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const frontend = path.resolve(__dirname, "..");
const read = (file: string) => readFileSync(path.join(frontend, file), "utf8");

function declarations(css: string, selector: string): Record<string, string> {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const block = css.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`));
  expect(block, `missing ${selector} rule`).not.toBeNull();
  return Object.fromEntries(
    [...block![1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map(([, name, value]) => [name, value.trim()]),
  );
}

function systemDarkDeclarations(css: string): Record<string, string> {
  const media = css.match(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{([\s\S]*)\}\s*$/);
  expect(media, "missing system-dark media rule").not.toBeNull();
  return declarations(media![1], ':root:not([data-theme="light"]):not([data-theme="dark"])');
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255);
  const linear = channels.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function contrast(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("semantic visual tokens", () => {
  const css = read("styles/tokens.css");
  const tokens = {
    light: declarations(css, ":root"),
    dark: declarations(css, '[data-theme="dark"]'),
  };

  it("uses the approved base palette and complete roles in both themes", () => {
    expect(tokens.light["--page"]).toBe("#EFFCFA");
    expect(tokens.dark["--action"]).toBe("#4DBB73");
    for (const theme of Object.values(tokens)) {
      for (const role of ["page", "surface", "surface-subtle", "text-primary", "text-secondary", "text-muted", "action", "action-hover", "action-active", "action-foreground", "signature", "signature-foreground", "border", "control-border", "focus", "status-success", "status-warning", "status-error", "status-info"]) {
        expect(theme[`--${role}`], `missing ${role}`).toMatch(/^#[0-9A-F]{6}$/);
      }
      expect(contrast(theme["--action"], theme["--action-foreground"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--action-hover"], theme["--action-foreground"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--action-active"], theme["--action-foreground"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--signature"], theme["--signature-foreground"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--page"], theme["--text-primary"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--surface"], theme["--text-secondary"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["--surface"], theme["--text-muted"])).toBeGreaterThanOrEqual(4.5);
      for (const surface of ["surface", "surface-subtle"]) {
        expect(contrast(theme[`--${surface}`], theme["--control-border"])).toBeGreaterThanOrEqual(3);
      }
      for (const role of ["status-success", "status-warning", "status-error", "status-info"]) {
        expect(contrast(theme["--surface"], theme[`--${role}`])).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(theme["--page"], theme["--focus"])).toBeGreaterThanOrEqual(3);
    }
  });

  it("keeps system dark semantic values identical to explicit dark", () => {
    expect(systemDarkDeclarations(css)).toEqual(tokens.dark);
  });

  it("documents the CSS mapping instead of a second token object", () => {
    const guide = read("../docs/design/knora-visual-tokens.md");
    for (const [role, light, dark] of [
      ["page", "#EFFCFA", "#0B1412"],
      ["surface", "#FFFFFF", "#12201C"],
      ["action", "#33A15B", "#4DBB73"],
      ["signature", "#784131", "#C68F79"],
      ["text-primary", "#1F3B36", "#D7EFE6"],
      ["border", "#D9E2DE", "#2A3D36"],
      ["control-border", "#788A82", "#60776C"],
    ]) {
      expect(tokens.light[`--${role}`]).toBe(light);
      expect(tokens.dark[`--${role}`]).toBe(dark);
      expect(guide).toContain(`\`--${role}\` | ${light} | ${dark}`);
    }
  });

  it("assigns Roboto Slab to headings and Inter to controls", () => {
    const typography = read("styles/typography.css");
    const headingFontRole = typography.match(/--font-heading:\s*"([^"]+)"/)?.[1];
    const controlFontRole = typography.match(/--font-control:\s*"([^"]+)"/)?.[1];
    expect(headingFontRole).toBe("Roboto Slab");
    expect(controlFontRole).toBe("Inter");
    expect(typography).toMatch(/button,\s*input,\s*textarea,\s*select\s*\{[^}]*font-family:\s*var\(--font-inter\)/s);
  });
});
