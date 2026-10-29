"""DocDrift CLI. See SPEC.md and README.md."""

import argparse
import sys

from docdrift.analyze import analyze
from docdrift.backends import MockBackend, OllamaBackend
from docdrift.budget import ANSWER_RESERVE, MIN_CONTEXT, estimate_tokens
from docdrift.diff_parser import read_diff
from docdrift.errors import BackendError, InputError
from docdrift.guardrails import validate
from docdrift.prompt import SYSTEM_PROMPT, build_user_prompt
from docdrift.report import render_json, render_markdown
from docdrift.sections import read_sections, select_sections


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Flag README sections a code diff may have made inaccurate.")
    p.add_argument("--diff", required=True, help="unified Git diff file")
    p.add_argument("--docs", required=True, help="Markdown README file")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument("--backend", choices=["ollama", "mock"], default="ollama")
    p.add_argument("--model", default="qwen3:8b", help="locally pulled Ollama model (default: qwen3:8b)")
    p.add_argument("--mock-response", help="fixture JSON returned by the mock backend")
    p.add_argument("--max-context", type=int, default=32768,
                   help="largest context window (tokens) to request from the model (default: 32768)")
    return p


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.backend == "mock" and not args.mock_response:
        parser.error("--backend mock requires --mock-response")
    if args.backend != "mock" and args.mock_response:
        parser.error("--mock-response is only valid with --backend mock")
    if args.max_context < MIN_CONTEXT:
        parser.error(f"--max-context must be at least {MIN_CONTEXT}")

    try:
        # Inputs are fully validated before any backend is created or called.
        diff = read_diff(args.diff)
        sections = read_sections(args.docs)
        code_lines = [l[1:] for l in diff.all_lines()]
        fixed = estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(build_user_prompt(diff, [])) + ANSWER_RESERVE
        budget = args.max_context - fixed
        if budget <= 0:
            raise InputError(f"diff too large for one call (~{fixed} tokens with instructions and answer "
                             f"reserve; --max-context is {args.max_context})")
        sent, not_sent = select_sections(sections, code_lines, budget)

        if args.backend == "mock":
            backend = MockBackend(args.mock_response)
        else:
            backend = OllamaBackend(args.model)

        if not diff.files:
            findings = []  # nothing to analyze: no model call
        else:
            backend.check_available()
            findings = [validate(f, sent, diff) for f in analyze(backend, diff, sent, args.max_context)]
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except BackendError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    ctx = {
        "diff_path": args.diff, "docs_path": args.docs, "diff": diff, "sections": sections,
        "sent": sent, "not_sent": not_sent, "findings": findings, "is_mock": backend.is_mock, "model": backend.model,
    }
    print(render_json(ctx) if args.format == "json" else render_markdown(ctx), end="")
    return 0


if __name__ == "__main__":
    sys.exit(run())
