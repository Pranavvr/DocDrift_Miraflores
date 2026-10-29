"""Step 2: split the README into sections and select which to send."""

import re
from dataclasses import dataclass

from docdrift.errors import InputError

HEADING_RE = re.compile(r"^#{1,6}\s+\S")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STOPWORDS = {
    "def", "return", "self", "none", "true", "false", "import", "from", "class",
    "if", "else", "elif", "for", "in", "not", "and", "or", "is", "the", "with", "as",
    "raise", "try", "except", "pass", "str", "int", "dict", "list",
}
SMALL_DOC_LIMIT = 8
TOP_K = 5


@dataclass
class Section:
    id: str
    heading: str  # "" for content before the first heading
    text: str  # full section text, including the heading line


def split_sections(text: str) -> list[Section]:
    sections: list[list[str]] = [[]]
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and HEADING_RE.match(line):
            sections.append([line])
        else:
            sections[-1].append(line)
    if not "".join(sections[0]).strip():
        sections = sections[1:]  # no content before the first heading
    result = []
    for n, lines in enumerate(sections, start=1):
        heading = lines[0].lstrip("#").strip() if HEADING_RE.match(lines[0]) else ""
        result.append(Section(id=f"s{n}", heading=heading, text="\n".join(lines).strip("\n")))
    return result


def keywords(code_lines: list[str]) -> set[str]:
    words = set()
    for line in code_lines:
        for w in WORD_RE.findall(line):
            w = w.lower()
            if len(w) > 2 and w not in STOPWORDS:
                words.add(w)
                words.update(p for p in w.split("_") if len(p) > 2 and p not in STOPWORDS)
    return words


def select_sections(sections: list[Section], code_lines: list[str]) -> list[Section]:
    """Send everything for small docs; otherwise the top 5 by keyword matches."""
    if len(sections) <= SMALL_DOC_LIMIT:
        return sections
    kw = keywords(code_lines)

    def score(s: Section) -> int:
        return sum(1 for w in WORD_RE.findall(s.text.lower()) if w in kw)

    ranked = sorted(sections, key=lambda s: -score(s))  # stable: ties keep document order
    top = ranked[:TOP_K]
    return sorted(top, key=lambda s: int(s.id[1:]))


def read_sections(path: str) -> list[Section]:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read docs file {path}: {e}") from e
    sections = split_sections(text)
    if not sections:
        raise InputError(f"docs file {path} is empty")
    return sections
