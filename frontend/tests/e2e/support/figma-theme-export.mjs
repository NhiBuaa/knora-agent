import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repository = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
);
const versions = { freemarker: "2.3.32", keycloak: "26.3.3" };

function valueAfter(args, name) {
  const index = args.indexOf(name);
  return index === -1 ? undefined : args[index + 1];
}

export function parseExportArguments(args = process.argv.slice(2)) {
  if (args.includes("--read-owned-parent-css"))
    throw new Error(
      "Live Keycloak CSS export was removed; provide pinned Maven artifacts instead.",
    );
  const allowed = new Set([
    "--artifact-dir",
    "--freemarker-jar",
    "--keycloak-themes-jar",
    "--keycloak-themes-vendor-jar",
    "--repository",
    "--output",
  ]);
  if (args.some((arg) => arg.startsWith("--") && !allowed.has(arg)))
    throw new Error("Unknown native fixture exporter option.");
  if (
    args.includes("--freemarker-jar") ||
    args.includes("--keycloak-themes-jar") ||
    args.includes("--keycloak-themes-vendor-jar")
  )
    for (const name of [
      "--freemarker-jar",
      "--keycloak-themes-jar",
      "--keycloak-themes-vendor-jar",
    ])
      if (!valueAfter(args, name))
        throw new Error(
          `Pinned ${name.slice(2)} is required with explicit jar paths; provide the keycloak-themes-26.3.3.jar and other pinned jars.`,
        );
  const artifactDir = valueAfter(args, "--artifact-dir");
  return {
    repository: path.resolve(valueAfter(args, "--repository") ?? repository),
    output: path.resolve(
      valueAfter(args, "--output") ??
        path.join(repository, ".verification/figma/q1/native"),
    ),
    artifactDir: artifactDir && path.resolve(artifactDir),
    freemarkerJar:
      valueAfter(args, "--freemarker-jar") &&
      path.resolve(valueAfter(args, "--freemarker-jar")),
    keycloakThemesJar:
      valueAfter(args, "--keycloak-themes-jar") &&
      path.resolve(valueAfter(args, "--keycloak-themes-jar")),
    keycloakThemesVendorJar:
      valueAfter(args, "--keycloak-themes-vendor-jar") &&
      path.resolve(valueAfter(args, "--keycloak-themes-vendor-jar")),
  };
}

function localMavenRepositories() {
  return [
    process.env.MAVEN_REPO,
    process.env.USERPROFILE &&
      path.join(process.env.USERPROFILE, ".m2", "repository"),
    process.env.HOME && path.join(process.env.HOME, ".m2", "repository"),
    path.join(repository, ".m2", "repository"),
  ].filter(Boolean);
}
function findArtifact(root, filename) {
  const candidate = path.join(root, filename);
  return fs.existsSync(candidate) ? candidate : undefined;
}
function resolveFromMavenCache(filename) {
  const group = filename.startsWith("freemarker-")
    ? ["org", "freemarker", "freemarker", versions.freemarker]
    : filename.startsWith("keycloak-themes-vendor-")
      ? ["org", "keycloak", "keycloak-themes-vendor", versions.keycloak]
      : ["org", "keycloak", "keycloak-themes", versions.keycloak];
  return localMavenRepositories()
    .map((root) => findArtifact(path.join(root, ...group), filename))
    .find(Boolean);
}
function resolveWithProviderPom(repositoryRoot) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "knora-figma-maven-"));
  const output = path.join(temp, "classpath.txt");
  const pom = path.join(
    repositoryRoot,
    "infra/keycloak/providers/email-otp-reset/pom.xml",
  );
  if (!fs.existsSync(pom)) return [];
  try {
    execFileSync(
      "mvn",
      [
        "-B",
        "-ntp",
        "-q",
        "-f",
        pom,
        "dependency:build-classpath",
        `-Dmdep.outputFile=${output}`,
      ],
      { stdio: "ignore" },
    );
  } catch {
    return [];
  }
  return fs.existsSync(output)
    ? fs
        .readFileSync(output, "utf8")
        .trim()
        .split(path.delimiter)
        .filter(Boolean)
    : [];
}
function resolveJar(explicit, artifactDir, filename, classpath) {
  const resolved = artifactDir
    ? (explicit ?? findArtifact(artifactDir, filename))
    : (explicit ??
      resolveFromMavenCache(filename) ??
      classpath.find((entry) => path.basename(entry) === filename));
  if (!resolved || !fs.existsSync(resolved))
    throw new Error(
      `Pinned ${filename} is required; provide --artifact-dir or its explicit path.`,
    );
  return resolved;
}
export function resolveArtifactPaths(options) {
  const classpath =
    options.artifactDir || options.freemarkerJar
      ? []
      : resolveWithProviderPom(options.repository);
  return {
    freemarker: resolveJar(
      options.freemarkerJar,
      options.artifactDir,
      `freemarker-${versions.freemarker}.jar`,
      classpath,
    ),
    keycloakThemes: resolveJar(
      options.keycloakThemesJar,
      options.artifactDir,
      `keycloak-themes-${versions.keycloak}.jar`,
      classpath,
    ),
    keycloakThemesVendor: resolveJar(
      options.keycloakThemesVendorJar,
      options.artifactDir,
      `keycloak-themes-vendor-${versions.keycloak}.jar`,
      classpath,
    ),
  };
}
export function exportNativeFixtures(options = parseExportArguments()) {
  fs.mkdirSync(options.output, { recursive: true });
  const artifacts = resolveArtifactPaths(options);
  const classes = fs.mkdtempSync(path.join(os.tmpdir(), "knora-figma-java-"));
  try {
    const renderer = path.join(
      options.repository,
      "frontend/tests/e2e/support/FigmaThemeRenderer.java",
    );
    execFileSync(
      "javac",
      ["-cp", artifacts.freemarker, "-d", classes, renderer],
      { stdio: "inherit" },
    );
    execFileSync(
      "java",
      [
        "-cp",
        [
          classes,
          artifacts.freemarker,
          artifacts.keycloakThemes,
          artifacts.keycloakThemesVendor,
        ].join(path.delimiter),
        "FigmaThemeRenderer",
        options.repository,
        options.output,
        artifacts.keycloakThemes,
        artifacts.keycloakThemesVendor,
      ],
      { stdio: "inherit" },
    );
  } finally {
    fs.rmSync(classes, { recursive: true, force: true });
  }
}
if (
  process.argv[1] &&
  pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url
)
  exportNativeFixtures();
