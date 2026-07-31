import argparse
import json
import time
import urllib.request
from pathlib import Path


def evaluate(dataset_path: Path, endpoint: str) -> dict:
    lines = dataset_path.read_text(encoding="utf-8-sig").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    results = []
    for case in cases:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                {"workspace_id": case["workspace_id"], "question": case["question"]}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request) as response:
            payload = json.load(response)
        sources = {citation["source"] for citation in payload["citations"]}
        expected_sources = set(case["expected_sources"])
        results.append(
            {
                "id": case["id"],
                "passed": payload["refused"] == case["expected_refused"]
                and expected_sources.issubset(sources),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "actual_sources": sorted(sources),
            }
        )
    return {
        "dataset": str(dataset_path),
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Knora HTTP evaluation dataset")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://localhost:8000/v1/questions")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = evaluate(args.dataset, args.endpoint)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['passed']}/{report['total']} cases passed; report={args.report}")


if __name__ == "__main__":
    main()
