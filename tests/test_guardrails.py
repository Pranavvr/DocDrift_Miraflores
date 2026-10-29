"""Each guardrail is tested in both directions: bad input is rejected, valid input passes."""

from docdrift import guardrails as g
from docdrift.diff_parser import parse_diff
from docdrift.sections import split_sections

DIFF = parse_diff("""--- a/client.py
+++ b/client.py
@@ -1,3 +1,3 @@
 import time
-MAX_RETRIES = 3
+MAX_RETRIES = 5
 BACKOFF_SECONDS = 2
""")
SECTIONS = split_sections(
    "# Client\nA client.\n\n## Retries\n\n"
    "The client retries 3 times, waiting “2” seconds.\n"
    "Set `max_retries` to change this. Set `max_retries` per call.\n"
)
SECTION = SECTIONS[1]


def finding(**kw):
    base = {
        "section_id": "s2",
        "verdict": "stale",
        "diff_evidence": "+ MAX_RETRIES = 5",
        "doc_evidence": "The client retries 3 times",
        "reason": "count changed",
        "suggested_text": "The client retries 5 times",
    }
    base.update(kw)
    return base


# G1
def test_g1_rejects_unknown_section():
    ok, reason = g.check_section_scope({"section_id": "s9"}, {"s1", "s2"})
    assert not ok and reason.startswith("G1")


def test_g1_passes_sent_section():
    assert g.check_section_scope({"section_id": "s2"}, {"s1", "s2"}) == (True, "")


# G2
def test_g2_rejects_diff_evidence_not_in_diff():
    ok, reason = g.check_diff_evidence("+MAX_RETRIES = 10", DIFF)
    assert not ok and reason.startswith("G2")


def test_g2_rejects_tiny_partial_diff_evidence():
    assert not g.check_diff_evidence("5", DIFF)[0]


def test_g2_passes_diff_evidence_with_or_without_prefix():
    assert g.check_diff_evidence("+ MAX_RETRIES = 5", DIFF)[0]
    assert g.check_diff_evidence("MAX_RETRIES   =   5", DIFF)[0]
    assert g.check_diff_evidence("-MAX_RETRIES = 3\n+MAX_RETRIES = 5", DIFF)[0]


def test_g2_rejects_doc_evidence_not_in_section():
    ok, reason = g.check_doc_evidence("The client retries 4 times", SECTION)
    assert not ok and reason.startswith("G2")


def test_g2_passes_doc_evidence_after_whitespace_and_quote_normalization():
    assert g.check_doc_evidence('retries 3   times, waiting "2" seconds', SECTION)[0]


# G3
def test_g3_rejects_invalid_verdict():
    ok, reason = g.check_verdict({"verdict": "probably_stale"})
    assert not ok and reason.startswith("G3")


def test_g3_passes_valid_verdicts():
    for v in ("stale", "still_accurate", "unsure"):
        assert g.check_verdict({"verdict": v})[0]


def test_g3_unsure_discards_suggestion():
    out = g.validate(finding(verdict="unsure"), SECTIONS, DIFF)
    assert out["validation_status"] == "not_applicable"
    assert "suggested_text" not in out


# G4
def test_g4_rejects_ambiguous_evidence():
    ok, reason = g.check_contained_edit("Set `max_retries`", SECTION)
    assert not ok and reason.startswith("G4")


def test_g4_passes_unique_evidence():
    assert g.check_contained_edit("The client retries 3 times", SECTION)[0]


# G5
def test_g5_rejects_value_not_in_added_lines():
    ok, reason = g.check_supported_values("The client retries 10 times", "The client retries 3 times", DIFF)
    assert not ok and "'10'" in reason


def test_g5_rejects_removed_value_and_unknown_identifier():
    assert not g.check_supported_values("Set `retry_limit`", "Set it", DIFF)[0]
    assert not g.check_supported_values("Uses RetryPolicy", "Uses it", DIFF)[0]


def test_g5_passes_values_from_added_lines_or_doc_evidence():
    assert g.check_supported_values("The client retries 5 times", "The client retries 3 times", DIFF)[0]
    assert g.check_supported_values("`MAX_RETRIES` is 5, waiting 2 seconds", "waiting 2 seconds", DIFF)[0]


def test_g5_number_match_is_whole_token():
    diff = parse_diff("--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-X = 1\n+X = 15\n")
    assert not g.check_supported_values("waits 5 seconds", "waits", diff)[0]


# validate(): statuses
def test_validate_passed():
    out = g.validate(finding(), SECTIONS, DIFF)
    assert out["validation_status"] == "passed"
    assert "rejection_reason" not in out


def test_validate_stale_without_fix_passes():
    out = g.validate(finding(suggested_text=""), SECTIONS, DIFF)
    assert out["validation_status"] == "passed"


def test_validate_still_accurate_is_not_applicable_but_checks_evidence():
    assert g.validate(finding(verdict="still_accurate"), SECTIONS, DIFF)["validation_status"] == "not_applicable"
    bad = g.validate(finding(verdict="still_accurate", doc_evidence="invented"), SECTIONS, DIFF)
    assert bad["validation_status"] == "rejected"


def test_validate_ignores_status_from_model():
    out = g.validate(finding(section_id="s9", validation_status="passed"), SECTIONS, DIFF)
    assert out["validation_status"] == "rejected"
    assert out["rejection_reason"].startswith("G1")
