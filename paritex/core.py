from bisect import bisect_right
from collections.abc import Sequence
from difflib import SequenceMatcher
from itertools import accumulate

from paritex.types import Divergence, Kind, ParityReport

_KINDS: dict[str, Kind] = {"delete": "missing", "insert": "added", "replace": "changed"}


def page_starts(pages: Sequence[Sequence[str]]) -> list[int]:
    """Cumulative word offsets of each page, for parity's page annotation."""
    return [0, *accumulate(len(page) for page in pages[:-1])]


def parity(
    original: Sequence[str],
    rebuilt: Sequence[str],
    starts: Sequence[int] | None = None,
) -> ParityReport:
    """Word-level diff; `starts` (from page_starts) adds original-page numbers.

    SequenceMatcher with autojunk off is quadratic in the worst case. That is the
    right trade at paper scale - a few thousand words, where autojunk's
    popular-element heuristic would silently skip genuinely repeated text — but
    it is why this is sized for papers, not for book-length documents.
    """
    sm = SequenceMatcher(a=original, b=rebuilt, autojunk=False)
    divergences = [
        Divergence(
            _KINDS[tag],
            " ".join(original[i1:i2]),
            " ".join(rebuilt[j1:j2]),
            None if starts is None else bisect_right(starts, i1),
        )
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    ]
    return ParityReport(sm.ratio(), divergences)
