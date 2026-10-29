"""Deterministic end-to-end cases (SPEC section 7) and exit codes."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import main
from docdrift.backends import MockBackend, OllamaBackend
from docdrift.analyze import parse_findings

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
SAMPLES = ROOT / "samples"


def run_cli(*args):
    return subprocess.run([sys.executable, "main.py", *args], cwd=ROOT, capture_output=True, text=True)


def mock_json(case, fixture):
    r = run_cli("--diff", f"samples/{case}/change.diff", "--docs", f"samples/{case}/README.md",
                "--backend", "mock", "--mock-response", f"tests/fixtures/{fixture}", "--format", "json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_tc03_unsupported_value_rejected_by_g5():
    out = mock_json("tc03", "tc03_unsupported_value.json")
    [f] = out["findings"]
    assert f["validation_status"] == "rejected"
    assert f["rejection_reason"].startswith("G5")
    assert out["summary"]["stale"] == 0  # no accepted fix
    assert out["message"].startswith("No finding passed validation")  # not "no documentation affected"


def test_tc04_invalid_diff_exits_1_without_calling_model(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("model must not be called")
    monkeypatch.setattr(MockBackend, "chat", boom)
    monkeypatch.setattr(OllamaBackend, "chat", boom)
    monkeypatch.setattr(OllamaBackend, "check_available", boom)
    for backend in (["--backend", "mock", "--mock-response", str(FIX / "tc01_stale.json")], []):
        code = main.run(["--diff", str(SAMPLES / "tc04" / "change.diff"),
                         "--docs", str(SAMPLES / "tc04" / "README.md"), *backend])
        assert code == 1
        assert "error:" in capsys.readouterr().err


def test_tc05_unknown_section_rejected_by_g1():
    out = mock_json("tc05", "tc05_bad_section.json")
    [f] = out["findings"]
    assert f["validation_status"] == "rejected"
    assert f["rejection_reason"].startswith("G1")


def test_tc01_mock_valid_fix_passes():
    out = mock_json("tc01", "tc01_stale.json")
    [f] = out["findings"]
    assert f["validation_status"] == "passed"
    assert out["mock"] is True


def test_markdown_report_labels_mock_output():
    r = run_cli("--diff", "samples/tc01/change.diff", "--docs", "samples/tc01/README.md",
                "--backend", "mock", "--mock-response", "tests/fixtures/tc01_stale.json")
    assert "[MOCK MODEL OUTPUT]" in r.stdout


def test_no_findings_message(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text('{"findings": []}')
    r = run_cli("--diff", "samples/tc02/change.diff", "--docs", "samples/tc02/README.md",
                "--backend", "mock", "--mock-response", str(empty))
    assert "No documentation affected by this change was found in the supplied file." in r.stdout
    assert "fully consistent" not in r.stdout


def test_bad_usage_exits_2():
    assert run_cli("--diff", "x", "--docs", "y", "--formatt", "markdown").returncode == 2
    assert run_cli("--diff", "x", "--docs", "y", "--backend", "mock").returncode == 2


def test_unusable_model_output_exits_3_after_retry(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all")
    r = run_cli("--diff", "samples/tc01/change.diff", "--docs", "samples/tc01/README.md",
                "--backend", "mock", "--mock-response", str(bad))
    assert r.returncode == 3
    assert "after retry" in r.stderr


def test_ollama_unreachable_exits_3_with_setup_help(monkeypatch, capsys):
    monkeypatch.setattr("docdrift.backends.OLLAMA_URL", "http://127.0.0.1:9")
    code = main.run(["--diff", str(SAMPLES / "tc01" / "change.diff"), "--docs", str(SAMPLES / "tc01" / "README.md")])
    assert code == 3
    assert "ollama pull" in capsys.readouterr().err


def test_input_files_are_not_modified():
    paths = [SAMPLES / "tc01" / "change.diff", SAMPLES / "tc01" / "README.md"]
    before = [p.read_bytes() for p in paths]
    run_cli("--diff", "samples/tc01/change.diff", "--docs", "samples/tc01/README.md",
            "--backend", "mock", "--mock-response", "tests/fixtures/tc01_stale.json")
    assert [p.read_bytes() for p in paths] == before


def test_diff_too_large_for_one_call_exits_1(tmp_path):
    added = "".join(f"+value_{n} = {n}  # padding to make the diff large\n" for n in range(400))
    big = tmp_path / "big.diff"
    big.write_text(f"--- a/big.py\n+++ b/big.py\n@@ -0,0 +1,400 @@\n{added}")
    r = run_cli("--diff", str(big), "--docs", "samples/tc01/README.md", "--max-context", "4096",
                "--backend", "mock", "--mock-response", "tests/fixtures/tc01_stale.json")
    assert r.returncode == 1
    assert "too large" in r.stderr


def test_sections_that_dont_fit_are_reported_not_analyzed(tmp_path):
    docs = tmp_path / "README.md"
    docs.write_text("\n".join(f"# Part {i}\n" + "lorem ipsum " * 150 for i in range(6)))
    empty = tmp_path / "empty.json"
    empty.write_text('{"findings": []}')
    r = run_cli("--diff", "samples/tc01/change.diff", "--docs", str(docs), "--max-context", "4096",
                "--backend", "mock", "--mock-response", str(empty), "--format", "json")
    out = json.loads(r.stdout)
    assert out["sections_not_analyzed"]
    assert len(out["sections_sent"]) + len(out["sections_not_analyzed"]) == 6


def test_max_context_below_minimum_is_usage_error():
    assert run_cli("--diff", "x", "--docs", "y", "--max-context", "100").returncode == 2


@pytest.mark.parametrize("raw",['{"findings": [{"section_id": "s1"}]}', '{"other": []}', "[1]"])
def test_parse_findings_rejects_bad_shapes(raw):
    with pytest.raises(ValueError):
        parse_findings(raw)


def test_parse_findings_accepts_object_or_list():
    f = {"section_id": "s1", "verdict": "stale", "diff_evidence": "a", "doc_evidence": "b", "reason": "c"}
    assert parse_findings(json.dumps({"findings": [f]})) == [f]
    assert parse_findings(json.dumps([f])) == [f]


def test_multiline_evidence_stays_on_one_report_line(tmp_path):
    fixture = tmp_path / "multi.json"
    fixture.write_text(json.dumps({"findings": [{
        "section_id": "s3", "verdict": "stale", "diff_evidence": "+        return None",
        "doc_evidence": "## Error handling\n`get_setting(name)` raises `KeyError` if the setting does not exist.",
        "reason": "now returns None",
        "suggested_text": "## Error handling\n`get_setting(name)` returns `None` if the setting does not exist."}]}))
    r = run_cli("--diff", "samples/tc01/change.diff", "--docs", "samples/tc01/README.md",
                "--backend", "mock", "--mock-response", str(fixture))
    assert '- **Doc evidence:** "## Error handling `get_setting(name)` raises' in r.stdout
    assert "\n## Error handling" not in r.stdout.split("## Stale findings")[1]
