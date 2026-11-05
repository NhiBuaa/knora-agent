import { describe, it, expect } from "vitest";
import {
  measureTopologyManifest,
  evaluateTopologyDrift,
  type TopologyManifest,
} from "./e2e/support/topology-manifest";

describe("Topology manifest measurement and drift evaluation", () => {
  const mockSha = "033b037ec71185413f94c92381dd14ba968f3ff5";
  const mockImageId =
    "sha256:6857183e8fa9f7831d1029c4ba5e227df2fbc89006dfa98e0965e683e390c50a";
  const mockContainerId =
    "c1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2";

  function createMockExec(overrides: Partial<Record<string, string>> = {}) {
    return (cmd: string): string => {
      if (cmd.includes("git rev-parse HEAD")) {
        if ("git rev-parse HEAD" in overrides)
          return overrides["git rev-parse HEAD"]!;
        return mockSha;
      }
      if (cmd.includes("git status --porcelain")) {
        if ("git status --porcelain" in overrides)
          return overrides["git status --porcelain"]!;
        return ""; // clean
      }
      if (cmd.includes("docker ps")) {
        if ("docker ps" in overrides) return overrides["docker ps"]!;
        return "c1a2b3c4d5e6\nc2b3c4d5e6f7";
      }
      if (cmd.includes("docker inspect c1a2b3c4d5e6")) {
        if ("docker inspect c1" in overrides)
          return overrides["docker inspect c1"]!;
        return `/knora-api|figma-api|${mockImageId}|0|2026-10-30T10:00:00Z|${mockContainerId}`;
      }
      if (cmd.includes("docker inspect c2b3c4d5e6f7")) {
        if ("docker inspect c2" in overrides)
          return overrides["docker inspect c2"]!;
        return `/knora-keycloak|figma-keycloak|sha256:kc1234567890abcdef|0|2026-10-30T10:00:00Z|c2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a3`;
      }
      return "";
    };
  }

  it("measures topology successfully when git and docker are clean and valid", () => {
    const manifest = measureTopologyManifest("test-project", createMockExec());
    expect(manifest.sourceSha).toBe(mockSha);
    expect(manifest.isClean).toBe(true);
    expect(manifest.project).toBe("test-project");
    expect(manifest.containers).toHaveLength(2);
    expect(manifest.containers[0].service).toBe("figma-api");
    expect(manifest.containers[0].imageId).toBe(mockImageId);
    expect(manifest.containers[0].containerId).toBe(mockContainerId);
    expect(manifest.containers[0].restartCount).toBe(0);
    expect(manifest.containers[1].service).toBe("figma-keycloak");
  });

  it("fails closed when git rev-parse throws an error", () => {
    const failingExec = () => {
      throw new Error("fatal: not a git repository");
    };
    expect(() => measureTopologyManifest("test-project", failingExec)).toThrow(
      /TOPOLOGY_GIT_SHA_FAILED/,
    );
  });

  it("fails closed when git SHA is invalid format", () => {
    const invalidShaExec = createMockExec({ "git rev-parse HEAD": "HEAD" });
    expect(() =>
      measureTopologyManifest("test-project", invalidShaExec),
    ).toThrow(/Invalid git commit SHA/);
  });

  it("fails closed when git status command throws", () => {
    const failingExec = (cmd: string) => {
      if (cmd.includes("git status")) throw new Error("permission denied");
      return mockSha;
    };
    expect(() => measureTopologyManifest("test-project", failingExec)).toThrow(
      /TOPOLOGY_GIT_STATUS_FAILED/,
    );
  });

  it("fails closed when docker ps returns empty string (no containers)", () => {
    const emptyDockerExec = createMockExec({ "docker ps": "" });
    expect(() =>
      measureTopologyManifest("test-project", emptyDockerExec),
    ).toThrow(/No active containers found/);
  });

  it("fails closed when docker inspect throws or malformed", () => {
    const malformedExec = createMockExec({
      "docker inspect c1": "invalid|data",
    });
    expect(() =>
      measureTopologyManifest("test-project", malformedExec),
    ).toThrow(/Malformed docker inspect format/);
  });

  it("evaluates zeroTopologyDrift as true for identical topologies with matching SHA", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const m2 = measureTopologyManifest("test-proj", createMockExec());

    const result = evaluateTopologyDrift(m1, m2, mockSha);
    expect(result.zeroTopologyDrift).toBe(true);
    expect(result.driftReasons).toEqual([]);
  });

  it("detects drift when worktree is dirty", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const mDirty: TopologyManifest = { ...m1, isClean: false };

    const result = evaluateTopologyDrift(m1, mDirty, mockSha);
    expect(result.zeroTopologyDrift).toBe(false);
    expect(result.driftReasons).toContain("Final worktree is dirty");
  });

  it("detects drift when sourceSha does not match expected subject SHA", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const m2 = measureTopologyManifest("test-proj", createMockExec());

    const result = evaluateTopologyDrift(
      m1,
      m2,
      "1111111111111111111111111111111111111111",
    );
    expect(result.zeroTopologyDrift).toBe(false);
    expect(
      result.driftReasons.some((r) =>
        r.includes("does not match expected subject SHA"),
      ),
    ).toBe(true);
  });

  it("detects drift when container image ID changes", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const mDrift: TopologyManifest = {
      ...m1,
      containers: [
        { ...m1.containers[0], imageId: "sha256:mutatedimageid123" },
        m1.containers[1],
      ],
    };

    const result = evaluateTopologyDrift(m1, mDrift, mockSha);
    expect(result.zeroTopologyDrift).toBe(false);
    expect(
      result.driftReasons.some((r) => r.includes("image ID changed")),
    ).toBe(true);
  });

  it("detects drift when container restarts or startedAt changes", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const mRestarted: TopologyManifest = {
      ...m1,
      containers: [
        {
          ...m1.containers[0],
          restartCount: 1,
          startedAt: "2026-10-30T10:30:00Z",
        },
        m1.containers[1],
      ],
    };

    const result = evaluateTopologyDrift(m1, mRestarted, mockSha);
    expect(result.zeroTopologyDrift).toBe(false);
    expect(
      result.driftReasons.some((r) => r.includes("restart count changed")),
    ).toBe(true);
    expect(
      result.driftReasons.some((r) =>
        r.includes("startedAt timestamp changed"),
      ),
    ).toBe(true);
  });

  it("detects drift when container count changes", () => {
    const m1 = measureTopologyManifest("test-proj", createMockExec());
    const mMissing: TopologyManifest = {
      ...m1,
      containers: [m1.containers[0]],
    };

    const result = evaluateTopologyDrift(m1, mMissing, mockSha);
    expect(result.zeroTopologyDrift).toBe(false);
    expect(
      result.driftReasons.some((r) => r.includes("Container count changed")),
    ).toBe(true);
  });
});
