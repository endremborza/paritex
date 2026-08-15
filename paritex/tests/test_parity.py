from paritex.core import parity
from paritex.extract import normalize


def test_identical():
    words = "same exact text".split()
    report = parity(words, words)
    assert report.ratio == 1.0
    assert not report.divergences


def test_divergence_kinds():
    report = parity("the quick brown fox".split(), "the slow brown".split())
    assert {d.kind for d in report.divergences} == {"changed", "missing"}


def test_normalize():
    assert normalize("Par-\nity ﬁne\n  Text") == "parity fine text"
    assert normalize("d´epartement") == normalize("département") == "departement"
    assert normalize("author∗") == "author*"
