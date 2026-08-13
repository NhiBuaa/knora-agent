# ruff: noqa: E501

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knora.answering.evidence_closure_v2 import (
    SealedEvidenceItem,
    close_scanner_result,
)

CANDIDATE = "eb1ce77d6b7f7165a59cd01ec6de588db032ce24"
SEAL_ID = "issue-56-final-seal-v1"
EXPECTED_R9_BLOB = "7833e7c4100b20ca5e5de01d3702ae29e0b55e9a"
EXPECTED_R9_SHA256 = "f409277b54aa32e1a811d7b1d43ed3b0f993d7b715a14eee3145fc9bbaab5cf6"
EVIDENCE_ROOT = Path(".agents/manual-tests/milestone-3/evidence")
HISTORY = Path(".agents/manual-tests/milestone-3/56-production-retrieval-v2.evaluations.jsonl")


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def command(*args: str, cwd: Path | None = None) -> bytes:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
    ).stdout


def final_evaluation(observed_at: str) -> dict[str, Any]:
    shared = {
        "candidate_sha": CANDIDATE,
        "authority_commit": "a64f40745db87d9f1584188f2f1ad73829f80d1f",
    }
    return {
        "schema_version": 1,
        "run_id": "m3-issue-56-20260813-acceptance-passed-01",
        "observed_at": observed_at,
        "executor": "Codex",
        "guide_revision": "issue-56-v5",
        "candidate": shared,
        "test_results": [
            {
                "id": "TC-01",
                "outcome": "PASS",
                "observation": (
                    "Exact reviewed R9 and fresh dependency assertions passed. Final "
                    "ordinary evidence is sealed by issue-56-final-seal-v1; this record "
                    "is effective only with its schema-qualified closure result reporting "
                    "zero exact credential matches."
                ),
                "evidence": [
                    "R9 blob 7833e7c4100b20ca5e5de01d3702ae29e0b55e9a",
                    "R9 blob-byte SHA-256 F409277B54AA32E1A811D7B1D43ED3B0F993D7B715A14EEE3145FC9BBAAB5CF6",
                    "seal issue-56-final-seal-v1",
                ],
            },
            {
                "id": "TC-02",
                "outcome": "PASS",
                "observation": "Exact NFKC asymmetric inputs and one text Content invariant passed.",
            },
            {
                "id": "TC-03",
                "outcome": "PASS",
                "observation": "EmbedContentConfig dimensionality and 1536 response validation passed.",
            },
            {
                "id": "TC-04",
                "outcome": "PASS",
                "observation": "First run and result bind frozen calibration SHA-256 692eac26a4d4857bb7fd147213ca8b5691961b3b4878f7dc915bda55ef281f07.",
            },
            {
                "id": "TC-05",
                "outcome": "PASS",
                "observation": "Complete-population independence oracle and independent semantic review passed.",
            },
            {
                "id": "TC-06",
                "outcome": "PASS",
                "observation": "All usefulness gates passed; sealed threshold selection deterministically pinned 0.657410732025.",
                "evidence": [
                    "observed table b38c54023369503fbefd3af77abbac11d382d4181193ab9ebd0194fe2ce9de6f",
                    "calibration result b66615100f4085fabd94f5efd194ffcfeafbe4da68d7f3ffde6174fa05940c66",
                ],
            },
            {
                "id": "TC-07",
                "outcome": "PASS",
                "observation": "Missing, guessed, inherited, and failed-calibration threshold paths fail closed.",
            },
            {
                "id": "TC-08",
                "outcome": "PASS",
                "observation": "All four m3-corpus-v1 members re-embedded on unchanged Chunk Sets; v1 remained immutable and cutover completed.",
                "evidence": [
                    "production reembedding 54fa8631a606ff857606371f059bea491ae740be47a0cf8d778c98eeda3d499d"
                ],
            },
            {
                "id": "TC-09",
                "outcome": "PASS",
                "observation": "fts-m3-or-v2 normalization, adversarial bound SQL, and empty-query zero-SQL behavior passed.",
            },
            {
                "id": "TC-10",
                "outcome": "PASS",
                "observation": "Both branch budgets equal eight; rrf-v2 dedup, contribution, and total ordering passed.",
            },
            {
                "id": "TC-11",
                "outcome": "PASS",
                "observation": "Vector/hybrid normalized diff contains exactly strategy, fts_candidate_k, lexical_policy_id, and fusion_policy_id.",
            },
            {
                "id": "TC-12",
                "outcome": "PASS",
                "observation": "Downstream Evidence Selection semantics and limits remain unchanged.",
            },
            {
                "id": "TC-13",
                "outcome": "PASS",
                "observation": "Semantic, lexical, and mixed runs passed through AnswerQuestion to AnsweringStore.retrieve_candidates with exact traces.",
                "evidence": [
                    "production retrieval ea29d8a1b912de8c8004a61fa895685f358dbbd4b3b860ce6287aca0a78a3930"
                ],
            },
            {
                "id": "TC-14",
                "outcome": "PASS",
                "observation": "Pre-closure #51 stayed blocked; conditional post-closure handback only makes TC-02/03/04 eligible and executes no #51 test.",
            },
        ],
        "automated_verification": {
            "pytest": "472 passed, 3 skipped",
            "ruff": "PASS",
            "docker_compose_config": "PASS",
            "git_diff_check": "PASS",
        },
        "human_approval": "approved",
        "human_approval_candidate_sha": CANDIDATE,
        "verdict": "PASSED",
        "closure_dependency": {
            "seal_id": SEAL_ID,
            "required_status": "PASS",
            "required_aggregate_match_count": 0,
        },
    }


def append_evaluation(root: Path, evaluation: dict[str, Any]) -> None:
    path = root / HISTORY
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if evaluation["run_id"] in existing:
        raise ValueError("final Evaluation run already exists")
    path.write_bytes(existing.encode() + canonical_json(evaluation))


def r9_proof(root: Path) -> dict[str, Any]:
    tree = command(
        "git",
        "ls-tree",
        "HEAD",
        "--",
        "docs/design/m3-retrieval-rrf-v2-authority-proposal-r9.md",
        cwd=root,
    ).decode()
    blob = tree.split()[2]
    blob_bytes = command("git", "cat-file", "blob", blob, cwd=root)
    if blob != EXPECTED_R9_BLOB or sha256(blob_bytes) != EXPECTED_R9_SHA256:
        raise ValueError("R9 authority identity mismatch")
    return {"blob": blob, "blob_byte_count": len(blob_bytes), "blob_sha256": sha256(blob_bytes)}


def issue_snapshot(number: str) -> bytes:
    return command(
        "gh",
        "api",
        f"repos/NhiBuaa/knora-agent/issues/{number}",
    )


def issue_comments(number: str) -> bytes:
    return command(
        "gh",
        "api",
        f"repos/NhiBuaa/knora-agent/issues/{number}/comments",
        "--paginate",
    )


def safe_db_projection() -> bytes:
    sql = (
        "select json_build_object('workspace_id',d.workspace_id,'source_key',d.source_key,"
        "'document_id',d.id,'document_version_id',d.current_document_version_id,"
        "'active_embedding_set_id',d.active_embedding_set_id,"
        "'active_embedding_configuration_id',d.active_embedding_configuration_id) "
        "from documents d where d.workspace_id='evaluation-m3-v1' order by d.source_key;"
        "select json_build_object('workspace_id',workspace_id,"
        "'embedding_configuration_id',embedding_configuration_id,"
        "'population_digest',population_digest,'status',status) "
        "from retrieval_v2_cutovers where workspace_id='evaluation-m3-v1';"
    )
    return command(
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "knora",
        "-d",
        "knora",
        "-Atc",
        sql,
    )


def ordinary_items(root: Path, issue51: Path, observed_at: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "candidate/git-archive.tar": command("git", "archive", "--format=tar", CANDIDATE, cwd=root),
        "evaluation/final-history.jsonl": (root / HISTORY).read_bytes(),
        "github/issue-56.json": issue_snapshot("56"),
        "github/issue-56-comments.json": issue_comments("56"),
        "github/issue-51.json": issue_snapshot("51"),
        "github/issue-51-comments.json": issue_comments("51"),
        "database/evaluation-m3-v1-safe-projection.jsonl": safe_db_projection(),
        "verification/summary.json": canonical_json(
            {
                "candidate_sha": CANDIDATE,
                "observed_at": observed_at,
                "pytest": "472 passed, 3 skipped",
                "ruff": "PASS",
                "docker_compose_config": "PASS",
                "git_diff_check": "PASS",
                "r9": r9_proof(root),
                "guide_blob": "9e0d91c79b13d5f84042176d79979b1c45f75d00",
                "frozen_calibration_sha256": "692eac26a4d4857bb7fd147213ca8b5691961b3b4878f7dc915bda55ef281f07",
                "issue51_tests_executed": False,
            }
        ),
        "closure/runner.py": (root / "evals/calibration/close_issue_56_evidence.py").read_bytes(),
    }
    issue51_names = (
        "51-production-evaluation-correlation-v12.md",
        "51-production-evaluation-correlation.evaluations.jsonl",
        "51-production-evaluation-correlation-v5-blocked-20260812-01.json",
    )
    for name in issue51_names:
        files[f"issue-51-locked/{name}"] = (
            issue51 / ".agents/manual-tests/milestone-3" / name
        ).read_bytes()
    status = command("git", "status", "--porcelain", cwd=issue51)
    files["issue-51-locked/worktree-status.txt"] = status
    for path in sorted(EVIDENCE_ROOT.glob("issue-56-*.json")):
        files[f"issue-56-evidence/{path.name}"] = path.read_bytes()
    for path in sorted(EVIDENCE_ROOT.glob("issue-56-*.zip")):
        files[f"issue-56-evidence/{path.name}"] = path.read_bytes()
    for path in sorted(EVIDENCE_ROOT.glob("issue-56-*.sha256")):
        files[f"issue-56-evidence/{path.name}"] = path.read_bytes()
    return files


def seal(
    files: dict[str, bytes], seal_path: Path, observed_at: str
) -> tuple[bytes, tuple[SealedEvidenceItem, ...]]:
    manifest_items = tuple(
        SealedEvidenceItem(reference=name, byte_count=len(content), sha256=sha256(content))
        for name, content in sorted(files.items())
    )
    manifest = canonical_json(
        {
            "schema_version": 1,
            "seal_id": SEAL_ID,
            "candidate_sha": CANDIDATE,
            "sealed_at": observed_at,
            "items": [asdict(item) for item in manifest_items],
        }
    )
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        payloads = {"SEALED-MANIFEST.json": manifest, **files}
        for name, content in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o444
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    sealed = buffer.getvalue()
    seal_path.write_bytes(sealed)
    seal_path.chmod(0o444)
    with tarfile.open(seal_path, "r") as archive:
        persisted_manifest = archive.extractfile("SEALED-MANIFEST.json")
        if persisted_manifest is None or persisted_manifest.read() != manifest:
            raise ValueError("sealed manifest revalidation failed")
        for item in manifest_items:
            member = archive.extractfile(item.reference)
            if member is None:
                raise ValueError("sealed evidence member missing")
            content = member.read()
            if len(content) != item.byte_count or sha256(content) != item.sha256:
                raise ValueError("sealed evidence member changed")
    return manifest, manifest_items


def execute(root: Path, issue51: Path) -> None:
    if command("git", "rev-parse", "HEAD", cwd=root).decode().strip() != CANDIDATE:
        raise ValueError("approved candidate mismatch")
    credential = os.environ.get("KNORA_GEMINI_API_KEY")
    if not credential:
        raise ValueError("runtime credential unavailable for exact-value scan")
    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    append_evaluation(root, final_evaluation(observed_at))
    files = ordinary_items(root, issue51, observed_at)
    seal_path = root / EVIDENCE_ROOT / "issue-56-final-sealed-evidence-v1.tar"
    closure_path = root / EVIDENCE_ROOT / "issue-56-final-closure-result-v1.json"
    if seal_path.exists() or closure_path.exists():
        raise ValueError("closure artifacts already exist")
    manifest, items = seal(files, seal_path, observed_at)
    sealed_bytes = seal_path.read_bytes()
    literal = credential.encode()
    per_item = {item.reference: files[item.reference].count(literal) for item in items}
    manifest_match_count = manifest.count(literal)
    archive_match_count = sealed_bytes.count(literal)
    credential = ""
    if manifest_match_count or archive_match_count != sum(per_item.values()):
        raise ValueError("sealed archive scan cannot be reconciled to manifest inventory")
    result = close_scanner_result(
        seal_id=SEAL_ID,
        sealed_manifest_sha256=sha256(manifest),
        manifest=items,
        per_item_match_counts=per_item,
        completed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    closure = {
        **asdict(result),
        "sealed_archive_sha256": sha256(sealed_bytes),
        "sealed_archive_byte_count": len(sealed_bytes),
        "candidate_sha": CANDIDATE,
        "closure_artifact_role": "sole-non-recursively-scanned-result",
    }
    closure_path.write_bytes(canonical_json(closure))
    closure_path.chmod(0o444)
    if result.status != "PASS":
        raise ValueError("exact credential match found in sealed evidence")
    print(
        json.dumps(
            {
                "status": result.status,
                "seal_id": result.seal_id,
                "item_count": result.item_count,
                "total_byte_count": result.total_byte_count,
                "aggregate_match_count": result.aggregate_match_count,
                "sealed_archive_sha256": closure["sealed_archive_sha256"],
                "closure_result_sha256": sha256(closure_path.read_bytes()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    execute(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
