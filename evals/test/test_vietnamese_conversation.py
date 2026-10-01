import asyncio
import hashlib
from dataclasses import replace
from importlib import import_module

import pytest
from evals.datasets.vietnamese_rag_v1 import VietnameseCase, VietnameseDataset


def evaluate(dataset, rows, reviews=()):
    try:
        module = import_module("evals.runners.vietnamese_conversation")
    except ModuleNotFoundError as error:
        if error.name != "evals.runners.vietnamese_conversation":
            raise
        pytest.fail("Conversation regression evaluator is missing")
    return module.evaluate_observations(dataset, rows, reviews, runtime_binding=binding())


def binding():
    return dict(
        retrieval_configuration_id="candidate",
        context_policy_id="context-v2",
        model="qwen3:8b",
        prompt_version="v3",
        generation_model_digest="sha256:" + "b" * 64,
        prompt_sha256="c" * 64,
    )


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def dataset():
    return VietnameseDataset(
        (
            VietnameseCase(
                "answer",
                "How many?",
                "source.pdf",
                2,
                ("a" * 64,),
                ("qualified count",),
                "ANSWER",
                "held_out",
            ),
            VietnameseCase(
                "absent", "What fee?", "source.pdf", None, (), (), "REFUSAL", "held_out"
            ),
        ),
        "test-v2",
        "d" * 64,
        "profile",
        "sha256:" + "e" * 64,
        "c" * 64,
        ("set",),
        "candidate",
    )


def rows():
    common = dict(
        **binding(),
        embedding_profile_id="profile",
        status="answered",
        structural_valid=True,
        generation_status="completed",
        provider="ollama",
        question_sha256=digest("How many?"),
        answer_sha256=digest("Three, except two."),
    )
    return [
        dict(
            common,
            case_id="answer",
            turn_id="turn-answer",
            trace_id="trace-answer",
            result_trace_id="trace-answer",
            decision="ANSWER",
            citations=[dict(source_key="source.pdf", page_start=2, content_checksum="a" * 64)],
        ),
        dict(
            common,
            case_id="absent",
            turn_id="turn-absent",
            trace_id="trace-absent",
            result_trace_id="trace-absent",
            status="refused",
            decision="REFUSAL",
            citations=[],
            question_sha256=digest("What fee?"),
            answer_sha256=digest(""),
        ),
    ]


def review(passed=True, observed=None):
    from evals.runners.vietnamese_conversation import response_sha256

    return [
        dict(
            case_id="answer",
            response_sha256=response_sha256(dataset(), (observed or rows())[0]),
            passed=passed,
            reason="qualified_count_and_support_reviewed",
        )
    ]


def test_structural_and_checksum_hits_cannot_claim_semantic_pass():
    result = evaluate(dataset(), rows())
    assert result["status"] == "AWAITING_SEMANTIC_REVIEW"
    assert result["decision_correct_count"] == 2
    assert result["citation_gold_hit_count"] == 1
    assert result["model_refusal_count"] == 1
    assert result["release_gate"] == "NOT_EVALUATED"


def test_exact_response_bound_semantic_review_is_required_to_pass():
    assert evaluate(dataset(), rows(), review())["status"] == "REGRESSION_PASSED"
    assert evaluate(dataset(), rows(), review(False))["status"] == "REGRESSION_FAILED"
    stale = [{**review()[0], "response_sha256": "f" * 64}]
    with pytest.raises(ValueError, match="review"):
        evaluate(dataset(), rows(), stale)


@pytest.mark.parametrize("change", ["missing", "duplicate", "question", "profile"])
def test_missing_duplicate_or_mismatched_observations_cannot_publish(change):
    observed = rows()
    if change == "missing":
        observed.pop()
    elif change == "duplicate":
        observed.append(observed[0])
    elif change == "question":
        observed[0]["question_sha256"] = digest("different question")
    else:
        observed[0]["embedding_profile_id"] = "other profile"
    with pytest.raises(ValueError, match="observation"):
        evaluate(dataset(), observed)


def test_wrong_page_or_unsupported_answer_does_not_pass_on_checksum_alone():
    observed = rows()
    observed[0]["citations"][0]["page_start"] = 3
    assert evaluate(dataset(), observed, review(observed=observed))["status"] == "REGRESSION_FAILED"
    observed = rows()
    observed[1].update(decision="ANSWER", status="answered")
    assert evaluate(dataset(), observed, review())["status"] == "REGRESSION_FAILED"


def test_pre_generation_refusal_is_reported_separately_from_model_refusal():
    observed = rows()
    observed[1].update(generation_status="not_called", provider=None)
    result = evaluate(dataset(), observed, review())
    assert result["pre_generation_refusal_count"] == 1
    assert result["model_refusal_count"] == 0


def test_extra_semantic_review_cannot_be_reused_for_another_dataset():
    with pytest.raises(ValueError, match="review"):
        evaluate(replace(dataset(), cases=dataset().cases[1:]), rows()[1:], review())


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora_dev",
        "postgresql+psycopg://knora:knora@remote:5432/knora_issue105_eval",
        "sqlite:///knora_issue105_eval",
        "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora_issue105_eval?dbname=knora_dev",
        "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora_issue105_eval?host=remote",
    ],
)
def test_live_runner_refuses_unisolated_or_remote_database(url):
    module = import_module("evals.runners.vietnamese_conversation")
    with pytest.raises(ValueError, match="isolated"):
        module.validate_evaluation_database(url)


def test_live_collection_creates_a_new_conversation_and_keeps_exact_questions():
    from types import SimpleNamespace

    module = import_module("evals.runners.vietnamese_conversation")

    class Store:
        def __init__(self):
            self.questions = []

        def create(self, workspace_id, key):
            return SimpleNamespace(id="new-evaluation-conversation")

        def submit_turn(self, **command):
            assert command["conversation_id"] == "new-evaluation-conversation"
            self.questions.append(command["question"])
            return SimpleNamespace(turn=SimpleNamespace(id=f"turn-{len(self.questions)}"))

        def get_turn(self, workspace_id, conversation_id, turn_id):
            return SimpleNamespace(id=turn_id, question=self.questions[-1], status="answered")

    class Runner:
        async def run_once(self, **command):
            assert command["workspace_id"] == "workspace"
            return True

    store = Store()
    recorded = []
    result = asyncio.run(
        module.collect_conversation_cases(
            dataset(),
            store=store,
            runner=Runner(),
            workspace_id="workspace",
            read_observation=lambda case, turn: {"case_id": case.id, "question": turn.question},
            record=lambda row: recorded.append(row),
        )
    )
    assert store.questions == [case.question for case in dataset().cases]
    assert result["conversation_id"] == "new-evaluation-conversation"
    assert result["observations"] == recorded


def test_failed_turn_still_produces_an_observation_instead_of_a_partial_report():
    from types import SimpleNamespace

    module = import_module("evals.runners.vietnamese_conversation")

    class Store:
        def create(self, *args):
            return SimpleNamespace(id="evaluation")

        def submit_turn(self, **command):
            self.question = command["question"]
            return SimpleNamespace(turn=SimpleNamespace(id="failed-turn"))

        def get_turn(self, *args):
            return SimpleNamespace(id="failed-turn", question=self.question, status="failed")

    class Runner:
        async def run_once(self, **command):
            return False

    result = asyncio.run(
        module.collect_conversation_cases(
            dataset(),
            store=Store(),
            runner=Runner(),
            workspace_id="workspace",
            read_observation=lambda case, turn: {"case_id": case.id, "status": turn.status},
            record=lambda row: None,
        )
    )
    assert len(result["observations"]) == 2
    assert all(row["status"] == "failed" for row in result["observations"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("trace_id", None),
        ("provider", "deterministic-local"),
        ("generation_status", "not_called"),
        ("retrieval_configuration_id", "other"),
    ],
)
def test_unproven_runtime_cannot_pass(field, value):
    observed = rows()
    observed[0][field] = value
    with pytest.raises(ValueError, match="provenance"):
        evaluate(dataset(), observed, review())


def test_changed_citation_invalidates_existing_semantic_review():
    observed = rows()
    observed[0]["citations"][0]["evidence_id"] = "E9"
    with pytest.raises(ValueError, match="review"):
        evaluate(dataset(), observed, review())


def test_code_provenance_rejects_uncommitted_runtime(tmp_path):
    import subprocess

    module = import_module("evals.runners.vietnamese_conversation")
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "runtime.py").write_text("first\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    provenance = module.code_provenance(tmp_path)
    assert len(provenance["git_commit"]) == 40
    assert len(provenance["git_tree"]) == 40
    (tmp_path / "runtime.py").write_text("changed\n")
    with pytest.raises(ValueError, match="committed"):
        module.code_provenance(tmp_path)


def test_private_output_rejected_in_git_checkout_even_from_other_cwd(tmp_path, monkeypatch):
    import subprocess

    module = import_module("evals.runners.vietnamese_conversation")
    checkout = tmp_path / "repo"
    subprocess.run(["git", "init", str(checkout)], check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        module.validate_private_output(checkout / "new" / "responses.json")
    module.validate_private_output(tmp_path / "private" / "responses.json")


def test_calibration_can_be_reused_only_for_same_corpus_and_profile():
    module = import_module("evals.runners.vietnamese_conversation")
    module.validate_calibration_target(dataset(), replace(dataset(), dataset_sha256="f" * 64))
    with pytest.raises(ValueError, match="corpus"):
        module.validate_calibration_target(dataset(), replace(dataset(), corpus_sha256="f" * 64))
