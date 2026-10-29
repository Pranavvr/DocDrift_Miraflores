"""Step 1: parse and validate a unified Git diff."""

import re
from dataclasses import dataclass, field

from docdrift.errors import InputError

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    header: str
    lines: list[str] = field(default_factory=list)  # original lines, with +/-/space prefix

    @property
    def added(self) -> list[str]:
        return [l[1:] for l in self.lines if l.startswith("+")]

    @property
    def removed(self) -> list[str]:
        return [l[1:] for l in self.lines if l.startswith("-")]


@dataclass
class FileDiff:
    path: str
    hunks: list[Hunk] = field(default_factory=list)


@dataclass
class ParsedDiff:
    files: list[FileDiff]  # .py files only
    ignored: list[str]  # non-.py paths

    def all_lines(self) -> list[str]:
        return [l for f in self.files for h in f.hunks for l in h.lines]

    def added_lines(self) -> list[str]:
        return [l for f in self.files for h in f.hunks for l in h.added]


def _strip_path(raw: str) -> str:
    path = raw.split("\t")[0].strip()
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def parse_diff(text: str) -> ParsedDiff:
    """Parse a unified diff. Raises InputError on malformed input."""
    lines = text.splitlines()
    files: list[FileDiff] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("--- "):
            i += 1  # skip "diff --git", "index ..." and other preamble
            continue
        if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
            raise InputError(f"line {i + 1}: '---' header not followed by '+++' header")
        old_path = _strip_path(lines[i][4:])
        new_path = _strip_path(lines[i + 1][4:])
        current = FileDiff(path=new_path if new_path != "/dev/null" else old_path)
        i += 2

        while i < len(lines) and lines[i].startswith("@@"):
            m = HUNK_RE.match(lines[i])
            if not m:
                raise InputError(f"line {i + 1}: malformed hunk header: {lines[i]!r}")
            old_left = int(m.group(2) or 1)
            new_left = int(m.group(4) or 1)
            hunk = Hunk(header=lines[i])
            i += 1
            while (old_left > 0 or new_left > 0) and i < len(lines):
                body = lines[i]
                if body.startswith("\\"):  # "\ No newline at end of file"
                    i += 1
                    continue
                tag = body[:1] or " "  # some tools strip the space on empty context lines
                if tag == "+":
                    new_left -= 1
                elif tag == "-":
                    old_left -= 1
                elif tag == " ":
                    old_left -= 1
                    new_left -= 1
                else:
                    break
                hunk.lines.append(body if body else " ")
                i += 1
            if old_left != 0 or new_left != 0:
                raise InputError(f"hunk {hunk.header!r} in {current.path}: line counts don't match header")
            current.hunks.append(hunk)
            while i < len(lines) and lines[i].startswith("\\"):
                i += 1

        if not current.hunks:
            raise InputError(f"file {current.path}: no hunks found")
        files.append(current)

    if not files:
        raise InputError("no valid file headers ('---'/'+++') found; is this a unified diff?")

    py = [f for f in files if f.path.endswith(".py")]
    ignored = [f.path for f in files if not f.path.endswith(".py")]
    return ParsedDiff(files=py, ignored=ignored)


def read_diff(path: str) -> ParsedDiff:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read diff file {path}: {e}") from e
    return parse_diff(text)
