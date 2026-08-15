"""Reconstruct papers as LaTeX with an AI backend and evaluate the parity."""

import argparse
from pathlib import Path

from paritex.backends import load_backends
from paritex.core import page_starts, parity
from paritex.extract import pdf_page_words, pdf_words
from paritex.papers import DEMO_PAPERS, fetch
from paritex.project import evaluate, init_project, reconstruct, refine, render
from paritex.types import ParityReport, Progress, ProjectReport

_PRINT_DIVERGENCES = 20


def main() -> None:
    parser = argparse.ArgumentParser(prog="paritex", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parity", help="compare two PDFs word-level")
    p.add_argument("original", type=Path)
    p.add_argument("rebuilt", type=Path)

    p = sub.add_parser("fetch", help="download the demo paper set")
    p.add_argument("names", nargs="*", help=f"subset of: {', '.join(DEMO_PAPERS)}")
    p.add_argument("--dest", type=Path, default=Path("papers"))

    p = sub.add_parser("init", help="create a reconstruction project from a PDF")
    p.add_argument("pdf", type=Path)
    p.add_argument(
        "project", type=Path, nargs="?", help="project dir (default: ./<pdf stem>)"
    )

    p = sub.add_parser("reconstruct", help="AI-reconstruct, render, and evaluate")
    p.add_argument("path", type=Path, help="project dir, or a PDF to init first")
    p.add_argument("--backend", help="backend name (see `paritex backends`)")
    p.add_argument("--config", type=Path, help="backend config TOML")
    p.add_argument("--rounds", type=int, default=1, help="max backend passes")
    p.add_argument("--target", type=float, default=1.0, help="parity ratio to stop at")

    p = sub.add_parser("refine", help="another AI pass over the current candidate")
    p.add_argument("project", type=Path)
    p.add_argument("--instruction", help="steer the pass beyond parity feedback")
    p.add_argument("--backend", help="backend name (see `paritex backends`)")
    p.add_argument("--config", type=Path, help="backend config TOML")
    p.add_argument("--rounds", type=int, default=1, help="max backend passes")
    p.add_argument("--target", type=float, default=1.0, help="parity ratio to stop at")

    p = sub.add_parser("render", help="tectonic-render a project's main.tex")
    p.add_argument("project", type=Path)

    p = sub.add_parser("eval", help="evaluate a rendered project against its original")
    p.add_argument("project", type=Path)

    p = sub.add_parser("backends", help="list configured backends")
    p.add_argument("--config", type=Path)

    args = parser.parse_args()
    match args.command:
        case "parity":
            pages = pdf_page_words(args.original)
            words = [word for page in pages for word in page]
            report = parity(words, pdf_words(args.rebuilt), page_starts(pages))
            _print_parity(report)
        case "fetch":
            for path in fetch(args.dest, args.names or None):
                print(path)
        case "init":
            print(init_project(args.pdf, args.project))
        case "reconstruct":
            backends, default = load_backends(args.config)
            backend = backends[args.backend or default]
            project = args.path
            if project.suffix == ".pdf":
                project = init_project(project)
                print(f"project: {project}")
            report = reconstruct(
                project, backend, args.rounds, args.target, on_event=_print_progress
            )
            _print_report(report)
        case "refine":
            backends, default = load_backends(args.config)
            report = refine(
                args.project,
                backends[args.backend or default],
                instruction=args.instruction,
                rounds=args.rounds,
                target=args.target,
                on_event=_print_progress,
            )
            _print_report(report)
        case "render":
            print(render(args.project))
        case "eval":
            _print_report(evaluate(args.project))
        case "backends":
            backends, default = load_backends(args.config)
            for name, backend in backends.items():
                marker = "*" if name == default else " "
                print(f"{marker} {name} ({backend.mode}): {' '.join(backend.argv)}")


def _print_progress(event: Progress) -> None:
    if event.stage == "backend" and event.detail:
        print(f"  {event.detail}", flush=True)
        return
    line = f"[round {event.round}] {event.stage}: {'ok' if event.ok else 'failed'}"
    if event.ratio is not None:
        line += f" {event.ratio:.1%}, {event.divergences} divergences"
    print(line, flush=True)


def _print_report(report: ProjectReport) -> None:
    print(f"pages: {report.pages_original} -> {report.pages_rebuilt}")
    _print_parity(report.parity)


def _print_parity(report: ParityReport) -> None:
    divergences = report.divergences
    print(f"parity: {report.ratio:.1%}, {len(divergences)} divergences")
    for d in divergences[:_PRINT_DIVERGENCES]:
        where = f" (p{d.page})" if d.page is not None else ""
        print(f"  {d.kind}{where}: {d.original[:70]!r} -> {d.rebuilt[:70]!r}")
    if len(divergences) > _PRINT_DIVERGENCES:
        print(f"  ... and {len(divergences) - _PRINT_DIVERGENCES} more (report.json)")
