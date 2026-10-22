"""Consumer of saved #192 PDF read_run objects, pinned to source 8535130."""

import hashlib
import json
import re

NATIVE_IDS = ("workspace_id", "run_id", "case_id", "attempt_id", "trace_id")


def project_saved_observations(raw: bytes, *, expected_sha256: str) -> list[dict]:
    if not isinstance(raw, bytes) or not isinstance(expected_sha256, str):
        raise ValueError("INVALID_ARTIFACT")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("ARTIFACT_DIGEST_MISMATCH")
    value = json.loads(raw.decode("utf-8-sig"))
    if (
        not isinstance(value, dict)
        or value.get("execution_status")
        not in {"QUEUED", "RUNNING", "COMPLETED", "BLOCKED", "INDETERMINATE"}
        or not isinstance(value.get("observations"), dict)
    ):
        raise ValueError("UNSUPPORTED_REPRESENTATION")
    result = []
    seen = set()
    for case_id, record in value["observations"].items():
        if not isinstance(case_id, str) or not case_id.strip() or not isinstance(record, dict):
            raise ValueError("INVALID_OBSERVATION")
        identity = {}
        for key in NATIVE_IDS:
            outer = case_id if key == "case_id" else value.get(key)
            inner = record.get(key)
            if outer is not None and inner is not None and outer != inner:
                raise ValueError("IDENTITY_CONFLICT")
            native = inner if inner is not None else outer
            if native is not None and (not isinstance(native, str) or not native.strip()):
                raise ValueError("INVALID_NATIVE_IDENTITY")
            identity[key] = native
        if not identity["case_id"] or identity["case_id"] in seen:
            raise ValueError("INVALID_CASE_IDENTITY")
        seen.add(identity["case_id"])
        status = record.get("status", "NOT_RUN")
        if status not in {"OBSERVED", "FAILED", "NOT_RUN", "BLOCKED", "INDETERMINATE"}:
            raise ValueError("INVALID_OBSERVATION_STATUS")
        decision = record.get("decision")
        if decision not in {None, "ANSWER", "REFUSAL"}:
            raise ValueError("INVALID_DECISION")
        evidence_status = record.get("generation_evidence_status")
        if evidence_status not in {None, "exact", "unavailable"}:
            raise ValueError("INVALID_EVIDENCE_STATUS")
        pairs = record.get("generation_evidence", [])
        if (
            not isinstance(pairs, list)
            or any(
                not isinstance(pair, list)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not re.fullmatch(r"E[1-9][0-9]*", pair[0])
                or not isinstance(pair[1], str)
                or not pair[1].strip()
                for pair in pairs
            )
            or [p[0] for p in pairs] != [f"E{i + 1}" for i in range(len(pairs))]
        ):
            raise ValueError("INVALID_PAIR_EVIDENCE")
        if evidence_status is not None and (evidence_status == "exact") != bool(pairs):
            raise ValueError("CONFLICTING_EVIDENCE_STATUS")
        output = record.get("public_answer")
        if output is not None and not isinstance(output, str):
            raise ValueError("INVALID_OUTPUT")
        bound = all(identity.values())
        exact = bound and status == "OBSERVED" and bool(pairs)
        result.append(
            {
                **identity,
                "source_artifact_sha256": digest,
                "status": status,
                "decision": decision,
                "generation_evidence": [
                    {"alias": alias, "content": content} for alias, content in pairs
                ]
                if exact
                else [],
                "generation_evidence_status": "exact" if exact else "unavailable",
                "public_answer": output,
                "output_status": "exact"
                if bound
                and status == "OBSERVED"
                and decision == "ANSWER"
                and output
                and output.strip()
                else "unavailable",
            }
        )
    return result
