# DocDrift

A local command-line tool that takes a code diff and a README, flags README sections the change may have made inaccurate, shows the evidence, and suggests targeted fixes for a human to review.

**Design principle:** the LLM interprets what a change *means*; Python decides what the LLM is allowed to conclude. Every model finding passes through five guardrails (G1–G5) that check its evidence against the real inputs before anything is shown as an accepted fix. The tool never modifies input files.

Full requirements: [`SPEC.md`](SPEC.md) (v1.4; changes from v1.2 are noted at the top with reasons).

## Setup

Requirements:
- **Python 3.10+**. No runtime dependencies (standard library only).
- **pytest**, only to run the tests.
- **[Ollama](https://ollama.com/download)**, only for real-model runs. The mock backend needs nothing.

```bash
git clone https://github.com/Pranavvr/DocDrift_Miraflores.git
cd DocDrift_Miraflores
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# For real-model runs:
ollama serve              # if Ollama isn't already running
ollama pull qwen3:4b      # default model (~2.5 GB)
ollama pull gemma3:4b     # optional, for comparison
```

## Run

No Ollama? `./demo.sh` still runs: it falls back to the labelled mock backend, and `pytest` needs no model. On Windows, use WSL, or run the three commands from `demo.sh` directly.

```bash
./demo.sh                 # representative case, guardrail rejection, invalid input (~30 s)

python3 -m pytest -q      # 56 deterministic tests, no model needed

# Real model (default qwen3:4b)
python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md

# Mock model (labeled [MOCK MODEL OUTPUT]; no Ollama needed)
python3 main.py --diff samples/tc01/change.diff --docs samples/tc01/README.md \
  --backend mock --mock-response tests/fixtures/tc01_stale.json

# On your own code
git diff > change.diff
python3 main.py --diff change.diff --docs README.md
```

| Option | Values | Default |
|---|---|---|
| `--format` | `markdown`, `json` | `markdown` |
| `--backend` | `ollama`, `mock` | `ollama` |
| `--model` | any pulled Ollama model | `qwen3:4b` |
| `--mock-response` | fixture JSON (mock only) | — |
| `--max-context` | largest context window to request (tokens) | `32768` |

Exit codes: `0` report produced · `1` invalid input file (model not called) · `2` bad command-line usage · `3` model backend unavailable or unusable output.

## How it works

```
change.diff ─► diff_parser ─┐
                            ├─► prompt ─► ONE model call ─► guardrails G1–G5 ─► report
README.md ──► sections ─────┘   (schema-forced JSON,           (Python only)
              (token budget)     retry once on bad output)
```

| Guardrail | Rejects a finding when… |
|---|---|
| **G1** Section scope | it names a section that wasn't sent to the model |
| **G2** Verifiable evidence | its quoted diff line or README text doesn't exist (after normalizing whitespace and quotes) |
| **G3** Fixed verdicts | its verdict isn't `stale` / `still_accurate` / `unsure`; `unsure` never carries a fix |
| **G4** Contained edits | the quoted README text isn't unique in its section, or the fix is identical to it |
| **G5** No unsupported values | the fix introduces a number or identifier that isn't in the original text or an added diff line |

Passing the guardrails confirms the evidence exists, not that the fix is right. A human makes the final call.

## Sample data and expected outputs

Each case is in `samples/tcNN/` (`change.diff` + `README.md`). Mock fixtures are in `tests/fixtures/`.

| Case | Input | Expected |
|---|---|---|
| TC-01 | `get_setting` now returns `None`; README says it raises `KeyError` | `stale`, passing fix |
| TC-02 | `greet` gains an optional parameter; README still valid | `still_accurate`, no fix |
| TC-03 | retries 3 → 5; mock suggests "10 retries" | fix rejected by G5 *(automated test)* |
| TC-04 | not a diff | error, exit 1, model not called *(automated test)* |
| TC-05 | mock cites section `s9`, which wasn't sent | rejected by G1 *(automated test)* |
| TC-06 | log-level default changes; env var may override it | `unsure`, no accepted fix |
| TC-07 | `timeout=None` → `30`; README says "requests wait as long as the server takes" (never says "timeout") | `stale`, fix passes G5 |

Example (TC-01, abbreviated):

```
## Stale findings
### `s3` (Error handling)
- Diff evidence: `+ return None`
- Doc evidence: "`get_setting(name)` raises `KeyError` if the setting does not exist."
- Suggested fix (guardrails passed; review before applying):
  > `get_setting(name)` returns `None` if the setting does not exist.
```

## Evaluation results (real models)

TC-01, 02, 06 and 07 were run 3× on each model, on an Apple M2 with 8 GB RAM, using `python3 eval/run_eval.py`. Every raw report is in `eval/results/`, and the per-run table is in [`eval/results/summary.md`](eval/results/summary.md).

Each run is graded twice: is the **model's verdict** right (before guardrails), and is the **tool's outcome** right (what the user sees after guardrails)?

| Case | qwen3:4b model / tool | gemma3:4b model / tool |
|---|---|---|
| TC-01 stale | 3/3 · 3/3 | 2/3 · 0/3 (1 timeout) |
| TC-02 still accurate | 0/3 · 3/3 | 0/3 · 3/3 |
| TC-06 unsure | 0/3 · 0/3 | 0/3 · 0/3 |
| TC-07 stale, no name match | 3/3 · 3/3 | 0/3 · 0/3 |
| **Total** | **6/12 · 9/12** | **2/12 · 3/12** |

What this shows:
- **qwen3:4b is the better choice,** and that's why it's the default. It solved the hard no-shared-words case (TC-07) every time, in about 20–45 s per run.
- **Guardrails add real value.** On TC-02 both models wrongly called the README stale in all 6 runs, and every one of those fixes was rejected. gemma3:4b produced mostly unsupported output (no-op fixes, empty evidence, wrong sections), and the guardrails rejected nearly all of it. A weak model ends up unhelpful rather than misleading.
- **Main weakness: overconfidence on ambiguous changes (TC-06).** qwen3:4b confidently suggests "logs at `WARNING`". The evidence is real and `WARNING` is in the diff, so every guardrail passes, but an environment variable may override the default. Guardrails check evidence, not judgement.

Model notes: `qwen3:8b` (the original default) was replaced by `qwen3:4b` because an 8B model doesn't run reliably in 8 GB RAM, and a 4B model keeps the comparison with `gemma3:4b` like for like. qwen3's hidden "thinking" step made runs take about 5 minutes, so it's turned off for models that report the capability.

## Implemented, mocked, deferred

**Implemented:** everything in SPEC v1.4. That covers diff validation, README sectioning, token-budget section selection with explicit context size, one model call with schema-forced JSON and one retry, guardrails G1–G5, Markdown/JSON reports, exit codes, 56 tests and the evaluation runner.

**Mocked:** the model, in automated tests and as a demo fallback (`--backend mock`). Mock output is always labeled `[MOCK MODEL OUTPUT]`. All sample diffs and READMEs are **synthetic**.

**Deferred:**
- TC-06 prompt improvement (see next steps)
- READMEs too large for one call (would need several calls; the spec requires one call per run)
- Languages other than Python, more than one docs file, writing fixes back to files, CI/git-hook integration

## Limitations

- **Guardrails verify evidence, not meaning.** A fix can pass every check and still be wrong (TC-06).
- **Token counts are estimated** (characters ÷ 3), not measured with the model's tokenizer. Only READMEs too large for one call fall back to keyword ranking, which can miss sections that describe behavior in different words. Those are listed as "not analyzed", not skipped silently.
- **G5 only sees explicit values.** It doesn't catch "five" vs. "5". A correct fix can fail if the diff implies a value without stating it (e.g. `.get()` returning `None` implicitly).
- **Small local models are slow and inconsistent:** 20–80 s per run on 8 GB RAM, with variable results between runs.
- Evaluated on 7 hand-made cases, not real-world commits.

## Next steps

1. **Overconfidence (TC-06):** prompt the model to look for overrides (env vars, config files, call-site arguments) before saying "stale". Or add a Python check that downgrades a stale finding to `unsure` when the diff shows an `os.environ`/config lookup next to the changed value.
2. **Real-world evaluation:** run on commits from open-source projects where the README was later fixed, to measure misses as well as false alarms.
3. **G5 robustness:** reject malformed suggestions (e.g. unbalanced backticks) with a clear reason.
4. **Large docs:** split across several calls, or retrieve sections by meaning rather than keywords.

## Time spent

**About 3h44m in total**, over two sessions, breaks excluded:

| Block | Time |
|---|---|
| Ideation + `SPEC.md` (2026-10-28) | 40 min |
| Setup, development, testing, evaluation, README (2026-10-29) | 2h10m |
| Explanation write-up + final check | 54 min |

Details in [`TIMELOG.md`](TIMELOG.md).

## AI use

- **Design (mine):** I identified the problem and wrote `SPEC.md` before any code: the core principle, finding schema, guardrails G1–G5, exit codes, test cases and evaluation plan.
- **Implementation (AI-assisted):** Claude Code (Anthropic) turned the spec into code and tests, ran the evaluation, and drafted this README, working under standing instructions I set in [`CLAUDE.md`](CLAUDE.md).
- **Direction and review (mine):**
  - I reviewed the code module by module and changed the design where it fell short. I replaced the spec's fixed "top 5 sections" rule with a token budget, because real READMEs exceed that limit.
  - I changed the default model after measuring hardware limits.
  - I added the no-op fix check after a real run exposed the gap.
  - Each change was made to the spec first (v1.3, v1.4) and committed before the code.
  - I also caught and corrected AI errors along the way, including a requirement it misattributed to the spec and a commit made outside the agreed workflow.
- **How the output was checked:**
  - 56 deterministic tests, with every guardrail tested both rejecting bad input and passing good input
  - real-model evaluation with raw outputs kept
  - grading the model's verdict separately from the tool's outcome
  - manual reading of the reports
- **Prior work reused:** none. The spec and all code were written for this exercise.
