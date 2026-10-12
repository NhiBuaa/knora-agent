import { spawnSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

const script = path.resolve(
  process.cwd(),
  "tests/e2e/support/figma-theme-export.mjs",
);

describe("offline native fixture exporter", () => {
  it("rejects an incomplete explicit artifact selection before rendering", () => {
    const result = spawnSync(
      process.execPath,
      [script, "--freemarker-jar", "freemarker-2.3.32.jar"],
      { encoding: "utf8" },
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toMatch(/keycloak-themes-26\.3\.3\.jar/);
  });

  it("accepts a repository-local artifact directory as the pinned source", () => {
    const result = spawnSync(
      process.execPath,
      [script, "--artifact-dir", ".verification/figma/missing-artifacts"],
      { encoding: "utf8" },
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toMatch(/freemarker-2\.3\.32\.jar/);
  });
});
