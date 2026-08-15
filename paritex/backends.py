import json
import os
import re
import subprocess
import threading
import tomllib
from collections.abc import Callable
from pathlib import Path

from paritex.layout import MAIN_TEX, REFS_BIB
from paritex.types import Auth, Backend, BackendError, Mode

OnLine = Callable[[str], None]

_DEFAULT_TIMEOUT = 3600.0
_LOG_TAIL = 4000
_LINE_WIDTH = 160
_TEMPLATE_SLOTS = ("prompt", "feedback", "refine", "compile_feedback", "bib_feedback")
_ANTHROPIC_AUTH_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
_CLAUDE_STREAM_ARGV = ("--output-format", "stream-json", "--verbose")
_BIB_BLOCK = re.compile(
    r"\\begin\{filecontents\*?\}(?:\[[^\]]*\])?\{"
    + re.escape(REFS_BIB)
    + r"\}\n(.*?)\\end\{filecontents\*?\}",
    re.DOTALL,
)


def claude_backend(
    name: str,
    *,
    auth: Auth = "login",
    allowed_tools: str = "Bash(tectonic:*)",
    mode: Mode = "agent",
    model: str | None = None,
    effort: str | None = None,
) -> Backend:
    """The uniform Claude Code backend: `login` scrubs Anthropic auth env vars so
    the run uses the box's Claude Code login; `api` refuses to start without
    ANTHROPIC_API_KEY and spends API credits deliberately. model/effort default
    to the box's Claude Code settings when None."""
    argv = (
        ("claude", "-p")
        if mode == "generate"
        else (
            "claude",
            "-p",
            "{prompt}",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            allowed_tools,
        )
    )
    if model:
        argv += ("--model", model)
    if effort:
        argv += ("--effort", effort)
    return Backend(
        name=name,
        argv=argv,
        mode=mode,
        timeout=_DEFAULT_TIMEOUT,
        drop_env=_ANTHROPIC_AUTH_ENV if auth == "login" else (),
        require_env=("ANTHROPIC_API_KEY",) if auth == "api" else (),
        stream="claude-json",
        stream_argv=_CLAUDE_STREAM_ARGV if mode == "agent" else (),
    )


BUILTIN: dict[str, Backend] = {
    "claude-code": claude_backend("claude-code"),
    "claude-api": claude_backend("claude-api", auth="api"),
    "claude-gen": claude_backend("claude-gen", mode="generate"),
}

_CONFIG_LOCATIONS = (Path("paritex.toml"), Path.home() / ".config" / "paritex.toml")


def load_backends(config: Path | None = None) -> tuple[dict[str, Backend], str]:
    """Builtins merged with the first config found; returns (backends, default name)."""
    if config is None:
        config = next((p for p in _CONFIG_LOCATIONS if p.is_file()), None)
    backends = dict(BUILTIN)
    default = "claude-code"
    if config is not None:
        data = tomllib.loads(config.read_text())
        default = data.get("default", default)
        for name, spec in data.get("backends", {}).items():
            backends[name] = parse_backend(name, spec, config.parent)
    if default not in backends:
        raise KeyError(f"default backend {default!r} not defined")
    return backends, default


def parse_backend(name: str, spec: dict, base: Path) -> Backend:
    """Backend from a spec mapping — the schema consumers reuse for their own config.

    Keys: argv (required), mode ('agent'|'generate'), timeout, and the template
    slots prompt/feedback/compile_feedback/bib_feedback, each inline or as a
    `*_file` path resolved against base.
    """
    mode: Mode = spec.get("mode", "agent")
    if mode not in ("agent", "generate"):
        raise ValueError(f"backend {name!r}: mode must be 'agent' or 'generate'")

    def template(key: str) -> str | None:
        if f"{key}_file" in spec:
            return (base / spec[f"{key}_file"]).read_text()
        return spec.get(key)

    templates = {key: template(key) for key in _TEMPLATE_SLOTS}
    return Backend(
        name=name,
        argv=tuple(spec["argv"]),
        mode=mode,
        timeout=spec.get("timeout", _DEFAULT_TIMEOUT),
        env=tuple(sorted(spec.get("env", {}).items())),
        drop_env=tuple(spec.get("drop_env", ())),
        require_env=tuple(spec.get("require_env", ())),
        stream=spec.get("stream", "raw"),
        stream_argv=tuple(spec.get("stream_argv", ())),
        **templates,
    )


def run_backend(
    backend: Backend, prompt: str, project: Path, on_line: OnLine | None = None
) -> None:
    """Run the backend in the project dir; prompt fills {prompt} in argv, else stdin.

    Agent mode expects the command to write main.tex and refs.bib itself;
    generate mode captures stdout as main.tex (chatter and code fences
    stripped) and materializes its filecontents refs.bib block — tectonic
    keeps TeX-written files virtual, so paritex writes the real one.

    With on_line, an agent-mode backend streams: stream_argv is appended,
    stdout+stderr are captured live, and each line — translated per
    backend.stream — reaches the callback instead of the console.
    """
    missing = [key for key in backend.require_env if not os.environ.get(key)]
    if missing:
        raise BackendError(
            f"{backend.name} requires env vars: {', '.join(missing)} (not set)"
        )
    env = None
    if backend.env or backend.drop_env:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in backend.drop_env
        }
        env.update(backend.env)
    argv = [arg.replace("{prompt}", prompt) for arg in backend.argv]
    stdin = None if any("{prompt}" in arg for arg in backend.argv) else prompt
    if on_line is not None and backend.mode == "agent":
        _run_streaming(backend, argv, stdin, project, env, on_line)
        return
    result = subprocess.run(
        argv,
        cwd=project,
        input=stdin,
        text=True,
        timeout=backend.timeout,
        env=env,
        capture_output=backend.mode == "generate",
    )
    if result.returncode:
        if backend.mode == "generate":
            raise BackendError((result.stderr + result.stdout)[-_LOG_TAIL:])
        raise BackendError(f"{backend.name} exited {result.returncode} (output above)")
    if backend.mode == "generate":
        tex = strip_fences(result.stdout)
        (project / MAIN_TEX).write_text(tex)
        (project / REFS_BIB).unlink(missing_ok=True)
        if block := _BIB_BLOCK.search(tex):
            (project / REFS_BIB).write_text(block.group(1))


def _run_streaming(
    backend: Backend,
    argv: list[str],
    stdin: str | None,
    project: Path,
    env: dict[str, str] | None,
    on_line: OnLine,
) -> None:
    proc = subprocess.Popen(
        argv + list(backend.stream_argv),
        cwd=project,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    timed_out = threading.Event()

    def _expire() -> None:
        timed_out.set()
        proc.kill()

    timer = threading.Timer(backend.timeout, _expire) if backend.timeout else None
    try:
        if timer:
            timer.start()
        if stdin is not None:
            assert proc.stdin is not None
            proc.stdin.write(stdin)
            proc.stdin.close()
        assert proc.stdout is not None
        for raw in proc.stdout:
            lines = (
                claude_stream_lines(raw)
                if backend.stream == "claude-json"
                else ([raw.rstrip()] if raw.strip() else [])
            )
            for line in lines:
                on_line(line)
        code = proc.wait()
    finally:
        if timer:
            timer.cancel()
    if timed_out.is_set():
        raise BackendError(f"{backend.name} timed out after {backend.timeout:.0f}s")
    if code:
        raise BackendError(f"{backend.name} exited {code}")


def claude_stream_lines(raw: str) -> list[str]:
    """One `claude -p --output-format stream-json` line -> human progress lines."""
    try:
        event = json.loads(raw)
    except ValueError:
        line = raw.strip()
        return [line] if line else []
    match event.get("type"):
        case "system" if event.get("subtype") == "init":
            return [f"agent session started (model {event.get('model', '?')})"]
        case "assistant":
            blocks = event.get("message", {}).get("content", [])
            return [line for block in blocks if (line := _describe_block(block))]
        case "result":
            seconds = event.get("duration_ms", 0) / 1000
            turns = event.get("num_turns", "?")
            line = f"agent session done: {turns} turns, {seconds:.0f}s"
            cost = event.get("total_cost_usd")
            return [line + (f", ${cost:.2f}" if cost is not None else "")]
    return []


def _describe_block(block: dict) -> str | None:
    if block.get("type") == "text":
        text = " ".join(block.get("text", "").split())
        return _clip(text) if text else None
    if block.get("type") != "tool_use":
        return None
    name = block.get("name", "tool")
    args = block.get("input", {})
    if name == "Bash" and "command" in args:
        return _clip(f"$ {args['command']}")
    target = args.get("file_path") or args.get("path") or args.get("pattern") or ""
    return _clip(f"{name} {target}".rstrip())


def _clip(text: str) -> str:
    return text if len(text) <= _LINE_WIDTH else text[: _LINE_WIDTH - 1] + "…"


def strip_fences(output: str) -> str:
    lines = output.splitlines()
    fences = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    if len(fences) >= 2:
        return "\n".join(lines[fences[0] + 1 : fences[-1]]) + "\n"
    return output
