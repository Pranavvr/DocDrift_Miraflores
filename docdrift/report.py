"""Step 5: render the report as Markdown or JSON."""

import json

NOTHING_FOUND = "No documentation affected by this change was found in the supplied file."
NOTHING_VERIFIED = ("No finding passed validation. The model flagged sections it could not back with "
                    "evidence; see Rejected findings.")


def closing_message(g: dict[str, list[dict]]) -> str | None:
    if g["stale"] or g["review"]:
        return None
    if any(f.get("verdict") in ("stale", "unsure") for f in g["rejected"]):
        return NOTHING_VERIFIED
    return NOTHING_FOUND


def group(findings: list[dict]) -> dict[str, list[dict]]:
    groups = {"stale": [], "review": [], "accurate": [], "rejected": []}
    for f in findings:
        if f["validation_status"] == "rejected":
            groups["rejected"].append(f)
        elif f["verdict"] == "stale":
            groups["stale"].append(f)
        elif f["verdict"] == "unsure":
            groups["review"].append(f)
        else:
            groups["accurate"].append(f)
    return groups


def _one_line(text: str) -> str:
    """Model text can span lines (e.g. a heading plus a sentence); keep it inside its bullet."""
    return " ".join(text.split())


def _location(f: dict, headings: dict[str, str]) -> str:
    heading = headings.get(f.get("section_id"), "")
    return f"`{f.get('section_id')}`" + (f" ({heading})" if heading else " (before first heading)")


def render_markdown(ctx: dict) -> str:
    findings = ctx["findings"]
    headings = {s.id: s.heading for s in ctx["sections"]}
    g = group(findings)
    out = ["# DocDrift report", ""]
    if ctx["is_mock"]:
        out += ["**[MOCK MODEL OUTPUT]** Findings come from a fixture file, not a real model.", ""]

    out += ["## Summary", "",
            f"- Diff: `{ctx['diff_path']}` | Docs: `{ctx['docs_path']}` | Model: `{ctx['model']}`",
            f"- Python files analyzed: {', '.join(f'`{f.path}`' for f in ctx['diff'].files) or 'none'}",
            f"- Ignored (non-.py) files: {', '.join(f'`{p}`' for p in ctx['diff'].ignored) or 'none'}",
            f"- Sections sent to model: {len(ctx['sent'])} of {len(ctx['sections'])} "
            f"({', '.join(s.id for s in ctx['sent'])})",
            f"- Not analyzed (didn't fit the context budget): "
            f"{', '.join(f'{s.id} ({s.heading})' for s in ctx['not_sent']) or 'none'}",
            f"- Findings: {len(g['stale'])} stale, {len(g['review'])} need review, "
            f"{len(g['accurate'])} still accurate, {len(g['rejected'])} rejected", ""]

    out += ["## Stale findings", ""]
    if not g["stale"]:
        out += ["None.", ""]
    for f in g["stale"]:
        out += [f"### {_location(f, headings)}", "",
                f"- **Diff evidence:** `{_one_line(f['diff_evidence'])}`",
                f"- **Doc evidence:** \"{_one_line(f['doc_evidence'])}\"",
                f"- **Reason:** {f['reason']}"]
        if f.get("suggested_text"):
            out += [f"- **Suggested fix** (guardrails passed; review before applying):", "",
                    f"  > {_one_line(f['suggested_text'])}"]
        else:
            out += ["- **Suggested fix:** none provided"]
        out.append("")

    out += ["## Needs human review", ""]
    if not g["review"]:
        out += ["None.", ""]
    for f in g["review"]:
        out += [f"- {_location(f, headings)}: {f['reason']}",
                f"  - Diff: `{_one_line(f['diff_evidence'])}` | Doc: \"{_one_line(f['doc_evidence'])}\""]
    if g["review"]:
        out.append("")

    if g["accurate"]:
        out += ["## Still accurate", ""]
        out += [f"- {_location(f, headings)}: {f['reason']}" for f in g["accurate"]]
        out.append("")

    out += ["## Rejected findings", ""]
    if not g["rejected"]:
        out += ["None.", ""]
    for f in g["rejected"]:
        out += [f"- {_location(f, headings)} ({f.get('verdict')}): **{_one_line(f['rejection_reason'])}**",
                f"  - Model's reason: {f.get('reason', '')}"]
    if g["rejected"]:
        out.append("")

    if closing_message(g):
        out += ["---", "", closing_message(g), ""]
    out += ["_Guardrails confirm the evidence exists, not that a fix is semantically correct. "
            "A human makes the final call._"]
    return "\n".join(out) + "\n"


def render_json(ctx: dict) -> str:
    g = group(ctx["findings"])
    data = {
        "mock": ctx["is_mock"],
        "model": ctx["model"],
        "diff": ctx["diff_path"],
        "docs": ctx["docs_path"],
        "python_files": [f.path for f in ctx["diff"].files],
        "ignored_files": ctx["diff"].ignored,
        "sections_sent": [s.id for s in ctx["sent"]],
        "sections_not_analyzed": [s.id for s in ctx["not_sent"]],
        "findings": ctx["findings"],
        "summary": {k: len(v) for k, v in g.items()},
    }
    if closing_message(g):
        data["message"] = closing_message(g)
    return json.dumps(data, indent=2) + "\n"
