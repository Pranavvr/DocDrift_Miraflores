"""Run the real-model evaluation cases (SPEC section 7) and summarize the results.

Usage: python3 eval/run_eval.py [--models qwen3:4b gemma3:4b] [--runs 3]

Raw JSON reports go to eval/results/<model>/<case>_run<N>.json; the summary table is printed
and written to eval/results/summary.md. The auto-grade below applies the expected outcome from
the spec mechanically; raw outputs are kept so every grade can be checked by hand.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"

# case -> (expected outcome, section the README change is about)
CASES = {
    "tc01": ("stale + passing fix", "s3"),
    "tc02": ("still_accurate, no fix", "s2"),
    "tc06": ("unsure, no accepted fix", "s2"),
    "tc07": ("stale + passing fix", "s2"),
}


def grade(case: str, report: dict) -> tuple[bool, str]:
    target = CASES[case][1]
    findings = report["findings"]
    on_target = [f for f in findings if f["section_id"] == target and f["validation_status"] != "rejected"]
    accepted_fixes = [f for f in findings if f["verdict"] == "stale" and f["validation_status"] == "passed"]
    verdicts = ", ".join(f"{f['section_id']}:{f['verdict']}/{f['validation_status']}" for f in findings) or "no findings"

    if case in ("tc01", "tc07"):
        ok = any(f["verdict"] == "stale" and f.get("suggested_text") for f in on_target) and \
            all(f["section_id"] == target for f in accepted_fixes)
    elif case == "tc02":
        ok = not accepted_fixes and not any(f["verdict"] == "unsure" for f in on_target)
    else:  # tc06
        ok = any(f["verdict"] == "unsure" for f in on_target) and not accepted_fixes
    return ok, verdicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3:4b", "gemma3:4b"])
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    rows = ["| Model | Case | Expected | Run | Result | Findings (section:verdict/status) | Seconds |",
            "|---|---|---|---|---|---|---|"]
    for model in args.models:
        out_dir = RESULTS / model.replace(":", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        for case, (expected, _) in CASES.items():
            for run in range(1, args.runs + 1):
                start = time.time()
                r = subprocess.run(
                    [sys.executable, "main.py", "--diff", f"samples/{case}/change.diff",
                     "--docs", f"samples/{case}/README.md", "--model", model, "--format", "json"],
                    cwd=ROOT, capture_output=True, text=True)
                secs = round(time.time() - start)
                if r.returncode != 0:
                    result, detail = "ERROR", f"exit {r.returncode}: {r.stderr.strip().splitlines()[-1] if r.stderr else ''}"
                else:
                    (out_dir / f"{case}_run{run}.json").write_text(r.stdout)
                    ok, detail = grade(case, json.loads(r.stdout))
                    result = "pass" if ok else "fail"
                row = f"| {model} | {case} | {expected} | {run} | {result} | {detail} | {secs} |"
                rows.append(row)
                print(row, flush=True)

    (RESULTS / "summary.md").write_text("\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
