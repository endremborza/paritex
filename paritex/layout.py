"""The produced-files contract: what a reconstruction project contains.

Consumers import these names, never restate them; files paritex did not
create are opaque to it, so consumers can layer their own into the same dir.
"""

from typing import Final

ORIGINAL: Final = "original.pdf"
MAIN_TEX: Final = "main.tex"
REFS_BIB: Final = "refs.bib"
REBUILT: Final = "main.pdf"
ASSETS: Final = "assets"
REPORT: Final = "report.json"
