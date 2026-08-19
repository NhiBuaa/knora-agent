"""Immutable M3 improvement-claim authority and validation seams.

The Markdown authority explains the policy, but the JSON projection and the Git/seal identities
below are the only production authority.  Focused tests may use ``ClaimRuleAuthority`` fixtures;
the canonical selector still validates the complete identity bundle before applying policy.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

AUTHORITY_VALIDATION_FAILURE = "AUTHORITY_VALIDATION_FAILURE"
AUTHORITY_IDENTIFIER = "m3-improvement-claim-v1"
CLAIM_RULE_VERSION = AUTHORITY_IDENTIFIER
APPROVED_HUMAN_IDENTITY = "NhiBuaa"
METRIC_CONTRACT = "m3-retrieval-metrics-v1"
CLAIM_RULE_DIGEST = "sha256:5f44d27602a6a9819d857a15f8cee201deea0f21385b01789777b4ef7bf83c7e"
SOURCE_COMMIT = "82f8f5193b658310e73e9f2fb4abf13ebb954076"
AUTHORITY_DOCUMENT_PATH = "docs/design/m3-improvement-claim-rule-v3.md"
AUTHORITY_DOCUMENT_BLOB = "cb9c917eaf3d73a31ec4e3d1007bb2463168dcc9"
AUTHORITY_DOCUMENT_SHA256 = "a8e43cd2468302df35c94648327f9c688f01ea0ba20a199f5a3dc78752ce4773"
POLICY_PROJECTION_PATH = "docs/design/m3-improvement-claim-rule-v1.policy.json"
POLICY_PROJECTION_BLOB = "6a79bfe367dc1af95a0f50613dcbaa6d3dc868b9"
ATTESTATION_PATH = ".agents/review/m3-improvement-claim-v1-approval.json"
ATTESTATION_COMMIT = "ed575ef837cd422bce131d79fc31959791996bcb"
ATTESTATION_BLOB = "0422385455af91420efab5affb87aabdb0c0f14c"
ATTESTATION_SHA256 = "8dbd257dffec5969b756a165f48e527ac6f79e2b1414786df594a7ca1346b4b1"
SEAL_ID = "m3-improvement-claim-v1-approval-seal-v2"
SEALED_ARCHIVE_PATH = ".agents/review/m3-improvement-claim-v1-approval-sealed-v2.tar"
SEALED_ARCHIVE_SHA256 = "7f24cedc0a9f0f97f06d97483e43b1c9231c6fb93a2996b8cde2bab234a4f38b"
SEALED_MANIFEST_SHA256 = "f7180796e6259cdcd8f5928311c260d77ab71b07a287c9417d8ab849cf2f6dff"
CLOSURE_PATH = ".agents/review/m3-improvement-claim-v1-approval-closure-v2.json"
CLOSURE_SHA256 = "5cec43e9a1cd4f502d8308b38bd2b27d30bfbec6922006c01b4fb1c13257e627"
REMEDIATION_IDENTITY_RECORD_PATH = (
    ".agents/review/identities/codex-agent-m3-final-package-review-v4.json"
)
REMEDIATION_IDENTITY_PROJECTION_PATH = (
    ".agents/review/identities/codex-agent-m3-final-package-review-v4-projection.json"
)
REMEDIATION_IDENTITY_GIT_BLOB = "e72ec5f9c834b51f48b507f36519ca16d9df1f5e"
REMEDIATION_IDENTITY_RAW_SHA256 = (
    "sha256:1fa4a4ef8e640c5c32f3ad88ebe38dd662381a89f8e347170fefa119f8d654e3"
)
REMEDIATION_IDENTITY_DIGEST = (
    "sha256:b6af13241badf537647b9c0301043fa721ea6fb42a1ab6a344ff28065076bfda"
)
REMEDIATION_SCOPE_PROJECTION_PATH = ".agents/review/m3-remediation-v4-scope-projection-final.json"
REMEDIATION_SCOPE_DIGEST = "closure.scope_projection_raw_sha256"
REMEDIATION_RESPONSE_PROJECTION_PATH = ".agents/review/m3-remediation-v4-response-projection-final.json"
REMEDIATION_RESPONSE_DIGEST = "closure.response_projection_raw_sha256"
REMEDIATION_SUBJECT_COMMIT = "closure.subject_commit"
REMEDIATION_SUBJECT_BLOB = "closure.subject_blob"
REMEDIATION_REVIEWER_ID = "codex-agent:/root/m3_final_package_review_v4"
REMEDIATION_CLOSURE_PATH = ".agents/review/m3-remediation-v4-review-closure-final.json"
REMEDIATION_CLOSURE_GIT_BLOB = "closure.git_blob"
REMEDIATION_CLOSURE_RAW_SHA256 = "closure.raw_sha256"
M3_POPULATION_SOURCE_COMMIT = "2a6061ad38b3b3c4f06811c7ceb8bc26af39892"

REQUIRED_GUARDRAIL_KEYS = (
    "structural_validity",
    "citation_correctness",
    "refusal_correctness",
)
EQUAL_PROVENANCE_FIELDS = (
    "dataset_version",
    "dataset_digest",
    "corpus_id",
    "corpus_digest",
    "chunk_set_id",
    "chunk_set_digest",
    "workspace",
    "chunking_configuration",
    "embedding_configuration",
    "generation_configuration",
    "scorer_configuration",
    "scorer_model",
    "scorer_prompt",
    "scorer_policy",
    "scorer_stochasticity",
    "metric_contract",
    "source_commit",
    "evaluation_commit",
    "report_artifact_schema_version",
)
ALLOWED_CONFIGURATION_FIELDS = (
    "retrieval_configuration_id",
    "strategy",
    "fusion_policy_id",
    "fusion_policy_version",
    "lexical_policy_id",
    "fts_candidate_k",
)

_EXPECTED_APPROVAL_KEYS = {
    "schema_version",
    "attestation_type",
    "authority_identifier",
    "claim_rule_version",
    "authority_document_path",
    "authority_document_blob",
    "authority_document_sha256",
    "policy_projection_path",
    "policy_projection_blob",
    "claim_rule_digest",
    "source_commit",
    "reviewer_id",
    "reviewer_was_author",
    "reviewed_complete_policy",
    "verdict",
    "policy_mutation_findings",
    "reviewed_at",
    "attestation_status",
    "approved_by",
    "approved_at",
}
_PLACEHOLDER_NORMALIZED = {
    "",
    "youridentity",
    "yourrealidentity",
    "humanidentity",
    "todo",
    "tbd",
    "unknown",
    "placeholder",
    "none",
    "na",
    "n/a",
}
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_RFC3339 = re.compile(r"\A\d{4}-\d{2}-\d{2}T[^\s]+(?:Z|[+-]\d{2}:?\d{2})\Z")


def _canonical_projection() -> dict[str, Any]:
    """Load the machine-readable projection; policy values do not live in Python."""
    path = Path(__file__).resolve().parents[2] / POLICY_PROJECTION_PATH
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("POLICY_PROJECTION_INVALID") from error
    if not isinstance(value, Mapping):
        raise ValueError("POLICY_PROJECTION_INVALID")
    return deepcopy(dict(value))


def canonical_policy_projection() -> dict[str, Any]:
    """Return a copy of the approved projection for an explicit focused-test fixture."""
    return deepcopy(_canonical_projection())


def _strict_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(_strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def validate_policy_projection(projection: object) -> dict[str, Any]:
    if not isinstance(projection, Mapping) or not _strict_equal(
        projection, _canonical_projection()
    ):
        raise ValueError("POLICY_PROJECTION_INVALID")
    return deepcopy(dict(projection))


def is_non_placeholder_identity(identity: object) -> bool:
    if not isinstance(identity, str):
        return False
    normalized = re.sub(r"[^a-z0-9/]+", "", identity.strip().lower())
    return bool(identity.strip()) and normalized not in _PLACEHOLDER_NORMALIZED


def validate_human_identity(identity: object) -> str:
    """Low-level syntax seam; authorization still requires the complete sealed chain."""
    if not is_non_placeholder_identity(identity):
        raise ValueError("HUMAN_IDENTITY_PLACEHOLDER")
    return str(identity)


@dataclass(frozen=True, slots=True)
class ClaimRuleAuthority:
    """Typed projection plus the immutable identities that bind production authority."""

    projection: Mapping[str, Any]
    claim_rule_digest: str = CLAIM_RULE_DIGEST
    source_commit: str = SOURCE_COMMIT
    authority_document_blob: str = AUTHORITY_DOCUMENT_BLOB
    authority_document_sha256: str = AUTHORITY_DOCUMENT_SHA256
    policy_projection_blob: str = POLICY_PROJECTION_BLOB
    attestation_commit: str = ATTESTATION_COMMIT
    attestation_blob: str = ATTESTATION_BLOB
    attestation_sha256: str = ATTESTATION_SHA256
    reviewer_id: str = APPROVED_HUMAN_IDENTITY
    approved_by: str = APPROVED_HUMAN_IDENTITY
    seal_id: str = SEAL_ID
    sealed_manifest_sha256: str = SEALED_MANIFEST_SHA256
    sealed_archive_sha256: str = SEALED_ARCHIVE_SHA256
    closure_sha256: str = CLOSURE_SHA256
    closure_status: str = "PASS"
    approval_payload: Mapping[str, Any] | None = None
    external_reviewer_id: str = REMEDIATION_REVIEWER_ID
    review_identity_digest: str = REMEDIATION_IDENTITY_DIGEST
    review_identity_git_blob: str = REMEDIATION_IDENTITY_GIT_BLOB
    review_identity_raw_sha256: str = REMEDIATION_IDENTITY_RAW_SHA256
    review_subject_commit: str = REMEDIATION_SUBJECT_COMMIT
    review_subject_blob: str = REMEDIATION_SUBJECT_BLOB
    review_scope_digest: str = REMEDIATION_SCOPE_DIGEST
    review_response_digest: str = REMEDIATION_RESPONSE_DIGEST
    review_closure_git_blob: str = REMEDIATION_CLOSURE_GIT_BLOB
    review_closure_raw_sha256: str = REMEDIATION_CLOSURE_RAW_SHA256
    chain_verified: bool = False
    verification_method: str = "explicit-test-fixture"

    @classmethod
    def from_projection(
        cls,
        projection: Mapping[str, Any],
        **bindings: Any,
    ) -> ClaimRuleAuthority:
        validated = validate_policy_projection(projection)
        return cls(projection=validated, **bindings)

    def validated_projection(self) -> dict[str, Any]:
        return validate_policy_projection(self.projection)

    def with_projection(self) -> dict[str, Any]:
        return self.validated_projection()

    @property
    def authority_identifier(self) -> str:
        return self.projection["authority_identifier"]

    @property
    def claim_rule_version(self) -> str:
        return self.projection["claim_rule_version"]

    @property
    def metric_contract(self) -> str:
        return self.projection["metric_contract"]

    @property
    def recall_k(self) -> int:
        return self.projection["recall_k"]

    @property
    def primary_metrics(self) -> tuple[str, ...]:
        return tuple(self.projection["primary_metric_set"]["ordered"])

    @property
    def guardrail_keys(self) -> tuple[str, ...]:
        return tuple(self.projection["guardrail_requirement"]["required_keys"])

    @property
    def equal_provenance_fields(self) -> tuple[str, ...]:
        return tuple(self.projection["provenance"]["equal_fields"])

    @property
    def allowed_provenance_differences(self) -> tuple[str, ...]:
        return tuple(self.projection["provenance"]["allowed_differences"])

    @property
    def claim_scope(self) -> str:
        return self.projection["claim_scope"]


def claim_rule_authority_fixture() -> ClaimRuleAuthority:
    """Explicit low-level seam; callers must opt in and production still checks identities."""
    payload = {
        "schema_version": 1,
        "attestation_type": "m3-improvement-claim-authority-approval-v1",
        "authority_identifier": AUTHORITY_IDENTIFIER,
        "claim_rule_version": CLAIM_RULE_VERSION,
        "authority_document_path": AUTHORITY_DOCUMENT_PATH,
        "authority_document_blob": AUTHORITY_DOCUMENT_BLOB,
        "authority_document_sha256": AUTHORITY_DOCUMENT_SHA256,
        "policy_projection_path": POLICY_PROJECTION_PATH,
        "policy_projection_blob": POLICY_PROJECTION_BLOB,
        "claim_rule_digest": CLAIM_RULE_DIGEST,
        "source_commit": SOURCE_COMMIT,
        "reviewer_id": "NhiBuaa",
        "reviewer_was_author": False,
        "reviewed_complete_policy": True,
        "verdict": "PASS",
        "policy_mutation_findings": [],
        "reviewed_at": "2026-08-17T03:34:43Z",
        "attestation_status": "APPROVED_EFFECTIVE",
        "approved_by": "NhiBuaa",
        "approved_at": "2026-08-17T03:34:43Z",
    }
    return ClaimRuleAuthority.from_projection(
        canonical_policy_projection(),
        approval_payload=payload,
        chain_verified=False,
        verification_method="explicit-test-fixture",
    )


# Keep the descriptive alias for callers that want to emphasize the test-only seam without
# letting pytest collect the imported factory as a test function.
test_claim_rule_authority_fixture = claim_rule_authority_fixture
test_claim_rule_authority_fixture.__test__ = False


def _identity_failure(identity: object) -> str | None:
    if is_non_placeholder_identity(identity):
        return None
    return "HUMAN_IDENTITY_PLACEHOLDER"


def _strict_approval_payload(payload: object) -> tuple[bool, str | None]:
    if not isinstance(payload, Mapping) or set(payload) != _EXPECTED_APPROVAL_KEYS:
        return False, "APPROVAL_PAYLOAD_SCHEMA_INVALID"
    if payload.get("schema_version") != 1:
        return False, "APPROVAL_PAYLOAD_SCHEMA_INVALID"
    if payload.get("attestation_type") != "m3-improvement-claim-authority-approval-v1":
        return False, "APPROVAL_PAYLOAD_SCHEMA_INVALID"
    if payload.get("authority_identifier") != AUTHORITY_IDENTIFIER:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("claim_rule_version") != CLAIM_RULE_VERSION:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("authority_document_path") != AUTHORITY_DOCUMENT_PATH:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("authority_document_blob") != AUTHORITY_DOCUMENT_BLOB:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("authority_document_sha256") != AUTHORITY_DOCUMENT_SHA256:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("policy_projection_path") != POLICY_PROJECTION_PATH:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("policy_projection_blob") != POLICY_PROJECTION_BLOB:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("claim_rule_digest") != CLAIM_RULE_DIGEST:
        return False, "APPROVAL_BINDING_MISMATCH"
    if payload.get("source_commit") != SOURCE_COMMIT:
        return False, "APPROVAL_BINDING_MISMATCH"
    if _identity_failure(payload.get("reviewer_id")):
        return False, "HUMAN_IDENTITY_PLACEHOLDER"
    if _identity_failure(payload.get("approved_by")):
        return False, "HUMAN_IDENTITY_PLACEHOLDER"
    if payload.get("reviewer_was_author") is not False:
        return False, "APPROVAL_ASSERTION_INVALID"
    if payload.get("reviewed_complete_policy") is not True:
        return False, "APPROVAL_ASSERTION_INVALID"
    if payload.get("verdict") != "PASS" or payload.get("policy_mutation_findings") != []:
        return False, "APPROVAL_ASSERTION_INVALID"
    if payload.get("attestation_status") != "APPROVED_EFFECTIVE":
        return False, "APPROVAL_ASSERTION_INVALID"
    for field in ("reviewed_at", "approved_at"):
        value = payload.get(field)
        if not isinstance(value, str) or not _RFC3339.match(value):
            return False, "APPROVAL_TIMESTAMP_INVALID"
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False, "APPROVAL_TIMESTAMP_INVALID"
    try:
        canonical_bytes = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        )
    except (TypeError, ValueError):
        return False, "APPROVAL_PAYLOAD_SCHEMA_INVALID"
    if hashlib.sha256(canonical_bytes).hexdigest() != ATTESTATION_SHA256:
        return False, "ATTESTATION_PAYLOAD_DIGEST_MISMATCH"
    return True, None


def _coerce_authority(value: ClaimRuleAuthority | Mapping[str, Any]) -> ClaimRuleAuthority:
    if isinstance(value, ClaimRuleAuthority):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("AUTHORITY_BUNDLE_INVALID")
    projection = value.get("projection", value.get("policy_projection"))
    if projection is None and value.get("authority_identifier") == AUTHORITY_IDENTIFIER:
        projection = value
    if not isinstance(projection, Mapping):
        raise ValueError("AUTHORITY_BUNDLE_INVALID")
    bindings = {
        field: value[field]
        for field in (
            "claim_rule_digest",
            "source_commit",
            "authority_document_blob",
            "authority_document_sha256",
            "policy_projection_blob",
            "attestation_commit",
            "attestation_blob",
            "attestation_sha256",
            "reviewer_id",
            "approved_by",
            "seal_id",
            "sealed_manifest_sha256",
            "sealed_archive_sha256",
            "closure_sha256",
            "closure_status",
            "approval_payload",
            "external_reviewer_id",
            "review_identity_digest",
            "review_identity_git_blob",
            "review_identity_raw_sha256",
            "review_subject_commit",
            "review_subject_blob",
            "review_scope_digest",
            "review_response_digest",
            "review_closure_git_blob",
            "review_closure_raw_sha256",
            "chain_verified",
            "verification_method",
        )
        if field in value
    }
    return ClaimRuleAuthority.from_projection(projection, **bindings)


def canonical_authority_validation(
    authority: ClaimRuleAuthority | Mapping[str, Any] | None = None,
    *,
    production: bool = True,
    repository_root: Path | None = None,
    sealed_archive_path: Path | None = None,
    closure_path: Path | None = None,
) -> dict[str, Any]:
    """Validate the exact authority identity before a policy decision is made."""
    # Production authority is a Git/seal capability, never a caller-provided object.  A
    # non-placeholder identity is only a syntax fixture; accepting it here would let a mutable
    # working-tree object self-assert APPROVED_EFFECTIVE without resolving the approved blobs.
    if production and authority is not None:
        try:
            supplied_bundle = _coerce_authority(authority)
        except (TypeError, ValueError) as error:
            return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": str(error)}
        for identity in (supplied_bundle.reviewer_id, supplied_bundle.approved_by):
            failure = _identity_failure(identity)
            if failure:
                return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": failure}
        return {
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": "CALLER_AUTHORITY_OVERRIDE",
        }
    if authority is None:
        if repository_root is None:
            return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": "AUTHORITY_MISSING"}
        sealed_archive_path = sealed_archive_path or repository_root / SEALED_ARCHIVE_PATH
        closure_path = closure_path or repository_root / CLOSURE_PATH
        try:
            authority = _authority_from_git(
                repository_root,
                sealed_archive_path=sealed_archive_path,
                closure_path=closure_path,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
            tarfile.TarError,
        ) as error:
            reason = str(error) or "AUTHORITY_VALIDATION_FAILURE"
            return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": reason}
    try:
        bundle = _coerce_authority(authority)
        bundle.validated_projection()
    except ValueError as error:
        return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": str(error)}
    for identity in (bundle.reviewer_id, bundle.approved_by):
        failure = _identity_failure(identity)
        if failure:
            return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": failure}
    expected = {
        "claim_rule_digest": CLAIM_RULE_DIGEST,
        "source_commit": SOURCE_COMMIT,
        "authority_document_blob": AUTHORITY_DOCUMENT_BLOB,
        "authority_document_sha256": AUTHORITY_DOCUMENT_SHA256,
        "policy_projection_blob": POLICY_PROJECTION_BLOB,
        "attestation_commit": ATTESTATION_COMMIT,
        "attestation_blob": ATTESTATION_BLOB,
        "attestation_sha256": ATTESTATION_SHA256,
        "seal_id": SEAL_ID,
        "sealed_manifest_sha256": SEALED_MANIFEST_SHA256,
        "sealed_archive_sha256": SEALED_ARCHIVE_SHA256,
        "closure_sha256": CLOSURE_SHA256,
        "closure_status": "PASS",
    }
    for field, expected_value in expected.items():
        if getattr(bundle, field) != expected_value:
            reason = (
                "ATTESTATION_IDENTITY_MISMATCH"
                if field in {"attestation_commit", "attestation_blob", "attestation_sha256"}
                else f"{field.upper()}_IDENTITY_MISMATCH"
            )
            return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": reason}
    payload_ok, payload_reason = _strict_approval_payload(bundle.approval_payload)
    if not payload_ok and (production or bundle.approval_payload is not None):
        return {"status": AUTHORITY_VALIDATION_FAILURE, "reason": payload_reason}
    if production and (
        bundle.reviewer_id != APPROVED_HUMAN_IDENTITY
        or bundle.approved_by != APPROVED_HUMAN_IDENTITY
    ):
        return {
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": "APPROVAL_IDENTITY_MISMATCH",
        }
    if payload_ok and (
        bundle.approval_payload["reviewer_id"] != bundle.reviewer_id
        or bundle.approval_payload["approved_by"] != bundle.approved_by
    ):
        return {
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": "APPROVAL_BINDING_MISMATCH",
        }
    if production and (
        not bundle.chain_verified or bundle.verification_method != "git-seal"
    ):
        return {
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": "AUTHORITY_CHAIN_UNVERIFIED",
        }
    return {
        "status": "APPROVED_EFFECTIVE",
        "reason": None,
        "claim_rule_version": CLAIM_RULE_VERSION,
        "claim_rule_digest": CLAIM_RULE_DIGEST,
        "authority": bundle,
    }


def _git(*args: str, repository_root: Path) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _git_blob(repository_root: Path, commit: str, path: str) -> tuple[str, bytes]:
    blob = _git("rev-parse", f"{commit}:{path}", repository_root=repository_root).decode().strip()
    content = _git("cat-file", "blob", blob, repository_root=repository_root)
    return blob, content


def _remediation_review_from_git(repository_root: Path) -> dict[str, str]:
    """Resolve the immutable package -> scope -> response -> closure chain from Git."""
    head = _git("rev-parse", "HEAD", repository_root=repository_root).decode().strip()
    closure_blob, closure_bytes = _git_blob(repository_root, head, REMEDIATION_CLOSURE_PATH)
    closure = json.loads(closure_bytes.decode("utf-8"))
    if not isinstance(closure, Mapping) or (
        closure.get("schema_version") != 2
        or closure.get("closure_id") != "m3-remediation-v4-review-closure-final-v1"
        or closure.get("status") != "APPROVED_EFFECTIVE"
        or closure.get("verdict") != "APPROVE"
        or any(closure.get(key) != 0 for key in ("critical_count", "major_count", "minor_count"))
        or closure.get("reviewer_id") != REMEDIATION_REVIEWER_ID
    ):
        raise ValueError("REMEDIATION_CLOSURE_INVALID")

    subject_commit = closure.get("subject_commit")
    subject_design_blob = closure.get("subject_blob")
    if not isinstance(subject_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", subject_commit):
        raise ValueError("REMEDIATION_SUBJECT_INVALID")
    if not isinstance(subject_design_blob, str) or not re.fullmatch(r"[0-9a-f]{40}", subject_design_blob):
        raise ValueError("REMEDIATION_SUBJECT_INVALID")

    subject_design_path = "docs/design/m3-remediation-v4.md"
    subject_blob, _ = _git_blob(
        repository_root, subject_commit, subject_design_path
    )
    if subject_blob != subject_design_blob:
        raise ValueError("REMEDIATION_SUBJECT_IDENTITY_MISMATCH")

    identity_blob, identity_bytes = _git_blob(
        repository_root, head, REMEDIATION_IDENTITY_RECORD_PATH
    )
    identity_raw_sha256 = "sha256:" + hashlib.sha256(identity_bytes).hexdigest()
    if identity_blob != REMEDIATION_IDENTITY_GIT_BLOB or (
        identity_raw_sha256 != REMEDIATION_IDENTITY_RAW_SHA256
    ):
        raise ValueError("REMEDIATION_IDENTITY_MISMATCH")
    identity = json.loads(identity_bytes.decode("utf-8"))
    expected_identity_keys = {
        "schema_version",
        "reviewer_id",
        "identity_kind",
        "task_path",
        "provider",
        "source_authority",
        "identity_digest",
        "purpose",
        "created_at",
    }
    if not isinstance(identity, Mapping) or set(identity) != expected_identity_keys:
        raise ValueError("REMEDIATION_IDENTITY_SCHEMA_INVALID")
    projection_blob, projection_bytes = _git_blob(
        repository_root, head, REMEDIATION_IDENTITY_PROJECTION_PATH
    )
    if projection_blob == "" or not projection_bytes:
        raise ValueError("REMEDIATION_IDENTITY_PROJECTION_MISSING")
    identity_projection = json.loads(projection_bytes.decode("utf-8"))
    if not isinstance(identity_projection, Mapping) or set(identity_projection) != {
        "identity_kind",
        "provider",
        "reviewer_id",
        "source_authority",
        "task_path",
    }:
        raise ValueError("REMEDIATION_IDENTITY_PROJECTION_INVALID")
    canonical_identity = (
        json.dumps(dict(identity_projection), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        + b"\n"
    )
    identity_digest = "sha256:" + hashlib.sha256(canonical_identity).hexdigest()
    if (
        identity.get("schema_version") != 1
        or identity.get("reviewer_id") != REMEDIATION_REVIEWER_ID
        or identity.get("identity_digest") != REMEDIATION_IDENTITY_DIGEST
        or identity_digest != REMEDIATION_IDENTITY_DIGEST
        or dict(identity_projection)
        != {
            "identity_kind": identity.get("identity_kind"),
            "provider": identity.get("provider"),
            "reviewer_id": identity.get("reviewer_id"),
            "source_authority": identity.get("source_authority"),
            "task_path": identity.get("task_path"),
        }
    ):
        raise ValueError("REMEDIATION_IDENTITY_BINDING_MISMATCH")

    scope_meta = closure.get("scope_projection")
    if not isinstance(scope_meta, Mapping) or (
        scope_meta.get("path") != REMEDIATION_SCOPE_PROJECTION_PATH
    ):
        raise ValueError("REMEDIATION_CLOSURE_SCOPE_INVALID")
    scope_blob, scope_bytes = _git_blob(repository_root, head, REMEDIATION_SCOPE_PROJECTION_PATH)
    scope_raw_sha256 = "sha256:" + hashlib.sha256(scope_bytes).hexdigest()
    if (
        scope_blob != scope_meta.get("git_blob")
        or scope_raw_sha256 != scope_meta.get("raw_sha256")
    ):
        raise ValueError("REMEDIATION_SCOPE_DIGEST_MISMATCH")
    scope = json.loads(scope_bytes.decode("utf-8"))
    required_requirements = [
        "authority_independent_review",
        "exact_manifest_population",
        "native_dependency_graph",
        "no_evaluation_only_retrieval",
        "pair_latency_boundary",
        "paired_generation_scorer_invariants",
        "public_citation_and_trace_failure",
        "sole_source_policy_projection",
        "two_layer_taxonomy",
    ]
    if not isinstance(scope, Mapping) or (
        scope.get("schema_version") != 2
        or scope.get("subject_commit") != subject_commit
        or scope.get("subject_blob") != subject_design_blob
        or scope.get("requirements") != required_requirements
        or scope.get("subject_paths") != sorted(set(scope.get("subject_paths", [])))
    ):
        raise ValueError("REMEDIATION_SCOPE_BINDING_MISMATCH")
    for path in scope["subject_paths"]:
        _git_blob(repository_root, subject_commit, str(path))

    response_meta = closure.get("response_projection")
    if not isinstance(response_meta, Mapping) or (
        response_meta.get("path") != REMEDIATION_RESPONSE_PROJECTION_PATH
    ):
        raise ValueError("REMEDIATION_CLOSURE_RESPONSE_INVALID")
    response_blob, response_bytes = _git_blob(
        repository_root, head, REMEDIATION_RESPONSE_PROJECTION_PATH
    )
    response_raw_sha256 = "sha256:" + hashlib.sha256(response_bytes).hexdigest()
    if (
        response_blob != response_meta.get("git_blob")
        or response_raw_sha256 != response_meta.get("raw_sha256")
    ):
        raise ValueError("REMEDIATION_RESPONSE_DIGEST_MISMATCH")
    response = json.loads(response_bytes.decode("utf-8"))
    if not isinstance(response, Mapping) or (
        response.get("schema_version") != 2
        or response.get("identity_record") != REMEDIATION_IDENTITY_RECORD_PATH
        or response.get("identity_digest") != REMEDIATION_IDENTITY_DIGEST
        or response.get("reviewer_id") != REMEDIATION_REVIEWER_ID
        or response.get("subject_commit") != subject_commit
        or response.get("reviewed_commit") != subject_commit
        or response.get("subject_blob") != subject_design_blob
        or response.get("scope_projection_blob") != scope_blob
        or response.get("scope_projection_raw_sha256") != scope_raw_sha256
        or response.get("status") != "completed"
        or response.get("verdict") != "APPROVE"
        or any(response.get(key) != 0 for key in ("critical_count", "major_count", "minor_count"))
        or response.get("finding") is not None
    ):
        raise ValueError("REMEDIATION_RESPONSE_BINDING_MISMATCH")

    policy_meta = closure.get("policy_projection")
    if not isinstance(policy_meta, Mapping) or policy_meta.get("path") != POLICY_PROJECTION_PATH:
        raise ValueError("REMEDIATION_CLOSURE_POLICY_INVALID")
    policy_blob, policy_bytes = _git_blob(repository_root, head, POLICY_PROJECTION_PATH)
    if policy_blob != policy_meta.get("git_blob") or (
        "sha256:" + hashlib.sha256(policy_bytes).hexdigest() != policy_meta.get("raw_sha256")
    ):
        raise ValueError("REMEDIATION_POLICY_PROVENANCE_MISMATCH")

    source_author = _git(
        "show", "-s", "--format=%an", subject_commit, repository_root=repository_root
    ).decode().strip()
    external_reviewer = str(identity["reviewer_id"])
    if external_reviewer in {source_author, APPROVED_HUMAN_IDENTITY}:
        raise ValueError("REMEDIATION_REVIEWER_NOT_INDEPENDENT")
    return {
        "external_reviewer_id": external_reviewer,
        "review_identity_digest": REMEDIATION_IDENTITY_DIGEST,
        "review_identity_git_blob": identity_blob,
        "review_identity_raw_sha256": REMEDIATION_IDENTITY_RAW_SHA256,
        "review_subject_commit": subject_commit,
        "review_subject_blob": subject_design_blob,
        "review_scope_digest": scope_raw_sha256,
        "review_response_digest": response_raw_sha256,
        "review_closure_git_blob": closure_blob,
        "review_closure_raw_sha256": "sha256:" + hashlib.sha256(closure_bytes).hexdigest(),
    }


def _authority_from_git(
    repository_root: Path,
    *,
    sealed_archive_path: Path | None,
    closure_path: Path | None,
) -> ClaimRuleAuthority:
    document_blob, document_bytes = _git_blob(
        repository_root, SOURCE_COMMIT, AUTHORITY_DOCUMENT_PATH
    )
    projection_blob, projection_bytes = _git_blob(
        repository_root, SOURCE_COMMIT, POLICY_PROJECTION_PATH
    )
    if document_blob != AUTHORITY_DOCUMENT_BLOB or (
        hashlib.sha256(document_bytes).hexdigest() != AUTHORITY_DOCUMENT_SHA256
    ):
        raise ValueError("AUTHORITY_DOCUMENT_IDENTITY_MISMATCH")
    if projection_blob != POLICY_PROJECTION_BLOB or (
        hashlib.sha256(projection_bytes).hexdigest()
        != CLAIM_RULE_DIGEST.removeprefix("sha256:")
    ):
        raise ValueError("POLICY_PROJECTION_IDENTITY_MISMATCH")
    attestation_blob, attestation_bytes = _git_blob(
        repository_root, ATTESTATION_COMMIT, ATTESTATION_PATH
    )
    if attestation_blob != ATTESTATION_BLOB or (
        hashlib.sha256(attestation_bytes).hexdigest() != ATTESTATION_SHA256
    ):
        raise ValueError("ATTESTATION_IDENTITY_MISMATCH")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE_COMMIT, ATTESTATION_COMMIT],
        cwd=repository_root,
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("ATTESTATION_NOT_DESCENDANT")
    payload = json.loads(attestation_bytes.decode("utf-8"))
    projection = json.loads(projection_bytes.decode("utf-8"))
    review_bindings = _remediation_review_from_git(repository_root)
    authority = ClaimRuleAuthority.from_projection(
        projection,
        approval_payload=payload,
        **review_bindings,
        chain_verified=True,
        verification_method="git-seal",
    )
    if sealed_archive_path is not None:
        archive_bytes = sealed_archive_path.read_bytes()
        if hashlib.sha256(archive_bytes).hexdigest() != SEALED_ARCHIVE_SHA256:
            raise ValueError("SEALED_ARCHIVE_IDENTITY_MISMATCH")
        manifest = _read_and_validate_sealed_archive(sealed_archive_path)
        if hashlib.sha256(manifest).hexdigest() != SEALED_MANIFEST_SHA256:
            raise ValueError("SEALED_MANIFEST_IDENTITY_MISMATCH")
    if closure_path is not None:
        closure_bytes = closure_path.read_bytes()
        if hashlib.sha256(closure_bytes).hexdigest() != CLOSURE_SHA256:
            raise ValueError("CLOSURE_IDENTITY_MISMATCH")
        closure = json.loads(closure_bytes.decode("utf-8"))
        expected_closure = {
            "schema_version": 1,
            "seal_id": SEAL_ID,
            "status": "PASS",
            "authority_source_commit": SOURCE_COMMIT,
            "authority_document_path": AUTHORITY_DOCUMENT_PATH,
            "authority_document_blob": AUTHORITY_DOCUMENT_BLOB,
            "policy_projection_path": POLICY_PROJECTION_PATH,
            "policy_projection_blob": POLICY_PROJECTION_BLOB,
            "claim_rule_digest": CLAIM_RULE_DIGEST,
            "attestation_path": ATTESTATION_PATH,
            "attestation_commit": ATTESTATION_COMMIT,
            "attestation_blob": ATTESTATION_BLOB,
            "attestation_sha256": ATTESTATION_SHA256,
            "sealed_manifest_sha256": SEALED_MANIFEST_SHA256,
            "sealed_archive_sha256": SEALED_ARCHIVE_SHA256,
            "closure_artifact_role": "sole-non-recursively-scanned-result",
        }
        if not isinstance(closure, Mapping) or not _strict_equal(closure, expected_closure):
            raise ValueError("CLOSURE_NOT_PASS")
    return authority


def _read_and_validate_sealed_archive(path: Path) -> bytes:
    with tarfile.open(path, "r") as archive:
        manifest_member = archive.extractfile("SEALED-MANIFEST.json")
        if manifest_member is None:
            raise ValueError("SEALED_MANIFEST_MISSING")
        manifest_bytes = manifest_member.read()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, Mapping) or set(manifest) != {
            "schema_version",
            "seal_id",
            "candidate_sha",
            "sealed_at",
            "items",
        }:
            raise ValueError("SEALED_MANIFEST_SCHEMA_INVALID")
        if manifest["schema_version"] != 1 or manifest["seal_id"] != SEAL_ID:
            raise ValueError("SEALED_MANIFEST_BINDING_MISMATCH")
        if manifest.get("candidate_sha") != SOURCE_COMMIT:
            raise ValueError("SEALED_MANIFEST_BINDING_MISMATCH")
        items = manifest["items"]
        if not isinstance(items, list):
            raise ValueError("SEALED_MANIFEST_SCHEMA_INVALID")
        references = [item.get("reference") for item in items if isinstance(item, Mapping)]
        if any(
            not isinstance(reference, str)
            or not reference
            or PurePosixPath(reference).is_absolute()
            or ".." in PurePosixPath(reference).parts
            for reference in references
        ):
            raise ValueError("SEALED_MANIFEST_SCHEMA_INVALID")
        attestation_references = [
            reference
            for reference in references
            if PurePosixPath(reference).name == PurePosixPath(ATTESTATION_PATH).name
        ]
        candidate_archives = [
            reference
            for reference in references
            if reference.endswith((".tar", ".tar.gz"))
        ]
        if (
            len(attestation_references) != 1
            or "authority-binding.json" not in references
            or len(candidate_archives) != 1
        ):
            raise ValueError("SEALED_MEMBER_MISSING")
        archive_members = archive.getmembers()
        archive_member_names = [member.name for member in archive_members]
        expected_member_names = {"SEALED-MANIFEST.json", *references}
        if (
            len(archive_member_names) != len(set(archive_member_names))
            or any(not member.isfile() for member in archive_members)
            or set(archive_member_names) != expected_member_names
        ):
            raise ValueError("SEALED_MEMBER_SET_MISMATCH")
        for item in items:
            if not isinstance(item, Mapping) or set(item) != {"reference", "byte_count", "sha256"}:
                raise ValueError("SEALED_MANIFEST_SCHEMA_INVALID")
            member = archive.extractfile(str(item["reference"]))
            if member is None:
                raise ValueError("SEALED_MEMBER_MISSING")
            content = member.read()
            if len(content) != item["byte_count"] or (
                hashlib.sha256(content).hexdigest() != item["sha256"]
            ):
                raise ValueError("SEALED_MEMBER_HASH_MISMATCH")
        return manifest_bytes


# Descriptive aliases for callers that use the authority-validation seam directly.
validate_approved_authority = canonical_authority_validation
validate_claim_rule_authority = canonical_authority_validation
