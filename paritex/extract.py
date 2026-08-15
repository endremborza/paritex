import re
import unicodedata
from pathlib import Path

import pymupdf

_WS = re.compile(r"\s+")
_ACCENTS = str.maketrans("", "", "´¨¯˘˙˚˛˜˝ˆˇ¸")  # standalone glyphs in old PDFs
_VARIANTS = str.maketrans({"∗": "*"})
_MIN_IMAGE_PX = 64


def normalize(text: str) -> str:
    """Fold ligatures, accents, and glyph variants so parity measures content."""
    text = text.replace("-\n", "").translate(_ACCENTS).translate(_VARIANTS)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _WS.sub(" ", text.lower()).strip()


def pdf_text(path: str | Path) -> str:
    with pymupdf.open(path) as doc:
        return "\n".join(str(page.get_text()) for page in doc)


def pdf_words(path: str | Path) -> list[str]:
    return normalize(pdf_text(path)).split()


def page_count(path: str | Path) -> int:
    with pymupdf.open(path) as doc:
        return doc.page_count


def pdf_images(path: str | Path, dest: Path) -> list[Path]:
    """Extract embedded raster images to dest, skipping icon-sized ones."""
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    seen: set[int] = set()
    with pymupdf.open(path) as doc:
        for pno, page in enumerate(doc.pages(), 1):
            for n, info in enumerate(page.get_images(full=True)):
                xref = info[0]
                if xref in seen:
                    continue
                seen.add(xref)
                img = doc.extract_image(xref)
                if min(img["width"], img["height"]) < _MIN_IMAGE_PX:
                    continue
                target = dest / f"p{pno:02d}-{n}.{img['ext']}"
                target.write_bytes(img["image"])
                out.append(target)
    return out
