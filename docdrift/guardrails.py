"""Step 4: guardrails G1-G5 (SPEC section 6). Only this module sets validation_status.

Each check is a pure function returning (ok, reason). `validate` applies them in order.
"""

import re

from docdrift.diff_parser import ParsedDiff
from docdrift.sections import Section

VERDICTS = {"stale", "still_accurate", "unsure"}
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "`": ""})
MIN_DIFF_EVIDENCE = 5  # shortest diff_evidence (chars) allowed to match part of a diff line

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
BACKTICK_RE = re.compile(r"`([^`]+)`")
SNAKE_RE = re.compile(r"\b[A-Za-z0-9]*_[A-Za-z0-9_]*\b")
CAMEL_RE = re.compile(r"\b[A-Za-z]+[a-z0-9][A-Z][A-Za-z0-9]*\b|\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b")


def normalize(text: str) -> str:
    """Collapse whitespace and unify quote characters (backticks are dropped)."""
    return " ".join(text.translate(QUOTES).split())


def strip_diff_prefix(line: str) -> str:
    return line[1:] if line[:1] in "+-" else line


# --- G1 ---------------------------------------------------------------------

def check_section_scope(finding: dict, sent_ids: set[str]) -> tuple[bool, str]:
    sid = finding.get("section_id")
    if sid in sent_ids:
        return True, ""
    return False, f"G1: section_id {sid!r} was not sent to the model (sent: {', '.join(sorted(sent_ids))})"


# --- G2 ---------------------------------------------------------------------

def check_diff_evidence(evidence: str, diff: ParsedDiff) -> tuple[bool, str]:
    pieces = [normalize(strip_diff_prefix(p.strip())) for p in evidence.splitlines() if p.strip()]
    if not pieces:
        return False, "G2: diff_evidence is empty"
    diff_lines = [normalize(l[1:]) for l in diff.all_lines()]
    for piece in pieces:
        exact = piece in diff_lines
        partial = len(piece) >= MIN_DIFF_EVIDENCE and any(piece in l for l in diff_lines)
        if not (exact or partial):
            return False, f"G2: diff_evidence {piece!r} not found in the diff"
    return True, ""


def check_doc_evidence(evidence: str, section: Section) -> tuple[bool, str]:
    needle = normalize(evidence)
    if not needle:
        return False, "G2: doc_evidence is empty"
    if needle not in normalize(section.text):
        return False, f"G2: doc_evidence {evidence!r} not found in section {section.id}"
    return True, ""


# --- G3 ---------------------------------------------------------------------

def check_verdict(finding: dict) -> tuple[bool, str]:
    if finding.get("verdict") in VERDICTS:
        return True, ""
    return False, f"G3: invalid verdict {finding.get('verdict')!r}"


# --- G4 ---------------------------------------------------------------------

def check_contained_edit(evidence: str, section: Section) -> tuple[bool, str]:
    count = normalize(section.text).count(normalize(evidence))
    if count == 1:
        return True, ""
    return False, f"G4: doc_evidence occurs {count} times in section {section.id}; replacement is ambiguous"


# --- G5 ---------------------------------------------------------------------

def value_tokens(text: str) -> set[str]:
    """Numbers and identifiers (backticked, snake_case, CamelCase) in text."""
    tokens = set(NUMBER_RE.findall(text))
    tokens.update(t.strip() for t in BACKTICK_RE.findall(text))
    plain = BACKTICK_RE.sub(" ", text)
    tokens.update(SNAKE_RE.findall(plain))
    tokens.update(CAMEL_RE.findall(plain))
    return {t for t in tokens if t and t != "_"}


def _contains_token(haystack: str, token: str) -> bool:
    return re.search(r"(?<![\w.])" + re.escape(token) + r"(?![\w])", haystack) is not None


def check_supported_values(suggested: str, doc_evidence: str, diff: ParsedDiff) -> tuple[bool, str]:
    added = "\n".join(diff.added_lines())
    evidence = doc_evidence.replace("`", "")
    for token in sorted(value_tokens(suggested)):
        if _contains_token(evidence, token) or _contains_token(added, token):
            continue
        return False, f"G5: {token!r} in suggested_text is not in doc_evidence or any added diff line"
    return True, ""


# --- apply all ----------------------------------------------------------------

def validate(finding: dict, sections: list[Section], diff: ParsedDiff) -> dict:
    """Return a copy of finding with validation_status (and rejection_reason) set."""
    f = dict(finding)
    f.pop("validation_status", None)  # never trust a status coming from the model
    f.pop("rejection_reason", None)
    by_id = {s.id: s for s in sections}

    def reject(reason: str) -> dict:
        f["validation_status"] = "rejected"
        f["rejection_reason"] = reason
        return f

    for ok, reason in (check_section_scope(f, set(by_id)), check_verdict(f)):
        if not ok:
            return reject(reason)
    section = by_id[f["section_id"]]

    for ok, reason in (
        check_diff_evidence(f.get("diff_evidence", ""), diff),
        check_doc_evidence(f.get("doc_evidence", ""), section),
    ):
        if not ok:
            return reject(reason)

    if f["verdict"] != "stale":
        f.pop("suggested_text", None)  # G3: no fix for unsure / still_accurate
        f["validation_status"] = "not_applicable"
        return f

    suggested = (f.get("suggested_text") or "").strip()
    if suggested:
        for ok, reason in (
            check_contained_edit(f["doc_evidence"], section),
            check_supported_values(suggested, f["doc_evidence"], diff),
        ):
            if not ok:
                return reject(reason)
    f["validation_status"] = "passed"
    return f
