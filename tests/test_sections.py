from docdrift.sections import select_sections, split_sections


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


def test_small_docs_send_all_sections():
    secs = split_sections("\n".join(f"# H{i}\ntext" for i in range(8)))
    assert select_sections(secs, ["x = 1"]) == secs


def test_large_docs_send_top_five_by_keyword_match():
    body = [f"# H{i}\nunrelated text" for i in range(10)]
    body[7] = "# Retries\nMAX_RETRIES controls retries"
    body[2] = "# Backoff\nbackoff seconds between retries"
    secs = split_sections("\n".join(body))
    sent = select_sections(secs, ["MAX_RETRIES = 5", "BACKOFF_SECONDS = 2"])
    ids = [s.id for s in sent]
    assert len(ids) == 5
    assert "s8" in ids and "s3" in ids
    assert ids == sorted(ids, key=lambda i: int(i[1:]))  # document order
