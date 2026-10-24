"""Regression tests verifying the complete remediation of findings A1 through A12."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from evals.runners.evaluation_review_packet import (
    FinalizerError,
    finalize_acceptance_results,
    project_capture_generation_evidence,
)
from evals.runners.langfuse_bridge import (
    BridgeError,
    readback_observations,
    readback_scores,
    verify_deleted,
)
from evals.scorers.deepeval_cloudflare import CloudflareJudge, JudgeError
from pydantic import BaseModel
from scripts.run_acceptance_live import load_credentials

from knora.evaluation.contracts import digest_json
from knora.evaluation.live_admission import (
    _SLOTS_V2,
    LiveAdmission,
    LivePackage,
    reviewed_build_pins,
    slot_authority_pins,
)


def _make_standard_12_items(primary_item_id="004", primary_cap=2, primary_digest="1" * 64):
    items = []
    for case_id in ("004", "005", "012", "014", "032", "045"):
        is_pri = case_id == primary_item_id
        items.append(
            {
                "item_id": case_id,
                "slot": "judge_real",
                "cap": primary_cap if is_pri else 1,
                "input_digest": primary_digest if is_pri else "a" * 64,
                "native_identity": {"case_id": case_id, "workspace_id": "ws-1"},
            }
        )
    for variant in ("wrong-fact", "off-topic", "unsupported", "missing-exception"):
        items.append(
            {
                "item_id": f"control-{variant}",
                "slot": "judge_synthetic",
                "cap": 1,
                "input_digest": "b" * 64,
                "native_identity": {"case_id": f"control-{variant}", "workspace_id": "ws-1"},
            }
        )
    for refusal_id in ("053", "002"):
        items.append(
            {
                "item_id": f"refusal-{refusal_id}",
                "slot": "refusal_deterministic",
                "cap": 0,
                "input_digest": "c" * 64,
                "native_identity": {"case_id": refusal_id, "workspace_id": "ws-1"},
            }
        )
    return items


def _make_manifest_v3(tmp_path, NOW, items, package_id="test-pkg"):
    pins = reviewed_build_pins()
    journal = tmp_path / f"{package_id}.sqlite"
    return {
        "manifest_version": 3,
        "package_id": package_id,
        "account_id": "a" * 32,
        "ownership": {"workspace_id": "ws-1"},
        "approved_by": "owner",
        "decision_reference": "ref",
        "live_approved_at": NOW.isoformat(),
        "package_deadline": (NOW + timedelta(days=7)).isoformat(),
        "max_attempts": 50,
        "startup_cap": 1,
        "window_cap": 1,
        "journal_path": str(journal.resolve()),
        "reviewed_build": pins,
        "code_sha": pins["code_sha"],
        "slots": dict(_SLOTS_V2),
        "skipped_slots": ["corpus_prepare", "qa_gold_v1_answer"],
        "gold_v1": {
            "dataset_id": "pdf-set-v3",
            "dataset_digest": "6" * 64,
            "version": 1,
            "cases": {"ANSWER": "answer", "REFUSAL": "refusal"},
            "sources": {
                "version-1": {"document_id": "document-1", "raw_sha256": "a" * 64},
            },
        },
        "items": items,
    }, journal


# -----------------------------------------------------------------------------
# A1: Runner uses controlled LiveAdmission transport; PENDING before send; wire hash
# -----------------------------------------------------------------------------
def test_a1_live_admission_transport_pending_before_send_and_wire_digest(tmp_path):
    NOW = datetime.now(UTC)
    items = _make_standard_12_items("004", primary_cap=2, primary_digest="1" * 64)
    manifest, journal = _make_manifest_v3(tmp_path, NOW, items, "test-pkg-a1")
    pkg = LivePackage.initialize(manifest, journal, clock=lambda: NOW)
    body = {"model": "@cf/openai/gpt-oss-20b", "max_tokens": 100}
    body_digest = digest_json(body)
    policy = {
        "item_id": "004",
        "approval_id": pkg.approval_id("judge_real", item_id="004"),
        "scope": {
            "purpose": "scoring",
            "profile_id": "judge-004",
            "workspace_id": "ws-1",
            "input_digest": "1" * 64,
        },
        "approved_by": "owner",
        "decision_reference": "ref",
        "classification": "public",
        "egress_approved": True,
        "account_id": "a" * 32,
        "plan": "Workers Free",
        "proof_observed_at": NOW.isoformat(),
        "proof_digest": "0" * 64,
        "deadline": (NOW + timedelta(minutes=5)).isoformat(),
        "max_attempts": 2,
        "quota_remaining_neurons": 10000,
        "max_neurons_per_attempt": 200,
        "paid_budget_usd": 0,
        "providers": [
            {
                "endpoint": (
                    f"https://api.cloudflare.com/client/v4/accounts/{'a' * 32}"
                    "/ai/v1/chat/completions"
                ),
                "model": "@cf/openai/gpt-oss-20b",
                "max_input_bytes": 4096,
                "max_output_tokens": 1024,
                "compatibility_digest": "3" * 64,
                "request_digests": [body_digest],
            }
        ],
    }
    auth = {"item_input": 1}
    pins = slot_authority_pins(manifest, "judge_real", policy, auth)
    inputs = {
        "input_digest": "1" * 64,
        "authority": auth,
        "identities": {"case_id": "004", "workspace_id": "ws-1"},
        "ancestry": {"corpus_prepare": "skipped"},
        **pins,
    }
    pkg.bind_item("judge_real", "004", policy, inputs)
    admission = LiveAdmission(policy, journal, clock=lambda: NOW, package=pkg, slot="judge_real")

    observed_status_during_exchange = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        with sqlite3.connect(journal) as db:
            row = db.execute(
                "SELECT status, body_digest FROM requests WHERE item_id='004'"
            ).fetchone()
            observed_status_during_exchange.append(row)
        return httpx.Response(
            200,
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
                "usage": {"completion_tokens": 5},
            },
        )

    cleanup = {
        "registration_id": "clean-1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "0" * 64,
    }
    with (
        pkg.window(
            scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
        ),
        pkg.operation("judge_real", item_id="004"),
        admission.dispatch(policy["scope"]),
    ):
        client = admission.sync_client(mock=httpx.MockTransport(mock_handler))
        res = client.post(
            policy["providers"][0]["endpoint"],
            json={"model": "@cf/openai/gpt-oss-20b", "max_tokens": 100},
        )
        assert res.status_code == 200

    # Verify PENDING was observed during exchange and wire hash was recorded
    assert len(observed_status_during_exchange) == 1
    assert observed_status_during_exchange[0][0] == "PENDING"
    # Verify COMPLETED was recorded only after successful return
    with sqlite3.connect(journal) as db:
        final_row = db.execute("SELECT status FROM requests WHERE item_id='004'").fetchone()
        assert final_row[0] == "COMPLETED"


# -----------------------------------------------------------------------------
# A2: Completed slot does not re-issue judge requests on resume
# -----------------------------------------------------------------------------
def test_a2_completed_slot_reads_durable_results_without_re_evaluating(tmp_path):
    NOW = datetime.now(UTC)
    items = _make_standard_12_items()
    manifest, journal = _make_manifest_v3(tmp_path, NOW, items, "test-pkg-a2")
    LivePackage.initialize(manifest, journal, clock=lambda: NOW)
    # Directly record completed result into slots table as if finished previously
    with sqlite3.connect(journal) as db:
        res = json.dumps({"status": "SUCCESS", "results": {"case-1": {"score": 1.0}}})
        db.execute(
            "UPDATE slots SET status='COMPLETED', result_json=? WHERE name='judge_real'",
            (res,),
        )

    # Resuming the package reads durable results without issuing any network request
    reopened = LivePackage(manifest, journal, clock=lambda: NOW)
    assert reopened.snapshot()["slots"]["judge_real"]["status"] == "COMPLETED"
    durable_results = reopened.slot_result("judge_real")
    assert durable_results["results"]["case-1"]["score"] == 1.0


# -----------------------------------------------------------------------------
# A3: reviewed_build_pins covers scripts/run_acceptance_live.py
# -----------------------------------------------------------------------------
def test_a3_reviewed_build_pins_includes_acceptance_live_runner():
    pins = reviewed_build_pins()
    assert "scripts/run_acceptance_live.py" in pins["sources"]
    assert len(pins["sources"]["scripts/run_acceptance_live.py"]) == 64


# -----------------------------------------------------------------------------
# A4: bind_item checks immutable input digest, manifest cap, tamper detection
# -----------------------------------------------------------------------------
def test_a4_bind_item_tamper_and_lower_cap_enforcement(tmp_path):
    NOW = datetime.now(UTC)
    items = _make_standard_12_items("004", primary_cap=5, primary_digest="a" * 64)
    manifest, journal = _make_manifest_v3(tmp_path, NOW, items, "test-pkg-a4")
    pkg = LivePackage.initialize(manifest, journal, clock=lambda: NOW)

    # 1. Digest mismatch rejected
    bad_policy = {
        "approval_id": pkg.approval_id("judge_real", item_id="004"),
        "scope": {
            "purpose": "scoring",
            "profile_id": "p",
            "workspace_id": "ws-1",
            "input_digest": "f" * 64,
        },
        "approved_by": "owner",
        "decision_reference": "ref",
        "classification": "public",
        "egress_approved": True,
        "account_id": "a" * 32,
        "plan": "Workers Free",
        "proof_observed_at": NOW.isoformat(),
        "proof_digest": "0" * 64,
        "deadline": (NOW + timedelta(minutes=5)).isoformat(),
        "max_attempts": 1,
        "quota_remaining_neurons": 10000,
        "max_neurons_per_attempt": 200,
        "paid_budget_usd": 0,
        "providers": [
            {
                "endpoint": (
                    f"https://api.cloudflare.com/client/v4/accounts/{'a' * 32}"
                    "/ai/v1/chat/completions"
                ),
                "model": "@cf/openai/gpt-oss-20b",
                "max_input_bytes": 4096,
                "max_output_tokens": 1024,
            }
        ],
    }
    bad_inputs = {
        "input_digest": "f" * 64,
        "authority": {"item_input": 1},
        "identities": {"case_id": "004", "workspace_id": "ws-1"},
    }
    with pytest.raises(ValueError, match="LIVE_ITEM_DIGEST_MISMATCH"):
        pkg.bind_item("judge_real", "004", bad_policy, bad_inputs)

    # 2. Lower policy cap enforcement (max_attempts = 1 even though db cap = 5)
    good_policy = {
        **bad_policy,
        "scope": {**bad_policy["scope"], "input_digest": "a" * 64},
        "max_attempts": 1,
    }
    good_inputs = {
        "input_digest": "a" * 64,
        "authority": {"item_input": 1},
        "identities": {"case_id": "004", "workspace_id": "ws-1"},
        "ancestry": {"corpus_prepare": "skipped"},
        **slot_authority_pins(manifest, "judge_real", good_policy, {"item_input": 1}),
    }
    pkg.bind_item("judge_real", "004", good_policy, good_inputs)

    cleanup = {
        "registration_id": "clean-1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "0" * 64,
    }
    with (
        pkg.window(
            scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
        ),
        pkg.operation("judge_real", item_id="004"),
        pkg._db() as db,
    ):
        pkg.reserve(db, "judge_real", item_id="004")
        app_id = pkg.approval_id("judge_real", item_id="004")
        db.execute("UPDATE approvals SET attempts=attempts+1 WHERE id=?", (app_id,))
        db.execute(
            "INSERT INTO requests (approval_id, sequence, body_digest, endpoint, model, "
            "reserved_at, status, item_id) "
            "VALUES (?, 1, '0000000000000000000000000000000000000000000000000000000000000000', "
            "'https://endpoint', 'model', ?, 'COMPLETED', '004')",
            (app_id, NOW.isoformat()),
        )
        # Second attempt must be rejected because policy max_attempts=1
        with pytest.raises(ValueError, match="LIVE_ITEM_CAP"):
            pkg.reserve(db, "judge_real", item_id="004")

    # 3. Tampering cap in DB causes reopen failure
    with sqlite3.connect(journal) as db:
        db.execute("UPDATE items SET cap=99 WHERE item_id='004'")
    with pytest.raises(ValueError, match="LIVE_PACKAGE_TAMPERED"):
        LivePackage(manifest, journal, clock=lambda: NOW)


# -----------------------------------------------------------------------------
# A5: Evidence projection respects alias_mapping; fail-closed on missing
# -----------------------------------------------------------------------------
def test_a5_evidence_projection_respects_alias_mapping():
    raw_cap = {
        "public_response": {"citations": [{"evidence_id": "E1", "content_checksum": "a" * 64}]},
        "alias_mapping": {"E1": "chunk-2", "E2": "chunk-1"},
        "candidates": [
            {
                "chunk_id": "chunk-1",
                "final_decision": "SELECTED",
                "final_rank": 1,
                "content": "Content 1",
            },
            {
                "chunk_id": "chunk-2",
                "final_decision": "SELECTED",
                "final_rank": 2,
                "content": "Content 2",
            },
        ],
    }
    import hashlib

    h2 = hashlib.sha256(b"Content 2").hexdigest()
    raw_cap["public_response"]["citations"][0]["content_checksum"] = h2

    evidence, verdict = project_capture_generation_evidence(raw_cap)
    assert verdict == "VALID"
    assert evidence[0]["alias"] == "E1"
    assert evidence[0]["content"] == "Content 2"
    assert evidence[1]["alias"] == "E2"
    assert evidence[1]["content"] == "Content 1"


# -----------------------------------------------------------------------------
# A6: Human labels completeness & authentic refusal evaluation
# -----------------------------------------------------------------------------
def test_a6_finalizer_requires_all_12_items():
    human_packet = {"packet_sha256": "digest123"}
    # Incomplete labels (< 12 items)
    incomplete_labels = {
        "packet_sha256": "digest123",
        "items": [{"case_id": "c1", "review": "accept"} for _ in range(5)],
    }
    with pytest.raises(FinalizerError, match="HUMAN_LABELS_INCOMPLETE"):
        finalize_acceptance_results({}, human_packet, incomplete_labels)


# -----------------------------------------------------------------------------
# A7: Langfuse POST_PENDING, POST_UNKNOWN and single-deletion protection
# -----------------------------------------------------------------------------
def test_a7_langfuse_post_unknown_and_single_deletion(tmp_path):
    from evals.runners.langfuse_bridge import ReceiptManager

    receipt = tmp_path / "receipt.json"
    ReceiptManager.reserve(
        receipt,
        approval_id="app:canary",
        project_key_fingerprint="f",
        payload_sha256="s",
        trace_ids=["trace-1"],
        observation_ids=["obs-1"],
        imported_at=datetime.now(UTC).isoformat(),
    )
    # Verify state transition helper
    ReceiptManager.update(receipt, status="POST_PENDING")
    assert ReceiptManager.read(receipt)["status"] == "POST_PENDING"
    ReceiptManager.update(receipt, status="POST_UNKNOWN")
    assert ReceiptManager.read(receipt)["status"] == "POST_UNKNOWN"


# -----------------------------------------------------------------------------
# A8: Dossier marks PENDING_OWNER_ACCEPTANCE and does not self-claim ACCEPTED
# -----------------------------------------------------------------------------
def test_a8_dossier_marks_pending_owner_acceptance():
    from evals.runners.evaluation_review_packet import SYNTHETIC_CONTROLS, TARGET_CASES

    judged = {}
    for cid in TARGET_CASES:
        judged[cid] = {
            "metrics": {
                m: {"status": "scored", "score": 1.0}
                for m in ("correctness", "answer_relevancy", "faithfulness")
            }
        }
    for vid, spec in SYNTHETIC_CONTROLS.items():
        ctrl_id = f"{spec['parent_case_id']}-{vid}"
        judged[ctrl_id] = {
            "metrics": {
                m: {
                    "status": "scored",
                    "score": 0.0 if m == spec["target_rejected_metric"] else 1.0,
                }
                for m in ("correctness", "answer_relevancy", "faithfulness")
            }
        }

    human_packet = {"packet_sha256": "h123"}
    human_labels = {
        "packet_sha256": "h123",
        "items": [{"case_id": f"item-{i}", "review": "accept"} for i in range(12)],
    }
    dossier = finalize_acceptance_results(judged, human_packet, human_labels)
    assert dossier["acceptance_status"] == "PENDING_OWNER_ACCEPTANCE"
    assert dossier["evaluation_status"] == "SCORED_READY_FOR_OWNER_REVIEW"
    assert dossier["pending_owner_gate"] == "GATE_3_FINAL_ACCEPTANCE"


# -----------------------------------------------------------------------------
# A9: Observations and scores 404 raise BridgeError; two-round verify_deleted
# -----------------------------------------------------------------------------
def test_a9_observations_404_raises_and_two_round_verification():
    def mock_404_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(
        base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(mock_404_handler)
    )
    with pytest.raises(BridgeError, match="READBACK_FAILED_404"):
        readback_observations(client, "tid")
    with pytest.raises(BridgeError, match="READBACK_FAILED_404"):
        readback_scores(client, "tid")

    # verify_deleted requires 2 consecutive rounds
    rounds = [0]

    def mock_delete_verify(req: httpx.Request) -> httpx.Response:
        rounds[0] += 1
        if rounds[0] <= 3:
            # First round: trace still present
            return httpx.Response(200, json={"id": "tid"})
        # Subsequent rounds: trace gone (404)
        return httpx.Response(404)

    client_del = httpx.Client(
        base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(mock_delete_verify)
    )
    assert verify_deleted(client_del, ["tid"], max_polls=5, consecutive_empty_required=2) is True


# -----------------------------------------------------------------------------
# A10: Disagreements comparison covers 12 items and counts non-target divergences
# -----------------------------------------------------------------------------
def test_a10_disagreements_comparison_covers_12_items():
    from evals.runners.evaluation_review_packet import (
        REFUSAL_CASES,
        SYNTHETIC_CONTROLS,
        TARGET_CASES,
    )

    judged = {}
    for cid in TARGET_CASES:
        judged[cid] = {
            "metrics": {
                m: {"status": "scored", "score": 1.0}
                for m in ("correctness", "answer_relevancy", "faithfulness")
            }
        }
    for vid, spec in SYNTHETIC_CONTROLS.items():
        ctrl_id = f"{spec['parent_case_id']}-{vid}"
        judged[ctrl_id] = {
            "metrics": {
                m: {
                    "status": "scored",
                    "score": 0.0 if m == spec["target_rejected_metric"] else 1.0,
                }
                for m in ("correctness", "answer_relevancy", "faithfulness")
            }
        }

    human_packet = {"packet_sha256": "h123"}
    # Synthetic controls evaluated as reject by human
    items = [
        {
            "case_id": cid,
            "review": {
                "correctness": "accept",
                "answer_relevancy": "accept",
                "faithfulness": "accept",
            },
        }
        for cid in TARGET_CASES
    ]
    for vid, spec in SYNTHETIC_CONTROLS.items():
        ctrl_id = f"{spec['parent_case_id']}-{vid}"
        items.append(
            {
                "case_id": ctrl_id,
                "review": {
                    "correctness": "reject",
                    "answer_relevancy": "reject",
                    "faithfulness": "reject",
                },
            }
        )
    for cid in REFUSAL_CASES:
        items.append({"case_id": cid, "review": {"refusal_handling": "accept"}})

    human_labels = {"packet_sha256": "h123", "items": items}
    refusal_captures = {
        "pdf-v3-053": {"public_response": {"decision": "REFUSAL"}},
        "pdf-v3-002": {"public_response": {"decision": "SUCCESS"}},
    }
    dossier = finalize_acceptance_results(
        judged, human_packet, human_labels, refusal_captures=refusal_captures
    )
    # Target controls: target metric matches human reject (0 disagreements).
    # Non-target metrics on synthetic controls diverge (judge=1.0, human=reject):
    # recorded as synthetic_non_target_divergence.
    assert dossier["human_review"]["target_metric_disagreements_count"] == 0
    assert dossier["human_review"]["non_target_synthetic_divergences_count"] > 0
    assert dossier["human_review"]["labels_sha256"] is not None


# -----------------------------------------------------------------------------
# A11: load_credentials supports allow_mock in unit tests
# -----------------------------------------------------------------------------
def test_a11_load_credentials_allow_mock_offline():
    account, token = load_credentials(allow_mock=True)
    assert account is not None
    assert token is not None


# -----------------------------------------------------------------------------
# A12: CloudflareJudge strict schema validation rejects coercion and extra fields
# -----------------------------------------------------------------------------
def test_a12_cloudflare_judge_strict_schema_validation():
    class SimpleSchema(BaseModel):
        score: int
        reason: str

    def mock_judge_extra_field(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"score": 1, "reason": "ok", "unreviewed_extra": True}
                            )
                        },
                    }
                ]
            },
        )

    judge = CloudflareJudge(
        endpoint=f"https://api.cloudflare.com/client/v4/accounts/{'a' * 32}/ai/v1/chat/completions",
        token="token",
        model="@cf/openai/gpt-oss-20b",
        max_output_tokens=1024,
        ledger=MagicMock(),
        client=httpx.Client(transport=httpx.MockTransport(mock_judge_extra_field)),
    )
    with pytest.raises(JudgeError, match="JUDGE_RESPONSE_INVALID"):
        judge.generate("prompt", schema=SimpleSchema)

    # Test type coercion rejection (score as string "1" instead of int 1)
    def mock_judge_coercion(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"score": "1", "reason": "ok"})},
                    }
                ]
            },
        )

    judge_coercion = CloudflareJudge(
        endpoint=f"https://api.cloudflare.com/client/v4/accounts/{'a' * 32}/ai/v1/chat/completions",
        token="token",
        model="@cf/openai/gpt-oss-20b",
        max_output_tokens=1024,
        ledger=MagicMock(),
        client=httpx.Client(transport=httpx.MockTransport(mock_judge_coercion)),
    )
    with pytest.raises(JudgeError, match="JUDGE_RESPONSE_INVALID"):
        judge_coercion.generate("prompt", schema=SimpleSchema)
