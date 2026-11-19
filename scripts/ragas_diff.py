"""Compare two RAGAS runs per case. Never averages: a mean hides the case that moved.

    python scripts/ragas_diff.py artifacts/ragas/run-a.json artifacts/ragas/run-b.json

Exit code: 0 if every score and every trace verdict is identical, 1 if anything differs.
That makes it usable as a reproducibility check for two consecutive runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "evaluator"))

from evaluator.contract import METRIC_NAMES  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-case diff of two RAGAS runs")
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.0,
                        help="absolute difference considered equal (default 0)")
    args = parser.parse_args()

    a, b = load(args.first), load(args.second)
    print(f"A: {Path(args.first).name}  run_id={a['run']['run_id']}")
    print(f"B: {Path(args.second).name}  run_id={b['run']['run_id']}")
    print()

    by_case_b = {sample["case_id"]: sample for sample in b["samples"]}
    differences = 0
    header = f"{'case':32s}" + "".join(f"{name[:9]:>11s}" for name in METRIC_NAMES) + "  trace"
    print(header)
    print("-" * len(header))

    for sample in a["samples"]:
        case = sample["case_id"]
        other = by_case_b.get(case)
        row = f"{case:32s}"
        moved = False
        for name in METRIC_NAMES:
            left = sample["scores"].get(name)
            right = other["scores"].get(name) if other else None
            if left is None or right is None:
                cell = "n/a"
                moved = moved or left != right
            else:
                delta = round(right - left, 4)
                cell = f"{delta:+.4f}" if abs(delta) > args.tolerance else "0"
                moved = moved or abs(delta) > args.tolerance
            row += f"{cell:>11s}"
        trace_moved = bool(other) and sample.get("verdicts") != other.get("verdicts")
        row += "  moved" if trace_moved else ""
        differences += int(moved or trace_moved)
        print(row)

    print()
    print(f"{differences} case(s) differ; aggregate A={a['run']['aggregate']}")
    return 0 if differences == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
