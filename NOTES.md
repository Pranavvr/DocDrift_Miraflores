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
- Section ranking (>8 sections) is plain keyword overlap; no stemming or synonyms.
- Model is told to skip unrelated sections rather than emit a finding for every section, to keep
  output small and avoid fake evidence for irrelevant sections.
- Schema wraps the list as {"findings": [...]} (Ollama structured output needs an object at the top);
  parser also accepts a bare list from the mock.
- A stale finding whose fix fails G4/G5 is reported under Rejected (no fix shown), not as stale-without-fix.
- If the diff contains no .py files, no model call is made and the report says nothing was found.

## Model behaviour observed

## Review changes (AI output changed or rejected)

## Next steps to investigate
