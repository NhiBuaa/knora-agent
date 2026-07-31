import io
import json
import urllib.request

from evals.runners.run_http_eval import evaluate


class StubHttpResponse(io.BytesIO):
    def __enter__(self) -> "StubHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_evaluate_accepts_utf8_bom_and_blank_lines(tmp_path, monkeypatch) -> None:
    dataset = tmp_path / "dataset.jsonl"
    case = {
        "id": "refund-window",
        "workspace_id": "demo",
        "question": "Thời hạn hoàn tiền?",
        "expected_sources": ["refund-policy.md"],
        "expected_refused": False,
    }
    dataset.write_text(f"{json.dumps(case)}\n\n", encoding="utf-8-sig")
    response = {
        "answer": "Trong vòng 30 ngày.",
        "citations": [{"source": "refund-policy.md"}],
        "refused": False,
    }
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request: StubHttpResponse(json.dumps(response).encode()),
    )

    report = evaluate(dataset, "http://knora.test/v1/questions")

    assert report["total"] == 1
    assert report["passed"] == 1

