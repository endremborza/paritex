import shutil
from pathlib import Path

import pymupdf
import pytest

from paritex.project import init_project, reconstruct, render
from paritex.types import Backend, RenderError

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

TEX = (
    "\\documentclass{article}\\pagestyle{empty}"
    "\\begin{document}hello parity world\\end{document}\n"
)


def make_pdf(path: Path, text: str) -> None:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text)
        doc.save(path)


def test_init(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "some text")
    project = init_project(pdf, tmp_path / "proj")
    assert (project / "original.pdf").exists()
    assert (project / "assets").is_dir()


@needs_tectonic
def test_reconstruct_perfect(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    (project / "src.tex").write_text(TEX)
    report = reconstruct(project, Backend("fake", ("cat", "src.tex"), "generate"))
    assert report.parity.ratio == 1.0
    assert report.pages_rebuilt == 1
    assert (project / "report.json").exists()


@needs_tectonic
def test_reconstruct_recovers_from_compile_failure(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    (project / "good.tex").write_text(TEX)
    script = 'if [ -f tried ]; then cat good.tex; else touch tried; echo "\\\\bad{"; fi'
    backend = Backend("fake", ("sh", "-c", script), "generate")
    report = reconstruct(project, backend, rounds=2)
    assert report.parity.ratio == 1.0


@needs_tectonic
def test_render_error(tmp_path: Path):
    bad = "\\documentclass{article}\\begin{document}\\nope"
    (tmp_path / "main.tex").write_text(bad)
    with pytest.raises(RenderError):
        render(tmp_path)
