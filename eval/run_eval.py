"""Run the real-model evaluation cases (SPEC section 7) and summarize the results.

Usage: python3 eval/run_eval.py [--models qwen3:4b gemma3:4b] [--runs 3]

Raw JSON reports go to eval/results/<model>/<case>_run<N>.json (timing and exit code in
<case>_run<N>.meta.json); the summary table is printed and written to eval/results/summary.md.
--regrade rebuilds the table from saved results without calling the model. The auto-grade below applies the expected outcome from
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


def grade(case: str, report: dict) -> tuple[bool, bool, str]:
    """Return (model verdict correct, tool outcome correct, findings summary).

    Model verdict: what the model said about the target section, before guardrails.
    Tool outcome: what the user ends up seeing after guardrails.
    """
    target = CASES[case][1]
    findings = report["findings"]
    said = {f["verdict"] for f in findings if f["section_id"] == target}
    on_target = [f for f in findings if f["section_id"] == target and f["validation_status"] != "rejected"]
    accepted_fixes = [f for f in findings if f["verdict"] == "stale" and f["validation_status"] == "passed"]
    verdicts = ", ".join(f"{f['section_id']}:{f['verdict']}/{f['validation_status']}" for f in findings) or "no findings"

    if case in ("tc01", "tc07"):
        model_ok = "stale" in said
        tool_ok = any(f["verdict"] == "stale" and f.get("suggested_text") for f in on_target) and \
            all(f["section_id"] == target for f in accepted_fixes)
    elif case == "tc02":
        model_ok = not said & {"stale", "unsure"}
        tool_ok = not accepted_fixes and not any(f["verdict"] == "unsure" for f in on_target)
    else:  # tc06
        model_ok = "unsure" in said and "stale" not in said
        tool_ok = any(f["verdict"] == "unsure" for f in on_target) and not accepted_fixes
    return model_ok, tool_ok, verdicts


def yes_no(ok: bool) -> str:
    return "yes" if ok else "**no**"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3:4b", "gemma3:4b"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--regrade", action="store_true", help="re-grade saved results without calling the model")
    args = ap.parse_args()

    rows = ["| Model | Case | Expected | Run | Model verdict correct | Tool outcome correct "
            "| Findings (section:verdict/status) | Seconds |",
            "|---|---|---|---|---|---|---|---|"]
    for model in args.models:
        out_dir = RESULTS / model.replace(":", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        for case, (expected, _) in CASES.items():
            for run in range(1, args.runs + 1):
                report_path = out_dir / f"{case}_run{run}.json"
                meta_path = out_dir / f"{case}_run{run}.meta.json"
                if not args.regrade:
                    start = time.time()
                    r = subprocess.run(
                        [sys.executable, "main.py", "--diff", f"samples/{case}/change.diff",
                         "--docs", f"samples/{case}/README.md", "--model", model, "--format", "json"],
                        cwd=ROOT, capture_output=True, text=True)
                    err = r.stderr.strip().splitlines()[-1] if r.returncode and r.stderr else ""
                    meta = {"exit": r.returncode, "seconds": round(time.time() - start), "error": err}
                    meta_path.write_text(json.dumps(meta) + "\n")
                    if r.returncode == 0:
                        report_path.write_text(r.stdout)
                meta = json.loads(meta_path.read_text())
                if meta["exit"] != 0:
                    cells = "ERROR | ERROR | " + f"exit {meta['exit']}: {meta['error']}"
                else:
                    model_ok, tool_ok, detail = grade(case, json.loads(report_path.read_text()))
                    cells = f"{yes_no(model_ok)} | {yes_no(tool_ok)} | {detail}"
                row = f"| {model} | {case} | {expected} | {run} | {cells} | {meta['seconds']} |"
                rows.append(row)
                print(row, flush=True)

    (RESULTS / "summary.md").write_text("\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
