"""Phase-4 runner: capture live agent behaviour, score it, load the rows.

    python evals/run_phase4.py capture
    python evals/run_phase4.py score --captured artifacts/phase4/captured.jsonl
    python evals/run_phase4.py load --report artifacts/phase4/ragas/<run>.json \
        --trajectory artifacts/phase4/trajectory.json --dry-run

The ADK trajectory eval is separate and official:

    adk eval support_agent evals/support_agent_v1.evalset.json \
        --config_file_path evals/test_config.json --num_runs 1 --print_detailed_results

Capture is a second inference run on purpose: ADK's evaluator does not expose the
retrieved contexts, and RAGAS needs them. See evals/README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from eval_support import (  # noqa: E402
    build_bq_rows,
    case_expected_tools,
    case_kind,
    case_question,
    case_reference,
    compare_trajectory,
    load_evalset,
    write_json,
    write_jsonl,
)

EVALSET = SERVICE_ROOT / "evals" / "support_agent_v1.evalset.json"
OUT = SERVICE_ROOT / "artifacts" / "phase4"


async def _capture_case(case) -> tuple[dict, dict]:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from support_agent.agent import root_agent
    from support_agent.config import settings

    question = case_question(case)
    session_id = case.eval_id
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="phase4", user_id="eval", session_id=session_id
    )
    runner = Runner(app_name="phase4", agent=root_agent, session_service=sessions)
    message = types.Content(role="user", parts=[types.Part(text=question)])

    actual_tools: list[str] = []
    contexts: list[str] = []
    retrieved_ids: list[str] = []
    answer = ""

    async for event in runner.run_async(
        user_id="eval", session_id=session_id, new_message=message
    ):
        for part in event.content.parts if event.content else []:
            if part.function_call:
                actual_tools.append(part.function_call.name)
            if part.function_response:
                name = part.function_response.name
                response = part.function_response.response or {}
                if name == "search_knowledge" and response.get("status") == "ok":
                    for passage in response.get("passages", []):
                        contexts.append(str(passage.get("content", "")))
                        retrieved_ids.append(str(passage.get("id", "")))
                elif name == "lookup_record" and response.get("status") == "ok":
                    asset = response.get("asset") or {}
                    contexts.append(json.dumps(asset, sort_keys=True))
                    retrieved_ids.append(str(asset.get("asset_id", "")))
            if part.text and part.text.strip():
                answer = part.text.strip()

    expected_tools = case_expected_tools(case)
    comparison = compare_trajectory(expected_tools, actual_tools)

    captured = {
        "case_id": case.eval_id,
        "split": "phase4",
        "case_kind": case_kind(case),
        "question": question,
        "contexts": contexts,
        "retrieved_ids": [item for item in retrieved_ids if item],
        "answer": answer,
        "reference": case_reference(case),
        "generation_mode": "adk-live",
        "model": settings.agent_model,
    }
    trajectory = {
        "case_id": case.eval_id,
        "case_kind": case_kind(case),
        "question": question,
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "exact": comparison["exact"],
        "in_order": comparison["in_order"],
        "missing": comparison["missing"],
        "unexpected": comparison["unexpected"],
        "answer": answer,
        "model": settings.agent_model,
    }
    return captured, trajectory


async def _capture_all(evalset_path: Path, limit: int | None) -> None:
    eval_set = load_evalset(evalset_path)
    cases = eval_set.eval_cases[:limit] if limit else eval_set.eval_cases
    captured_rows = []
    trajectory: dict[str, dict] = {}

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.eval_id}")
        captured, trace = await _capture_case(case)
        captured_rows.append(captured)
        trajectory[case.eval_id] = trace
        print(f"  tools: {trace['actual_tools']}")
        print(f"  exact={trace['exact']} in_order={trace['in_order']}")
        print(f"  answer: {captured['answer'][:160]}")

    write_jsonl(OUT / "captured.jsonl", captured_rows)
    write_json(OUT / "trajectory.json", trajectory)
    exact = sum(1 for row in trajectory.values() if row["exact"])
    print(f"\ncaptured {len(captured_rows)} cases; exact trajectories {exact}/{len(cases)}")
    print(f"wrote {OUT / 'captured.jsonl'}")
    print(f"wrote {OUT / 'trajectory.json'}")


def _ragas_eligible(captured: Path) -> Path:
    """RAGAS needs contexts; trajectory-only cases (not-found, out-of-domain) are skipped."""
    rows = [
        json.loads(line)
        for line in captured.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    eligible = [row for row in rows if row.get("contexts")]
    if len(eligible) == len(rows):
        return captured

    target = captured.with_name(captured.stem + "-ragas.jsonl")
    write_jsonl(target, eligible)
    skipped = [row["case_id"] for row in rows if not row.get("contexts")]
    print(f"RAGAS: skipping {len(skipped)} case(s) with no contexts: {', '.join(skipped)}")
    return target


def _score(captured: Path, arm: str, label: str, out: Path, skip_trace: bool) -> Path:
    script = ROOT / "scripts" / "ragas_run.py"
    dataset = _ragas_eligible(captured)
    command = [
        sys.executable,
        str(script),
        "--dataset",
        str(dataset),
        "--arm",
        arm,
        "--label",
        label,
        "--out",
        str(out),
    ]
    if skip_trace:
        command.append("--skip-trace")
    subprocess.run(command, check=True)
    reports = sorted(out.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if not reports:
        raise SystemExit(f"no RAGAS report found in {out}")
    return reports[-1]


def _load(report_path: Path, trajectory_path: Path, args) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    rows = build_bq_rows(report, trajectory, report_date=args.report_date)

    if args.dry_run:
        print(json.dumps(rows, indent=2))
        return

    from google.cloud import bigquery

    project = args.project or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("set --project or GOOGLE_CLOUD_PROJECT")
    table = f"{project}.{args.dataset}.{args.table}"
    errors = bigquery.Client(project=project).insert_rows_json(table, rows)
    if errors:
        raise SystemExit(f"BigQuery insert failed: {errors}")
    print(f"loaded {len(rows)} rows into {table}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="run the agent and record answers/contexts")
    capture.add_argument("--evalset", type=Path, default=EVALSET)
    capture.add_argument("--limit", type=int)

    score = sub.add_parser("score", help="run the RAGAS/Vertex arm over the capture")
    score.add_argument("--captured", type=Path, default=OUT / "captured.jsonl")
    score.add_argument("--arm", choices=("vertex", "openai"), default="vertex")
    score.add_argument("--label", default="phase4-agent")
    score.add_argument("--out", type=Path, default=OUT / "ragas")
    score.add_argument("--skip-trace", action="store_true")

    load = sub.add_parser("load", help="shape rows and insert them into BigQuery")
    load.add_argument("--report", type=Path, required=True)
    load.add_argument("--trajectory", type=Path, default=OUT / "trajectory.json")
    load.add_argument("--project", default="")
    load.add_argument("--dataset", default="ai_platform")
    load.add_argument("--table", default="eval_reports")
    load.add_argument("--report-date", default=None)
    load.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "capture":
        asyncio.run(_capture_all(args.evalset, args.limit))
    elif args.command == "score":
        report = _score(args.captured, args.arm, args.label, args.out, args.skip_trace)
        print(f"report: {report}")
    else:
        _load(args.report, args.trajectory, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
