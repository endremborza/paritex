from dataclasses import dataclass
from typing import Literal

Kind = Literal["missing", "added", "changed"]
Mode = Literal["agent", "generate"]
Auth = Literal["login", "api"]
Stage = Literal["backend", "render", "bib", "parity"]
Stream = Literal["raw", "claude-json"]


@dataclass(frozen=True)
class Divergence:
    kind: Kind
    original: str
    rebuilt: str
    page: int | None = None


@dataclass(frozen=True)
class ParityReport:
    ratio: float
    divergences: list[Divergence]


@dataclass(frozen=True)
class ProjectReport:
    parity: ParityReport
    pages_original: int
    pages_rebuilt: int


@dataclass(frozen=True)
class Progress:
    round: int
    stage: Stage
    ok: bool = True
    ratio: float | None = None
    divergences: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class Backend:
    """A configured AI command. Auth is explicit, never inherited by accident:
    env pairs are set for the child, drop_env vars are scrubbed from it, and
    require_env vars must be present or the run refuses to start."""

    name: str
    argv: tuple[str, ...]
    mode: Mode = "agent"
    prompt: str | None = None
    feedback: str | None = None
    refine: str | None = None
    compile_feedback: str | None = None
    bib_feedback: str | None = None
    timeout: float | None = None
    env: tuple[tuple[str, str], ...] = ()
    drop_env: tuple[str, ...] = ()
    require_env: tuple[str, ...] = ()
    stream: Stream = "raw"
    stream_argv: tuple[str, ...] = ()


class RenderError(Exception):
    def __init__(self, log: str):
        super().__init__(f"tectonic failed:\n{log}")
        self.log = log


class BackendError(Exception):
    def __init__(self, log: str):
        super().__init__(f"backend failed:\n{log}")
        self.log = log


class BibError(Exception):
    def __init__(self, violations: list[str]):
        super().__init__("bibliography gate failed:\n" + "\n".join(violations))
        self.violations = violations
