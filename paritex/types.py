from dataclasses import dataclass
from typing import Literal

Kind = Literal["missing", "added", "changed"]
Mode = Literal["agent", "generate"]


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
class Backend:
    name: str
    argv: tuple[str, ...]
    mode: Mode = "agent"
    prompt: str | None = None
    feedback: str | None = None
    compile_feedback: str | None = None
    timeout: float | None = None


class RenderError(Exception):
    def __init__(self, log: str):
        super().__init__(f"tectonic failed:\n{log}")
        self.log = log
