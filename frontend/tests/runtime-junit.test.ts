import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { expect, it } from "vitest";

it("runtime JUnit distinguishes the same journey in desktop and mobile", () => {
  const root = path.resolve(process.cwd(), "..");
  const temp = mkdtempSync(path.join(tmpdir(), "knora-runtime-junit-"));
  const playwright = JSON.stringify(
    path.join(root, "frontend/node_modules/@playwright/test"),
  );
  try {
    const config = path.join(temp, "playwright.config.cjs");
    writeFileSync(
      config,
      `const { defineConfig } = require(${playwright});
module.exports = defineConfig({ testDir: __dirname, workers: 1, retries: 0,
  outputDir: __dirname + '/results',
  projects: [{ name: 'desktop' }, { name: 'mobile' }] });`,
    );
    writeFileSync(
      path.join(temp, "report.spec.js"),
      `const { test } = require(${playwright});
test('same journey', () => {});`,
    );
    const harness = path.join(temp, "report.ps1");
    writeFileSync(
      harness,
      `param($Source,$Root,$Config,$Output)
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$null,[ref]$null)
foreach ($name in 'Invoke-Checked','Invoke-Playwright') {
    $function = $ast.Find({param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $name
    },$true)
    Invoke-Expression $function.Extent.Text
}
$repositoryRoot=$Root; $profileDir=$Output
Invoke-Playwright 'native' $Config 'report.spec.js' '' '' | Out-Host`,
    );
    const run = spawnSync(
      "pwsh",
      [
        "-NoProfile",
        "-File",
        harness,
        path.join(root, "scripts/run-runtime-verification.ps1"),
        root,
        config,
        temp,
      ],
      { encoding: "utf8", timeout: 20_000 },
    );
    expect(run.status, run.stdout + run.stderr).toBe(0);
    const validation = spawnSync(
      "python",
      [
        path.join(root, "scripts/ci_checks.py"),
        "reports",
        path.join(temp, "native.xml"),
      ],
      { encoding: "utf8", timeout: 10_000 },
    );
    expect(validation.status, validation.stdout + validation.stderr).toBe(0);
    expect(validation.stdout).toContain("2 passing test cases");
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}, 30_000);
