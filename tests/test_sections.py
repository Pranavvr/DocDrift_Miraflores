from docdrift.budget import context_size
from docdrift.sections import section_tokens, select_sections, split_sections


def test_preamble_is_its_own_section():
    secs = split_sections("Intro text\n\n# Title\nBody\n## Sub\nMore\n")
    assert [s.id for s in secs] == ["s1", "s2", "s3"]
    assert secs[0].heading == "" and secs[0].text == "Intro text"
    assert secs[1].heading == "Title"
    assert secs[2].text == "## Sub\nMore"


def test_no_preamble_starts_at_first_heading():
    secs = split_sections("# Title\nBody\n")
    assert [(s.id, s.heading) for s in secs] == [("s1", "Title")]


def test_hash_inside_code_fence_is_not_a_heading():
    secs = split_sections("# Title\n```bash\n# a comment\n```\n")
    assert len(secs) == 1


def test_everything_sent_when_it_fits_even_with_many_sections():
    secs = split_sections("\n".join(f"# H{i}\ntext" for i in range(30)))
    sent, not_sent = select_sections(secs, ["x = 1"], budget=10_000)
    assert sent == secs and not_sent == []


def test_over_budget_fills_by_keyword_rank_and_lists_the_rest():
    filler = "unrelated words " * 20
    body = [f"# H{i}\n{filler}" for i in range(10)]
    body[7] = f"# Retries\nMAX_RETRIES controls retries {filler}"
    body[2] = f"# Backoff\nbackoff seconds between retries {filler}"
    secs = split_sections("\n".join(body))
    budget = 3 * section_tokens(secs[7])  # room for about three sections
    sent, not_sent = select_sections(secs, ["MAX_RETRIES = 5", "BACKOFF_SECONDS = 2"], budget)
    ids = [s.id for s in sent]
    assert "s8" in ids and "s3" in ids  # the two relevant sections win
    assert sum(section_tokens(s) for s in sent) <= budget
    assert ids == sorted(ids, key=lambda i: int(i[1:]))  # document order
    assert {s.id for s in sent} | {s.id for s in not_sent} == {s.id for s in secs}


def test_oversized_section_skipped_but_smaller_ones_still_fit():
    secs = split_sections("# Big\n" + "retries " * 500 + "\n# Small\nretries")
    sent, not_sent = select_sections(secs, ["retries = 5"], budget=50)
    assert [s.heading for s in sent] == ["Small"]
    assert [s.heading for s in not_sent] == ["Big"]


def test_context_size_rounds_up_and_caps():
    small = [{"content": "x" * 300}]
    assert context_size(small, 32768) == 4096
    big = [{"content": "x" * 3 * 20_000}]  # ~20k tokens + reserve -> 32768
    assert context_size(big, 32768) == 32768
    assert context_size(big, 16384) == 16384
