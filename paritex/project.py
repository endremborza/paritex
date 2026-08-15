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


def render(project: Path, tex: str = MAIN_TEX) -> Path:
    """tectonic compile. PARITEX_SEARCH_PATHS (colon-separated dirs) adds
    `-Z search-path` entries for classes outside tectonic's bundle (llncs & co)."""
    result = subprocess.run(
        ["tectonic", *_search_paths(), tex], cwd=project, capture_output=True, text=True
    )
    if result.returncode:
        raise RenderError((result.stderr + result.stdout)[-_LOG_TAIL:])
    return project / (tex.removesuffix(".tex") + ".pdf")


def _search_paths() -> list[str]:
    paths = os.environ.get("PARITEX_SEARCH_PATHS", "")
    return [
        arg
        for p in paths.split(":")
        if p
        for arg in ("-Z", f"search-path={Path(p).expanduser()}")
    ]


def evaluate(project: Path) -> ProjectReport:
    original, rebuilt = project / ORIGINAL, project / REBUILT
    pages = pdf_page_words(original)
    report = ProjectReport(
        parity=parity(
            [word for page in pages for word in page],
            pdf_words(rebuilt),
            page_starts(pages),
        ),
        pages_original=len(pages),
        pages_rebuilt=page_count(rebuilt),
    )
    (project / REPORT).write_text(json.dumps(report_to_dict(report), indent=1))
    return report


def report_to_dict(report: ProjectReport) -> dict:
    """The report.json serialization contract: version-stamped, deterministic."""
    import paritex

    return {"paritex_version": paritex.__version__, **asdict(report)}


def reconstruct(
    project: Path,
    backend: Backend,
    rounds: int = 1,
    target: float = 1.0,
    on_event: Callable[[Progress], None] | None = None,
) -> ProjectReport:
    """Run backend -> tectonic -> bib gate -> parity, feeding failures back.

    Loops up to `rounds` times, stopping early at `target` parity; a render or
    gate failure on the final round raises (RenderError / BibError).
    """
    return _rounds(
        project, backend, _initial_prompt(backend, project), rounds, target, on_event
    )


def refine(
    project: Path,
    backend: Backend,
    instruction: str | None = None,
    rounds: int = 1,
    target: float = 1.0,
    on_event: Callable[[Progress], None] | None = None,
) -> ProjectReport:
    """A further pass over the existing candidate: parity feedback, optionally
    steered by a caller-supplied instruction. Same loop and gates as reconstruct."""
    if not (project / MAIN_TEX).is_file():
        raise FileNotFoundError(f"nothing to refine: no {MAIN_TEX} in {project}")
    if not (project / REBUILT).is_file():
        render(project)
    report = evaluate(project)
    values = {"ratio": f"{report.parity.ratio:.1%}", "feedback": _summarize(report)}
    slot = "refine" if instruction else "feedback"
    if instruction:
        values["instruction"] = instruction
    prompt = _fill(backend, slot, project, **values)
    return _rounds(project, backend, prompt, rounds, target, on_event)


def _rounds(
    project: Path,
    backend: Backend,
    prompt: str,
    rounds: int,
    target: float,
    on_event: Callable[[Progress], None] | None,
) -> ProjectReport:
    from paritex.backends import run_backend

    emit = on_event or (lambda event: None)
    for round_ in range(1, rounds + 1):
        last = round_ == rounds
        emit(Progress(round_, "backend"))
        on_line = None
        if on_event is not None:
            on_line = lambda line, r=round_: emit(Progress(r, "backend", detail=line))  # noqa: E731
        run_backend(backend, prompt, project, on_line)
        _clear_derived(project)
        try:
            render(project)
        except RenderError as err:
            emit(Progress(round_, "render", ok=False, detail=err.log))
            if last:
                raise
            prompt = _fill(backend, "compile_feedback", project, log=err.log)
            continue
        emit(Progress(round_, "render"))
        violations = check_bib(project)
        if violations:
            emit(Progress(round_, "bib", ok=False, detail="\n".join(violations)))
            if last:
                raise BibError(violations)
            listing = "\n".join(f"- {v}" for v in violations)
            prompt = _fill(backend, "bib_feedback", project, violations=listing)
            continue
        emit(Progress(round_, "bib"))
        report = evaluate(project)
        ratio = report.parity.ratio
        divergences = len(report.parity.divergences)
        emit(Progress(round_, "parity", ratio=ratio, divergences=divergences))
        if ratio >= target or last:
            return report
        prompt = _fill(
            backend,
            "feedback",
            project,
            ratio=f"{ratio:.1%}",
            feedback=_summarize(report),
        )
    raise AssertionError("unreachable: every final round returns or raises")


def _clear_derived(project: Path) -> None:
    """main.tex just changed: whatever was derived from its predecessor is stale."""
    for name in (REPORT, REBUILT):
        (project / name).unlink(missing_ok=True)


def _initial_prompt(backend: Backend, project: Path) -> str:
    if backend.mode == "generate":
        return _fill(backend, "prompt", project, text=pdf_text(project / ORIGINAL))
    return _fill(backend, "prompt", project)


def _fill(backend: Backend, slot: str, project: Path, **values: str) -> str:
    template = getattr(backend, slot) or prompts.DEFAULTS[backend.mode][slot]
    assets = sorted(p.name for p in (project / ASSETS).glob("*"))
    static = {
        "pdf": ORIGINAL,
        "main_tex": MAIN_TEX,
        "refs_bib": REFS_BIB,
        "assets": ", ".join(assets) or "none extracted",
    }
    if backend.mode == "generate" and "{tex}" in template:
        values["tex"] = (project / MAIN_TEX).read_text()
    # static names first so document-derived values are never re-substituted
    return prompts.fill(template, **static, **values)


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
