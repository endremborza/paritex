"""Structural bibliography gate: regex-level checks that refs.bib is real.

Semantic validation — whether the entries name real papers — is hallubib's.
"""

import re
from pathlib import Path

from paritex.layout import MAIN_TEX, REFS_BIB

_COMMENT = re.compile(r"(?<!\\)%.*")
_CITE = re.compile(
    r"\\[A-Za-z]*[cC]ite[A-Za-z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]*)\}"
)
_ENTRY = re.compile(
    r"@(?!string\b|comment\b|preamble\b)\w+\s*\{\s*([^,{}\s]+)\s*,", re.IGNORECASE
)
_THEBIB = re.compile(r"\\begin\s*\{thebibliography\}")


def cite_keys(tex: str) -> set[str]:
    """Keys of every \\cite-family command, comments stripped, \\nocite{*} ignored."""
    keys: set[str] = set()
    for group in _CITE.findall(_COMMENT.sub("", tex)):
        keys.update(key.strip() for key in group.split(",") if key.strip())
    keys.discard("*")
    return keys


def bib_keys(bib: str) -> set[str]:
    return set(_ENTRY.findall(bib))


def check_bib(project: Path) -> list[str]:
    """Violations of the refs.bib contract; empty means the gate passes."""
    tex = (project / MAIN_TEX).read_text()
    violations = []
    if _THEBIB.search(_COMMENT.sub("", tex)):
        violations.append(
            f"{MAIN_TEX} inlines a thebibliography; the bibliography must be {REFS_BIB}"
        )
    bib_path = project / REFS_BIB
    if not bib_path.is_file():
        return violations + [f"{REFS_BIB} is missing"]
    keys = bib_keys(bib_path.read_text())
    if not keys:
        violations.append(f"{REFS_BIB} has no entries")
    missing = sorted(cite_keys(tex) - keys)
    if missing:
        violations.append(f"cited keys missing from {REFS_BIB}: {', '.join(missing)}")
    return violations
