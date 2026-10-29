import pytest

from docdrift.diff_parser import parse_diff, read_diff
from docdrift.errors import InputError

VALID = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 import os
-X = 1
+X = 2
 Y = 3
--- a/notes.txt
+++ b/notes.txt
@@ -1 +1 @@
-old
+new
"""


def test_parses_files_hunks_and_lines():
    d = parse_diff(VALID)
    assert [f.path for f in d.files] == ["app.py"]
    assert d.ignored == ["notes.txt"]
    hunk = d.files[0].hunks[0]
    assert hunk.added == ["X = 2"]
    assert hunk.removed == ["X = 1"]
    assert hunk.lines == [" import os", "-X = 1", "+X = 2", " Y = 3"]


def test_multiple_hunks_and_no_newline_marker():
    text = """--- a/a.py
+++ b/a.py
@@ -1,1 +1,1 @@
-a = 1
+a = 2
\\ No newline at end of file
@@ -10,2 +10,3 @@ def f():
 x = 1
+y = 2
 z = 3
"""
    d = parse_diff(text)
    assert len(d.files[0].hunks) == 2
    assert d.added_lines() == ["a = 2", "y = 2"]


def test_new_file_uses_new_path():
    d = parse_diff("--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+print('hi')\n")
    assert d.files[0].path == "new.py"


@pytest.mark.parametrize("text", [
    "",
    "just some text\nnot a diff\n",
    "--- a/x.py\nno plus header\n",
    "--- a/x.py\n+++ b/x.py\n",  # no hunks
    "--- a/x.py\n+++ b/x.py\n@@ broken @@\n+x\n",
    "--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,3 @@\n-a\n+b\n",  # counts don't match header
])
def test_malformed_diffs_raise(text):
    with pytest.raises(InputError):
        parse_diff(text)


def test_unreadable_file_raises(tmp_path):
    with pytest.raises(InputError):
        read_diff(str(tmp_path / "missing.diff"))
