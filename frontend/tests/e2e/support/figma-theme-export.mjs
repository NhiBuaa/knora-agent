import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repository = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
);
fs.mkdirSync(path.join(repository, ".verification/figma/q1/native"), {
  recursive: true,
});
const parentStyles = {
  "patternfly.min.css":
    "60d06da3e8d411c4263558546527ddf294b821fbad5dc777f3c338b47d3cb744",
  "patternfly-addons.css":
    "048733a7b0de85495862f45957a223779d7d0c68d7ad6b32b824b815c6790551",
};
for (const [name, expected] of Object.entries(parentStyles)) {
  const target = path.join(
    repository,
    ".verification/figma/q1/native/common/vendor/patternfly-v5",
    name,
  );
  if (process.argv.includes("--read-owned-parent-css")) {
    const labels = execFileSync(
      "docker",
      [
        "inspect",
        "knora-figma-e2e-figma-keycloak-1",
        "--format",
        '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.docker.compose.project.working_dir"}}|{{json .NetworkSettings.Ports}}',
      ],
      { encoding: "utf8" },
    );
    const fields = labels.trim().split("|");
    const bindings = JSON.parse(fields[3])["8080/tcp"];
    if (
      fields[0] !== "knora-figma-e2e" ||
      fields[1] !== "figma-keycloak" ||
      path.resolve(fields[2]) !== repository ||
      !bindings?.some(
        (binding) =>
          binding.HostIp === "127.0.0.1" && binding.HostPort === "8380",
      )
    )
      throw new Error("Owned static parent resource boundary rejected.");
    const response = await fetch(
      `http://127.0.0.1:8380/resources/bgqz0/common/keycloak/vendor/patternfly-v5/${name}`,
    );
    if (!response.ok)
      throw new Error("Pinned static parent resource unavailable.");
    const content = Buffer.from(await response.arrayBuffer());
    if (createHash("sha256").update(content).digest("hex") !== expected)
      throw new Error("Pinned static parent resource hash changed.");
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
  }
  if (
    !fs.existsSync(target) ||
    createHash("sha256").update(fs.readFileSync(target)).digest("hex") !==
      expected
  )
    throw new Error(
      "Complete pinned parent CSS required; use --read-owned-parent-css against the owned graph.",
    );
}
// The pinned image and already-owned proof cache are supplied by the controller.
// Export is offline; it cannot read or mutate live realm/database services.
execFileSync(
  "docker",
  [
    "run",
    "--rm",
    "--network",
    "none",
    "--mount",
    `type=bind,source=${repository},target=/work`,
    "--mount",
    "type=volume,source=knora-figma-e2e_maven-proof-cache,target=/root/.m2,readonly",
    "--workdir",
    "/work",
    "--entrypoint",
    "sh",
    "maven:3.9.9-eclipse-temurin-21",
    "-c",
    "set -eu; fm=/root/.m2/repository/org/freemarker/freemarker/2.3.32/freemarker-2.3.32.jar; kc=/root/.m2/repository/org/keycloak/keycloak-themes/26.3.3/keycloak-themes-26.3.3.jar; javac -cp $fm -d /tmp frontend/tests/e2e/support/FigmaThemeRenderer.java; java -cp /tmp:$fm:$kc FigmaThemeRenderer /work /work/.verification/figma/q1/native $kc",
  ],
  { stdio: "inherit" },
);
