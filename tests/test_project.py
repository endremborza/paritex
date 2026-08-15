import shutil
from pathlib import Path

import pymupdf
import pytest

from paritex.project import init_project, reconstruct, refine, render
from paritex.types import Backend, BibError, Progress, RenderError

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

BIB_BLOCK = (
    "\\begin{filecontents*}{refs.bib}\n"
    "@article{demo, title={T}, author={A}, journal={J}, year={2020}}\n"
    "\\end{filecontents*}\n"
)


def tex(body: str, bib: str = BIB_BLOCK) -> str:
    return (
        f"{bib}\\documentclass{{article}}\\pagestyle{{empty}}"
        f"\\begin{{document}}{body}\\end{{document}}\n"
    )


def make_pdf(path: Path, text: str) -> None:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text)
        doc.save(path)


def switching_backend(project: Path, first: str, then: str) -> Backend:
    (project / "first.tex").write_text(first)
    (project / "then.tex").write_text(then)
    script = "if [ -f tried ]; then cat then.tex; else touch tried; cat first.tex; fi"
    return Backend("fake", ("sh", "-c", script), "generate")


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
    (project / "src.tex").write_text(tex("hello parity world"))
    events: list[Progress] = []
    backend = Backend("fake", ("cat", "src.tex"), "generate")
    report = reconstruct(project, backend, on_event=events.append)
    assert report.parity.ratio == 1.0
    assert report.pages_rebuilt == 1
    assert (project / "report.json").exists()
    assert (project / "refs.bib").exists()
    assert [e.stage for e in events] == ["backend", "render", "bib", "parity"]
    assert all(e.ok for e in events)
    assert events[-1].ratio == 1.0


@needs_tectonic
def test_reconstruct_recovers_from_compile_failure(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    backend = switching_backend(project, "\\bad{", tex("hello parity world"))
    events: list[Progress] = []
    report = reconstruct(project, backend, rounds=2, on_event=events.append)
    assert report.parity.ratio == 1.0
    stages = [(e.stage, e.ok) for e in events[:2]]
    assert stages == [("backend", True), ("render", False)]


@needs_tectonic
def test_reconstruct_recovers_from_parity_feedback(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    backend = switching_backend(
        project, tex("hello wrong world"), tex("hello parity world")
    )
    events: list[Progress] = []
    report = reconstruct(project, backend, rounds=2, on_event=events.append)
    assert report.parity.ratio == 1.0
    ratios = [e.ratio for e in events if e.stage == "parity" and e.ratio is not None]
    assert len(ratios) == 2 and ratios[0] < 1.0


@needs_tectonic
def test_reconstruct_recovers_from_bib_gate(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    backend = switching_backend(
        project, tex("hello parity world", bib=""), tex("hello parity world")
    )
    events: list[Progress] = []
    report = reconstruct(project, backend, rounds=2, on_event=events.append)
    assert report.parity.ratio == 1.0
    failed = [e for e in events if not e.ok]
    assert [e.stage for e in failed] == ["bib"]
    assert "refs.bib" in failed[0].detail


@needs_tectonic
def test_refine_steers_with_instruction(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    (project / "main.tex").write_text(tex("hello wrong world"))
    (project / "src.tex").write_text(tex("hello parity world"))
    script = "cat > prompt.txt; cat src.tex"
    backend = Backend("fake", ("sh", "-c", script), "generate")
    report = refine(project, backend, instruction="fix the middle word")
    assert report.parity.ratio == 1.0
    prompt = (project / "prompt.txt").read_text()
    assert "fix the middle word" in prompt
    assert "wrong" in prompt  # parity feedback rides along


@needs_tectonic
def test_refine_without_candidate_fails(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "some text")
    project = init_project(pdf, tmp_path / "proj")
    with pytest.raises(FileNotFoundError, match="nothing to refine"):
        refine(project, Backend("fake", ("true",), "generate"))


@needs_tectonic
def test_bib_gate_fails_loudly_on_final_round(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    (project / "src.tex").write_text(tex("hello parity world", bib=""))
    backend = Backend("fake", ("cat", "src.tex"), "generate")
    with pytest.raises(BibError):
        reconstruct(project, backend)


@needs_tectonic
def test_failed_round_clears_stale_report(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, "hello parity world")
    project = init_project(pdf, tmp_path / "proj")
    (project / "report.json").write_text("{}")
    (project / "src.tex").write_text("\\bad{")
    backend = Backend("fake", ("cat", "src.tex"), "generate")
    with pytest.raises(RenderError):
        reconstruct(project, backend)
    assert not (project / "report.json").exists()


@needs_tectonic
def test_render_error(tmp_path: Path):
    bad = "\\documentclass{article}\\begin{document}\\nope"
    (tmp_path / "main.tex").write_text(bad)
    with pytest.raises(RenderError):
        render(tmp_path)


@needs_tectonic
def test_render_search_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    extra = tmp_path / "texmf"
    extra.mkdir()
    (extra / "snippet.tex").write_text("found elsewhere")
    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{snippet}\\end{document}"
    )
    monkeypatch.delenv("PARITEX_SEARCH_PATHS", raising=False)
    with pytest.raises(RenderError):
        render(project)
    monkeypatch.setenv("PARITEX_SEARCH_PATHS", str(extra))
    assert render(project).is_file()
