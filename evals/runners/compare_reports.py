from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.runners.evaluation import normalize_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare evaluation reports without wall-clock observations"
    )
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    first = normalize_report(json.loads(args.first.read_text(encoding="utf-8")))
    second = normalize_report(json.loads(args.second.read_text(encoding="utf-8")))
    if first != second:
        print("normalized reports differ")
        return 1
    print("normalized reports are identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
