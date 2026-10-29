"""Step 3: one model call (plus at most one retry on unparseable output)."""

import json

from docdrift.errors import BackendError
from docdrift.prompt import FINDING_SCHEMA, SYSTEM_PROMPT, build_user_prompt

FIELDS = ("section_id", "verdict", "diff_evidence", "doc_evidence", "reason")


def parse_findings(raw: str) -> list[dict]:
    """Parse model output into a list of finding dicts. Raises ValueError with a readable message."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"output is not valid JSON: {e}") from e
    if isinstance(data, dict):
        data = data.get("findings")
    if not isinstance(data, list):
        raise ValueError('expected {"findings": [...]}')
    for n, f in enumerate(data):
        if not isinstance(f, dict):
            raise ValueError(f"finding {n} is not an object")
        missing = [k for k in FIELDS if not isinstance(f.get(k), str)]
        if missing:
            raise ValueError(f"finding {n} is missing string field(s): {', '.join(missing)}")
        if "suggested_text" in f and f["suggested_text"] is not None and not isinstance(f["suggested_text"], str):
            raise ValueError(f"finding {n}: suggested_text must be a string")
    return data


def analyze(backend, diff, sections) -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(diff, sections)},
    ]
    raw = backend.chat(messages, FINDING_SCHEMA)
    try:
        return parse_findings(raw)
    except ValueError as first_error:
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"Your output could not be used: {first_error}. "
                                        'Return only JSON of the form {"findings": [...]}.'},
        ]
        raw = backend.chat(messages, FINDING_SCHEMA)
        try:
            return parse_findings(raw)
        except ValueError as e:
            raise BackendError(f"model output unusable after retry: {e}") from e
