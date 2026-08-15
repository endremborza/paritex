import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

from paritex import prompts
from paritex.core import parity
from paritex.extract import page_count, pdf_images, pdf_text, pdf_words
from paritex.types import Backend, ProjectReport, RenderError

ORIGINAL = "original.pdf"
MAIN_TEX = "main.tex"
REBUILT = "main.pdf"
ASSETS = "assets"
REPORT = "report.json"
_LOG_TAIL = 4000
_FEEDBACK_DIVERGENCES = 40
_FEEDBACK_WIDTH = 160


def init_project(pdf: Path, project: Path | None = None) -> Path:
    project = project or Path(pdf.stem)
    project.mkdir(parents=True, exist_ok=True)
    original = project / ORIGINAL
    if pdf.resolve() != original.resolve():
        shutil.copy(pdf, original)
    pdf_images(original, project / ASSETS)
    return project


def render(project: Path) -> Path:
    result = subprocess.run(
        ["tectonic", MAIN_TEX], cwd=project, capture_output=True, text=True
    )
    if result.returncode:
        raise RenderError((result.stderr + result.stdout)[-_LOG_TAIL:])
    return project / REBUILT


def evaluate(project: Path) -> ProjectReport:
    original, rebuilt = project / ORIGINAL, project / REBUILT
    report = ProjectReport(
        parity=parity(pdf_words(original), pdf_words(rebuilt)),
        pages_original=page_count(original),
        pages_rebuilt=page_count(rebuilt),
    )
    (project / REPORT).write_text(json.dumps(asdict(report), indent=1))
    return report


def reconstruct(
    project: Path, backend: Backend, rounds: int = 1, target: float = 1.0
) -> ProjectReport:
    """Run backend -> tectonic -> parity, feeding failures back, `rounds` times max."""
    from paritex.backends import run_backend

    prompt = _initial_prompt(backend, project)
    report = None
    for round_ in range(1, rounds + 1):
        run_backend(backend, prompt, project)
        try:
            render(project)
        except RenderError as err:
            if round_ == rounds:
                raise
            prompt = _fill(backend, "compile_feedback", project, log=err.log)
            continue
        report = evaluate(project)
        if report.parity.ratio >= target:
            return report
        prompt = _fill(
            backend,
            "feedback",
            project,
            ratio=f"{report.parity.ratio:.1%}",
            feedback=_summarize(report),
        )
    if report is None:
        raise RenderError("no successful render")
    return report


def _initial_prompt(backend: Backend, project: Path) -> str:
    if backend.mode == "generate":
        return _fill(backend, "prompt", project, text=pdf_text(project / ORIGINAL))
    return _fill(backend, "prompt", project)


def _fill(backend: Backend, slot: str, project: Path, **values: str) -> str:
    template = getattr(backend, slot) or prompts.DEFAULTS[backend.mode][slot]
    assets = sorted(p.name for p in (project / ASSETS).glob("*"))
    values |= {"pdf": ORIGINAL, "assets": ", ".join(assets) or "none extracted"}
    if backend.mode == "generate" and "{tex}" in template:
        values["tex"] = (project / MAIN_TEX).read_text()
    return prompts.fill(template, **values)


def _summarize(report: ProjectReport) -> str:
    divergences = report.parity.divergences

    def clip(text: str) -> str:
        return text if len(text) <= _FEEDBACK_WIDTH else text[:_FEEDBACK_WIDTH] + "..."

    lines = [
        f"- {d.kind}: {clip(d.original)!r} -> {clip(d.rebuilt)!r}"
        for d in divergences[:_FEEDBACK_DIVERGENCES]
    ]
    if len(divergences) > _FEEDBACK_DIVERGENCES:
        rest = len(divergences) - _FEEDBACK_DIVERGENCES
        lines.append(f"... and {rest} more (see report.json)")
    return "\n".join(lines)
