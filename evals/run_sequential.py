"""Sequential eval driver — the same five evaluators, cases, and task
function as run_evals.py, driven case-by-case through the SDK's public
per-row evaluator API (Evaluator.evaluate(EvaluationData)) instead of
Experiment.run_evaluations.

Why this exists (2026-09-04): Experiment.run_evaluations reproducibly
hung at `await queue.join()` in this environment across THREE runs and
two different graph wirings — verbatim tracebacks in
agent-memory/evidence/evals-run3d.txt, evals-run3e-official.txt, and
evals-run4-official.txt (each exit 130 after SIGINT, each blocked at
experiment.py's queue.join) — while the identical graph + task function
completes per-case (168s single-case diagnostic) and the identical
judges scored correctly when the harness last finished (run 2). The
asyncio scheduling wrapper is the only difference; evaluators, judge
prompts, rubrics, cases, and the graph are untouched by this driver.
Results carry the same per-row fields the Experiment report carries.
"""

import json
import os
import sys
import traceback

from strands_evals.types.evaluation import EvaluationData

from evals.cases import test_cases
from evals.run_evals import (
    output_evaluator,
    run_case,
    safe_action_evaluator,
    tool_parameter_evaluator,
    tool_selection_evaluator,
    trajectory_evaluator,
)

os.environ["EVAL_MODE"] = "1"

EVALUATORS = [
    trajectory_evaluator,
    output_evaluator,
    tool_selection_evaluator,
    tool_parameter_evaluator,
    safe_action_evaluator,
]


def main() -> int:
    rows: list[dict] = []
    for index, case in enumerate(test_cases, start=1):
        print(f"[seq] case {index}/5: {case.name}", flush=True)
        try:
            out = run_case(case)
        except Exception as exc:  # record and continue — never hide a case
            print(f"[seq]   TASK FAILED: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            for evaluator in EVALUATORS:
                rows.append({
                    "case": case.name,
                    "evaluator": type(evaluator).__name__,
                    "score": 0.0,
                    "test_pass": False,
                    "reason": f"task function failed: {type(exc).__name__}: {exc}",
                    "label": "task-failure",
                })
            continue

        for evaluator in EVALUATORS:
            data = EvaluationData[dict, str](
                input=case.input,
                name=case.name,
                expected_output=case.expected_output,
                expected_trajectory=case.expected_trajectory,
                metadata=case.metadata,
                actual_output=out.get("output"),
                actual_trajectory=out.get("trajectory"),
            )
            try:
                outputs = evaluator.evaluate(data)
            except Exception as exc:
                print(f"[seq]   evaluator {type(evaluator).__name__} FAILED: {exc}", flush=True)
                traceback.print_exc()
                outputs = []
            for row in outputs:
                record = row.model_dump()
                record.update({"case": case.name, "evaluator": type(evaluator).__name__})
                rows.append(record)
                print(
                    f"[seq]   {type(evaluator).__name__}: pass={record.get('test_pass')} "
                    f"score={record.get('score')} label={record.get('label')}",
                    flush=True,
                )

    passed = sum(1 for r in rows if r.get("test_pass"))
    scores = [float(r.get("score") or 0.0) for r in rows]
    unsafe = [r for r in rows if r.get("label") == "unsafe"]
    summary = {
        "rows": len(rows),
        "passed": passed,
        "pass_rate": (passed / len(rows)) if rows else 0.0,
        "overall_score": (sum(scores) / len(scores)) if scores else 0.0,
        "unauthorized_action_attempts": len(unsafe),
        "per_evaluator": {},
    }
    for row in rows:
        bucket = summary["per_evaluator"].setdefault(
            row["evaluator"], {"rows": 0, "passed": 0}
        )
        bucket["rows"] += 1
        bucket["passed"] += 1 if row.get("test_pass") else 0

    print("\n[seq] === Sequential eval summary ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    with open("agent-memory/evidence/evals-sequential-results-2026-09-04.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2)
    print("[seq] full rows: agent-memory/evidence/evals-sequential-results-2026-09-04.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
