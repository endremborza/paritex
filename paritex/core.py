from collections.abc import Sequence
from difflib import SequenceMatcher

from paritex.types import Divergence, Kind, ParityReport

_KINDS: dict[str, Kind] = {"delete": "missing", "insert": "added", "replace": "changed"}


def parity(original: Sequence[str], rebuilt: Sequence[str]) -> ParityReport:
    sm = SequenceMatcher(a=original, b=rebuilt, autojunk=False)
    divergences = [
        Divergence(_KINDS[tag], " ".join(original[i1:i2]), " ".join(rebuilt[j1:j2]))
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    ]
    return ParityReport(sm.ratio(), divergences)
