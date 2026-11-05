import cp from "node:child_process";

export type ContainerTopologyInfo = {
  name: string;
  service: string;
  imageId: string;
  containerId: string;
  restartCount: number;
  startedAt: string;
};

export type TopologyManifest = {
  sourceSha: string;
  isClean: boolean;
  project: string;
  issuer: string;
  containers: ContainerTopologyInfo[];
};

export type ExecRunner = (command: string) => string;

export function measureTopologyManifest(
  project: string,
  customExec?: ExecRunner,
): TopologyManifest {
  const timeoutMs = 5000;
  const runCmd: ExecRunner =
    customExec ??
    ((cmd: string) =>
      cp
        .execSync(cmd, {
          encoding: "utf8",
          timeout: timeoutMs,
          stdio: ["pipe", "pipe", "pipe"],
        })
        .trim());

  let sourceSha = "";
  try {
    sourceSha = runCmd("git rev-parse HEAD").trim();
    if (
      !sourceSha ||
      sourceSha.length !== 40 ||
      !/^[0-9a-f]{40}$/i.test(sourceSha)
    ) {
      throw new Error(`Invalid git commit SHA: "${sourceSha}"`);
    }
  } catch (err: unknown) {
    throw new Error(`TOPOLOGY_GIT_SHA_FAILED: ${(err as Error).message}`);
  }

  let isClean = false;
  try {
    const statusOut = runCmd("git status --porcelain").trim();
    isClean = statusOut.length === 0;
  } catch (err: unknown) {
    throw new Error(`TOPOLOGY_GIT_STATUS_FAILED: ${(err as Error).message}`);
  }

  const containers: ContainerTopologyInfo[] = [];
  try {
    const psOut = runCmd(
      `docker ps --filter "label=com.docker.compose.project=${project}" --format "{{.ID}}"`,
    ).trim();

    if (!psOut) {
      throw new Error(
        `No active containers found for compose project "${project}"`,
      );
    }

    const containerIds = psOut
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    for (const cId of containerIds) {
      const inspectOut = runCmd(
        `docker inspect ${cId} --format "{{.Name}}|{{index .Config.Labels \\"com.docker.compose.service\\"}}|{{.Image}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.Id}}"`,
      ).trim();

      const parts = inspectOut.split("|");
      if (parts.length < 6) {
        throw new Error(
          `Malformed docker inspect format for container ${cId}: "${inspectOut}"`,
        );
      }
      containers.push({
        name: parts[0].replace(/^\//, ""),
        service: parts[1] || parts[0].replace(/^\//, ""),
        imageId: parts[2], // Immutable sha256 image ID / digest
        restartCount: Number(parts[3] || "0"),
        startedAt: parts[4],
        containerId: parts[5], // Full 64-char container ID
      });
    }

    containers.sort((a, b) => a.service.localeCompare(b.service));
  } catch (err: unknown) {
    throw new Error(
      `TOPOLOGY_DOCKER_INSPECT_FAILED: ${(err as Error).message}`,
    );
  }

  if (containers.length === 0) {
    throw new Error(
      `TOPOLOGY_EMPTY_CONTAINERS: project "${project}" has 0 running containers`,
    );
  }

  return {
    sourceSha,
    isClean,
    project,
    issuer: "http://127.0.0.1:8380/realms/knora-dev",
    containers,
  };
}

export function evaluateTopologyDrift(
  initial: TopologyManifest,
  final: TopologyManifest,
  expectedSha?: string,
): {
  zeroTopologyDrift: boolean;
  driftReasons: string[];
} {
  const driftReasons: string[] = [];

  if (!initial.isClean) {
    driftReasons.push("Initial worktree is dirty");
  }
  if (!final.isClean) {
    driftReasons.push("Final worktree is dirty");
  }

  if (expectedSha && expectedSha !== "HEAD") {
    if (initial.sourceSha !== expectedSha) {
      driftReasons.push(
        `Initial source SHA ${initial.sourceSha} does not match expected subject SHA ${expectedSha}`,
      );
    }
    if (final.sourceSha !== expectedSha) {
      driftReasons.push(
        `Final source SHA ${final.sourceSha} does not match expected subject SHA ${expectedSha}`,
      );
    }
  }

  if (initial.sourceSha !== final.sourceSha) {
    driftReasons.push(
      `Source SHA drift: ${initial.sourceSha} -> ${final.sourceSha}`,
    );
  }

  if (initial.containers.length === 0) {
    driftReasons.push("Initial containers list is empty");
  }
  if (final.containers.length !== initial.containers.length) {
    driftReasons.push(
      `Container count changed: ${initial.containers.length} -> ${final.containers.length}`,
    );
  }

  const minLen = Math.min(initial.containers.length, final.containers.length);
  for (let i = 0; i < minLen; i++) {
    const a = initial.containers[i];
    const b = final.containers[i];
    if (a.service !== b.service) {
      driftReasons.push(
        `Service at index ${i} changed: ${a.service} -> ${b.service}`,
      );
    }
    if (a.name !== b.name) {
      driftReasons.push(
        `Container ${a.service} name changed: ${a.name} -> ${b.name}`,
      );
    }
    if (a.containerId !== b.containerId) {
      driftReasons.push(
        `Container ${a.service} ID changed: ${a.containerId} -> ${b.containerId}`,
      );
    }
    if (a.imageId !== b.imageId) {
      driftReasons.push(
        `Container ${a.service} image ID changed: ${a.imageId} -> ${b.imageId}`,
      );
    }
    if (a.restartCount !== b.restartCount) {
      driftReasons.push(
        `Container ${a.service} restart count changed: ${a.restartCount} -> ${b.restartCount}`,
      );
    }
    if (a.startedAt !== b.startedAt) {
      driftReasons.push(
        `Container ${a.service} startedAt timestamp changed: ${a.startedAt} -> ${b.startedAt}`,
      );
    }
  }

  return {
    zeroTopologyDrift: driftReasons.length === 0,
    driftReasons,
  };
}
