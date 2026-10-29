# Working Notes

Running log of limitations, shortcuts, model quirks and review changes. Feeds the README's
limitations / next steps / deferred sections and the AI-use statement.

## Limitations & shortcuts
- G2 diff_evidence: each quoted line must equal a diff line, or be a substring of one if >= 5 chars
  (models often quote part of a line). Very short fragments like "5" are rejected.
- Normalization drops backticks as well as unifying quotes/whitespace, so "raises KeyError" matches
  "raises `KeyError`". Slightly more lenient than the spec's "quote characters".
- G5 only looks at explicit tokens. "five" vs "5" isn't caught; an implicit value (e.g. `.get()`
  returning None without the word None in the diff) makes a correct fix fail G5.
- Section selection uses a token budget (spec 1.3): everything is sent when it fits. Token counts are
  estimated as chars/3, not measured with the model's tokenizer. Only when a README doesn't fit does
  plain keyword ranking decide what's sent (no stemming or synonyms), so TC-07-style misses are still
  possible for very large docs; those sections are listed as "not analyzed".
- num_ctx is sized to the prompt (power of two, 4096..--max-context). Bigger contexts cost RAM and
  small models read long inputs less reliably, so "fits" doesn't mean "read well".
- Model is told to skip unrelated sections rather than emit a finding for every section, to keep
  output small and avoid fake evidence for irrelevant sections.
- Schema wraps the list as {"findings": [...]} (Ollama structured output needs an object at the top);
  parser also accepts a bare list from the mock.
- A stale finding whose fix fails G4/G5 is reported under Rejected (no fix shown), not as stale-without-fix.
- If the diff contains no .py files, no model call is made and the report says nothing was found.

## Model behaviour observed

### Evaluation, 2026-10-29 (3 runs x 4 cases x 2 models, M2 / 8 GB; table in eval/results/summary.md)
| | Model verdict correct | Tool outcome correct |
|---|---|---|
| qwen3:4b | 6/12 | 9/12 |
| gemma3:4b | 2/12 (1 timeout) | 3/12 (1 timeout) |

- qwen3:4b: TC-01 and TC-07 3/3 (TC-07 is the no-shared-words case). ~20-45 s/run (measured 18-47 s).
- TC-02: both models wrongly said "stale" 6/6 times; guardrails rejected every fix, so the tool
  outcome was right. qwen's rejection came from garbled backticks tripping G5, with a confusing
  reason, so partly luck.
- TC-06: both models fail. qwen confidently suggests "logs at `WARNING`", which passes every
  guardrail: evidence is real and WARNING is in the diff. Guardrails can't see that the env-var
  override makes this uncertain. KNOWN LIMITATION; prompt tweak deferred (revisit if time).
- gemma3:4b: mostly no-op fixes, empty evidence, wrong sections. Guardrails rejected nearly all
  of it: never a wrong accepted fix in TC-01/02/07. Weak model + guardrails = unhelpful, not misleading.
- One gemma run timed out (300 s HTTP timeout) right after switching from qwen; likely the 8 GB
  machine swapping models. Recorded as ERROR.
- Grader scores two things separately: the model's verdict on the target section (before
  guardrails) and what the user sees (after). Expected outcomes are applied mechanically; raw
  JSON is kept for every run so each grade can be checked by hand.
- qwen3:4b with thinking on: TC-01 correct but 4 min 48 s. With think=false: ~30 s, same result.
  think=false is sent only to models whose /api/show capabilities include "thinking"; sending it
  to gemma3:4b made a trivial request hang for 5+ minutes.
- 2026-10-29, gemma3:4b, M2 / 8 GB RAM: ~95 s cold, ~60 s warm per run.
- TC-01 (gemma3:4b): correct stale finding on s3 with a fix that passed. Also a duplicate finding
  pointing at s1 with s3's text; G2 rejected it. Model included the heading line in doc_evidence.
- TC-07 (gemma3:4b): the real stale sentence (s2) was found, but the model quoted the README as
  diff_evidence, so G2 rejected it. It also marked s1 ("Download web pages from scripts.") stale with
  suggested_text identical to doc_evidence, and that passed: no guardrail catches a no-op fix.

## Review changes (AI output changed or rejected)

## Next steps to investigate
- TC-06 / overconfidence: prompt the model to look for overrides (env vars, config files, call-site
  arguments) before saying "stale"; or a Python check that flags stale findings when the diff
  context shows `os.environ`/config lookups near the changed value, downgrading them to unsure.
- G5 backtick parsing breaks on unbalanced backticks; reject malformed suggestions with a clear reason.
- Larger eval set: real commits from open-source repos, not hand-made samples.
