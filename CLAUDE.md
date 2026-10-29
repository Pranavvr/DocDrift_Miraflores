# DocDrift — instructions for Claude Code

`SPEC.md` is the source of truth. If something is unclear or missing, ask; don't guess.
Don't copy the spec here: it's the only place requirements live.

## Commands

- Tests: `python3 -m pytest -q`
- Run: `python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md`
- Mock run: add `--backend mock --mock-response tests/fixtures/<file>.json`
- Demo: `./demo.sh` (representative case + invalid input)

## Rules

- Standard library only; `pytest` is the only dev dependency. Ollama is called over HTTP with `urllib`.
- Keep code plain and small. It has to be explained and changed live, so no clever abstractions.
- The LLM interprets; Python decides. Only `guardrails.py` sets `validation_status`.
- Each guardrail is a pure function returning `(ok, reason)`, and each has a test that rejects bad input and one that passes valid input.
- Exit codes exactly as in SPEC §3: 1 bad input, 2 usage, 3 backend. Input errors must exit before any model call.
- Never write to input files.

## Workflow

- Commit after each step that leaves the tests passing. Short imperative messages, no AI attribution or co-author lines.
- Time: when the user says "start", "break" or "stop", append the `date` time to `TIMELOG.md`.
- Log limitations, shortcuts, model quirks and review changes in `NOTES.md` as they come up.
- Anything not implemented goes in the README as deferred, never as done.
