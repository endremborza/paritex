import subprocess
import tomllib
from pathlib import Path

from paritex.types import Backend, Mode

BUILTIN: dict[str, Backend] = {
    "claude": Backend(
        name="claude",
        argv=(
            "claude",
            "-p",
            "{prompt}",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            "Bash(tectonic:*)",
        ),
    ),
    "claude-gen": Backend(name="claude-gen", argv=("claude", "-p"), mode="generate"),
}

_CONFIG_LOCATIONS = (Path("paritex.toml"), Path.home() / ".config" / "paritex.toml")


def load_backends(config: Path | None = None) -> tuple[dict[str, Backend], str]:
    """Builtins merged with the first config found; returns (backends, default name)."""
    if config is None:
        config = next((p for p in _CONFIG_LOCATIONS if p.is_file()), None)
    backends = dict(BUILTIN)
    default = "claude"
    if config is not None:
        data = tomllib.loads(config.read_text())
        default = data.get("default", default)
        for name, spec in data.get("backends", {}).items():
            backends[name] = _parse(name, spec, config.parent)
    if default not in backends:
        raise KeyError(f"default backend {default!r} not defined")
    return backends, default


def _parse(name: str, spec: dict, base: Path) -> Backend:
    mode: Mode = spec.get("mode", "agent")
    if mode not in ("agent", "generate"):
        raise ValueError(f"backend {name!r}: mode must be 'agent' or 'generate'")

    def template(key: str) -> str | None:
        if f"{key}_file" in spec:
            return (base / spec[f"{key}_file"]).read_text()
        return spec.get(key)

    prompts = {key: template(key) for key in ("prompt", "feedback", "compile_feedback")}
    return Backend(
        name=name,
        argv=tuple(spec["argv"]),
        mode=mode,
        timeout=spec.get("timeout"),
        **prompts,
    )


def run_backend(backend: Backend, prompt: str, project: Path) -> None:
    """Run the backend in the project dir; prompt fills {prompt} in argv, else stdin.

    Agent mode expects the command to write main.tex itself; generate mode
    captures stdout as main.tex (surrounding chatter and code fences stripped).
    """
    argv = [arg.replace("{prompt}", prompt) for arg in backend.argv]
    stdin = None if any("{prompt}" in arg for arg in backend.argv) else prompt
    result = subprocess.run(
        argv,
        cwd=project,
        input=stdin,
        text=True,
        check=True,
        timeout=backend.timeout,
        capture_output=backend.mode == "generate",
    )
    if backend.mode == "generate":
        (project / "main.tex").write_text(strip_fences(result.stdout))


def strip_fences(output: str) -> str:
    lines = output.splitlines()
    fences = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fences) >= 2:
        return "\n".join(lines[fences[0] + 1 : fences[-1]]) + "\n"
    return output
