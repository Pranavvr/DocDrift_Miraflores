# DocDrift — Specification

**Version:** 1.4 (MVP)
**Target:** Local Python CLI

*1.3: section selection now uses a token budget instead of a fixed section count (Step 2), and the model's context size is set explicitly (Step 3). A fixed "top 5" dropped sections that would have fit, and Ollama's small default context silently truncates long prompts.*

*1.4: G4 also rejects a suggestion identical to `doc_evidence` (a no-op fix passed every check in a gemma3:4b run of TC-07). Default model changed from `qwen3:8b` to `qwen3:4b`: the development machine has 8 GB RAM, where an 8B model doesn't run reliably, and a 4B model keeps the comparison with `gemma3:4b` like for like.*

## 1. Problem

When developers change code, they often forget to update the documentation, so README files end up describing behavior the code no longer has.

**Objective:** A local tool that takes a code diff and a README, identifies documentation the change may have made inaccurate, shows evidence, and suggests targeted corrections for human review.

**Core design principle:** the LLM interprets what a change *means*; Python code constrains what the LLM may conclude and propose. The tool must not assume every code change requires a doc update.

## 2. Scope

- Python source changes, given as a unified Git diff. Non-`.py` files in the diff are ignored and listed in the report.
- One Markdown file (`README.md`) per run.
- Docs about configuration, function behavior, parameters, and error handling.
- Local LLM inference via Ollama, plus a mock backend for tests.
- **One model call per run:** all relevant diff hunks and all selected doc sections are sent together in a single request.

The tool works only on the supplied files. It does not access GitHub or the full repository, and it never modifies input files.

## 3. CLI

    python main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md

| Option | Values | Default |
|---|---|---|
| `--format` | `markdown`, `json` | `markdown` |
| `--backend` | `ollama`, `mock` | `ollama` |
| `--model` | any locally pulled Ollama model | `qwen3:4b` (alternative: `gemma3:4b`) |
| `--mock-response` | path to a fixture JSON (mock backend only) | — |
| `--max-context` | largest context window (tokens) the tool may request | `32768` |

Output from the mock backend is labeled `[MOCK MODEL OUTPUT]` in the report.

### Exit codes

`0` = success and non-zero = failure is a universal convention; the specific meanings of 1–3 are defined by this tool.

| Code | Meaning | Example |
|---|---|---|
| `0` | Success (a report was produced, even one with stale findings) | Normal run |
| `1` | Invalid input file | Malformed diff, unreadable README, diff too large for one call |
| `2` | Bad command-line usage (argparse default, left as is) | `--formatt markdown` |
| `3` | Model backend unavailable or unusable output | Ollama not running, model not pulled, invalid JSON after retry |

## 4. Workflow

### Step 1 — Parse the diff (Python)
- Validate unified diff structure (file headers and hunk headers).
- Extract file paths and added, removed and context lines; keep the original lines for evidence checks.
- On malformed or unreadable input: clear error, exit code `1`, and the model is not called.

### Step 2 — Prepare documentation sections (Python)
- Split the README by Markdown headings. Content before the first heading is its own section.
- Give each section an ID (`s1`, `s2`, …).
- **Selection by token budget:** estimate tokens as characters ÷ 3 (deliberately conservative). The doc budget is `--max-context` minus the instructions, the diff, and a reserve for the model's answer.
  - If all sections fit, send all of them.
  - Otherwise rank sections by matches against identifiers and keywords from the changed code, and add them in rank order until the budget is used up. Sent sections keep document order.
  - If the instructions and diff alone exceed the budget, exit with code `1` (diff too large for one call).
- Sections not sent are listed in the report as "not analyzed", so nothing is skipped silently.

Sending everything that fits matters: many stale-doc cases share no identifier with the code change (see TC-07), so keyword ranking is only a fallback for docs too large for one call.

### Step 3 — Analyze (LLM)
Send the model:
- The relevant diff hunks.
- The selected sections with their IDs.
- Instructions to judge each section using only the supplied evidence.

The finding schema (Section 5) is passed to Ollama's structured-output option (the `format` parameter), so the model is forced to return JSON in that exact shape.

The context size (Ollama's `num_ctx` option) is set explicitly to fit the prompt plus the answer reserve, never above `--max-context`. Ollama's default context is small and silently truncates longer prompts.

Diff and doc contents are wrapped in clear delimiters and treated as **untrusted data, not instructions.**

If the output still can't be parsed, retry once with the parse error included. If it fails again, exit with code `3`.

If Ollama isn't running or the model isn't pulled, exit with code `3` and print setup instructions.

### Step 4 — Validate (Python)
Apply guardrails G1–G5 (Section 6) to every finding. Only Python sets `validation_status`.

**Schema vs. guardrails:** the schema guarantees the output is well-formed (fields exist, verdict is one of three values). It cannot know what is in the diff or README, so it cannot tell whether the content is true. The guardrails check content against the real inputs.

### Step 5 — Report (Python)
The Markdown report contains:
- Summary of analyzed changes (and ignored files), and any sections not analyzed because they didn't fit the budget.
- **Stale findings:** location, evidence, reason, and validated suggested fix.
- **Needs human review:** `unsure` findings.
- **Rejected findings:** with the guardrail and reason for each.
- If no section was judged affected, the report says "No documentation affected by this change was found in the supplied file," never "code and docs are fully consistent."

## 5. Finding Schema

The model returns a list of findings:

    {
      "section_id": "s2",
      "verdict": "stale",
      "diff_evidence": "+ MAX_RETRIES = 5",
      "doc_evidence": "The client retries 3 times.",
      "reason": "The documented retry count differs from the new default.",
      "suggested_text": "The client retries 5 times."
    }

- `verdict`: `stale` · `still_accurate` · `unsure`
- `suggested_text`: optional, and only meaningful for `stale`. It **replaces `doc_evidence`** within the flagged section.

Python adds:
- `validation_status`:
  - `passed`: all applicable guardrails pass.
  - `rejected`: any guardrail fails. Never shown as an accepted fix.
  - `not_applicable`: `still_accurate` or `unsure` findings, which have no fix to validate but still must pass G1–G3.
- `rejection_reason`: set when the status is `rejected`.

## 6. Guardrails (enforced in Python, never by the LLM)

**G1 — Section scope.** `section_id` must be one of the IDs sent to the model. Otherwise reject.
*Example:* sections sent are `s1`, `s2`, `s3`; a finding for `s9` is rejected.

**G2 — Verifiable evidence.** `diff_evidence` must match a line in the diff (the `+`/`-` prefix is optional) and `doc_evidence` must appear in the flagged section. Compare after normalizing whitespace and quote characters. Otherwise reject.

**G3 — Fixed verdicts.** Only the three verdicts are valid. For `unsure`, any `suggested_text` is discarded and the finding goes to "Needs human review." (This overlaps with the schema but is kept as a second check, since the mock backend bypasses Ollama's schema.)

**G4 — Contained edits.** `doc_evidence` must occur exactly once in the flagged section, so the replacement applies unambiguously (in memory only). The suggestion must also differ from `doc_evidence` after normalization; a fix that changes nothing is not a fix. Otherwise reject the suggestion.

**G5 — No unsupported values.** Any number or identifier in `suggested_text` that isn't in `doc_evidence` must appear in an added (`+`) line of the diff. Identifiers are tokens in backticks, snake_case, or CamelCase. Otherwise reject the suggestion.
*Example:* the diff adds `MAX_RETRIES = 5`; "retries 5 times" passes, "retries 10 times" is rejected.

A passing check confirms the evidence exists, not that the suggestion is semantically correct. Final judgment stays with a human.

## 7. Test Cases

Each case lives in `samples/tcNN/` with `change.diff` and `README.md`. Mock fixtures live in `tests/fixtures/`.

### Deterministic tests (automated, must always pass)

| ID | Input | Expected |
|---|---|---|
| **TC-03** Unsupported value | Retry count changes 3 → 5; mock output suggests "10 retries" | Suggestion `rejected` by G5; no accepted fix |
| **TC-04** Invalid diff | Malformed file with no valid headers or hunks | Clear error, exit code `1`, model not called |
| **TC-05** Bad section ID | Mock output references a section ID that wasn't supplied | Finding `rejected` by G1 |

**Unit tests** also cover diff parsing, section splitting, and each guardrail in both directions:
- **Bad input → rejected** (the guardrail fires).
- **Valid input → passed** (the guardrail doesn't fire by mistake). This prevents a broken validator that rejects everything from passing the tests.

### Evaluation cases (real model; run 3× each, results recorded in README)

| ID | Input | Expected |
|---|---|---|
| **TC-01** Stale | Function now returns `None`; README says it raises `KeyError` | `stale`, valid evidence, passing fix |
| **TC-02** Still accurate | Function gains an optional parameter; README examples still valid | `still_accurate`; no fix |
| **TC-06** Ambiguous | Config default changes, but runtime overrides may affect behavior | `unsure`; no accepted fix |
| **TC-07** No name match | `timeout=None` → `timeout=30`; README says "requests wait as long as the server takes" (never mentions "timeout") | `stale`, with a fix that passes G5 |

The real model's results vary from run to run, so these are reported honestly rather than asserted as strict pass/fail.

Run the evaluation cases on both `qwen3:4b` and `gemma3:4b` and record both in the results table, so the model choice is backed by results.

## 8. Out of Scope

- Languages other than Python
- Embeddings or vector databases
- Full-repository analysis
- Writing to README files or making Git commits
- Git hooks, CI/CD, GitHub Actions
- Agentic or multi-agent workflows
- Guaranteed detection of all inconsistencies

## 9. Done When

1. All deterministic tests pass.
2. Evaluation cases have been run against a real local model, with results recorded in the README.
3. The README covers setup, dependencies, sample commands, expected outputs, limitations, time spent, next steps, and AI-use disclosure.

Anything not implemented is listed in the README as deferred, never reported as complete.
