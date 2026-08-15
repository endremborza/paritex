from paritex.core import page_starts, parity
from paritex.extract import normalize


def test_identical():
    words = "same exact text".split()
    report = parity(words, words)
    assert report.ratio == 1.0
    assert not report.divergences


def test_divergence_kinds():
    report = parity("the quick brown fox".split(), "the slow brown".split())
    assert {d.kind for d in report.divergences} == {"changed", "missing"}
    assert all(d.page is None for d in report.divergences)


def test_page_annotation():
    pages = [["a", "b"], ["c", "d"]]
    starts = page_starts(pages)
    assert starts == [0, 2]
    report = parity(["a", "b", "c", "d"], ["x", "b", "c", "y"], starts)
    assert [(d.original, d.page) for d in report.divergences] == [("a", 1), ("d", 2)]


def test_normalize():
    assert normalize("Par-\nity ﬁne\n  Text") == "parity fine text"
    assert normalize("d´epartement") == normalize("département") == "departement"
    assert normalize("author∗") == "author*"
