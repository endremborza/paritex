import urllib.request
from pathlib import Path

DEMO_PAPERS = {
    "attention": "https://arxiv.org/pdf/1706.03762",  # single column, tables, figures
    "gan": "https://arxiv.org/pdf/1406.2661",  # math-heavy, plots
    "word2vec": "https://arxiv.org/pdf/1301.3781",  # tables, plain layout
    "resnet": "https://arxiv.org/pdf/1512.03385",  # two-column CVPR, many tables
    "gw150914": "https://arxiv.org/pdf/1602.03837",  # two-column REVTeX, figures
    "bitcoin": "https://bitcoin.org/bitcoin.pdf",  # short whitepaper, diagrams
}


def fetch(dest: Path, names: list[str] | None = None) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for name in names or DEMO_PAPERS:
        target = dest / f"{name}.pdf"
        if not target.exists():
            request = urllib.request.Request(
                DEMO_PAPERS[name], headers={"User-Agent": "paritex-demo-fetch"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                target.write_bytes(response.read())
        out.append(target)
    return out
