from pathlib import Path

import pytest

from paritex.backends import (
    BUILTIN,
    claude_backend,
    claude_stream_lines,
    load_backends,
    parse_backend,
    run_backend,
    strip_fences,
)
from paritex.prompts import fill
from paritex.types import Backend, BackendError


def test_builtin_and_config(tmp_path: Path):
    (tmp_path / "prompt.txt").write_text("do it: {pdf}")
    config = tmp_path / "paritex.toml"
    config.write_text(
        'default = "mine"\n'
        "[backends.mine]\n"
        'mode = "generate"\n'
        'argv = ["cat", "src.tex"]\n'
        'prompt_file = "prompt.txt"\n'
        'feedback = "fix: {feedback}"\n'
        'bib_feedback = "bib: {violations}"\n'
        "timeout = 5\n"
    )
    backends, default = load_backends(config)
    assert default == "mine"
    assert backends["claude-code"].mode == "agent"
    assert backends["claude-code"].timeout is not None
    mine = backends["mine"]
    assert mine.argv == ("cat", "src.tex")
    assert mine.prompt == "do it: {pdf}"
    assert mine.feedback == "fix: {feedback}"
    assert mine.bib_feedback == "bib: {violations}"
    assert mine.timeout == 5


def test_parse_backend_rejects_bad_mode(tmp_path: Path):
    with pytest.raises(ValueError):
        parse_backend("bad", {"argv": ["x"], "mode": "chat"}, tmp_path)


def test_run_generate_captures_stdout(tmp_path: Path):
    (tmp_path / "src.tex").write_text("content\n")
    run_backend(Backend("fake", ("cat", "src.tex"), "generate"), "ignored", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "content\n"


def test_run_prompt_on_stdin(tmp_path: Path):
    run_backend(Backend("fake", ("cat",), "generate"), "the prompt", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "the prompt"


def test_generate_failure_carries_output(tmp_path: Path):
    backend = Backend("bad", ("sh", "-c", "echo oops >&2; exit 3"), "generate")
    with pytest.raises(BackendError) as err:
        run_backend(backend, "ignored", tmp_path)
    assert "oops" in err.value.log


def test_agent_failure_carries_exit_code(tmp_path: Path):
    backend = Backend("bad", ("sh", "-c", "exit 2"))
    with pytest.raises(BackendError, match="exited 2"):
        run_backend(backend, "ignored", tmp_path)


def test_claude_backend_model_effort():
    plain = claude_backend("claude-code")
    assert "--model" not in plain.argv and "--effort" not in plain.argv
    tuned = claude_backend("claude-code", model="sonnet", effort="medium")
    argv = " ".join(tuned.argv)
    assert "--model sonnet" in argv and "--effort medium" in argv
    assert tuned.stream == "claude-json"
    assert "--output-format" in tuned.stream_argv


def test_agent_streaming_forwards_lines(tmp_path: Path):
    backend = Backend("fake", ("sh", "-c", "echo one; echo two >&2"))
    lines: list[str] = []
    run_backend(backend, "ignored", tmp_path, lines.append)
    assert sorted(lines) == ["one", "two"]


def test_agent_streaming_failure(tmp_path: Path):
    backend = Backend("fake", ("sh", "-c", "echo partial; exit 3"))
    lines: list[str] = []
    with pytest.raises(BackendError, match="exited 3"):
        run_backend(backend, "ignored", tmp_path, lines.append)
    assert lines == ["partial"]


def test_claude_stream_lines():
    init = '{"type":"system","subtype":"init","model":"claude-sonnet-5"}'
    assert claude_stream_lines(init) == [
        "agent session started (model claude-sonnet-5)"
    ]
    turn = (
        '{"type":"assistant","message":{"content":['
        '{"type":"text","text":"Reading the\\n PDF now"},'
        '{"type":"tool_use","name":"Bash","input":{"command":"tectonic main.tex"}},'
        '{"type":"tool_use","name":"Write","input":{"file_path":"main.tex"}}]}}'
    )
    assert claude_stream_lines(turn) == [
        "Reading the PDF now",
        "$ tectonic main.tex",
        "Write main.tex",
    ]
    done = '{"type":"result","num_turns":7,"duration_ms":61500,"total_cost_usd":0.4212}'
    assert claude_stream_lines(done) == ["agent session done: 7 turns, 62s, $0.42"]
    assert claude_stream_lines('{"type":"user","message":{}}') == []
    assert claude_stream_lines("not json\n") == ["not json"]
    assert claude_stream_lines("   \n") == []


def test_config_spec_refine_and_stream(tmp_path: Path):
    config = tmp_path / "paritex.toml"
    config.write_text(
        "[backends.custom]\n"
        'argv = ["mytool"]\n'
        'refine = "steer: {instruction}"\n'
        'stream = "claude-json"\n'
        'stream_argv = ["--stream"]\n'
    )
    backends, _ = load_backends(config)
    assert backends["custom"].refine == "steer: {instruction}"
    assert backends["custom"].stream == "claude-json"
    assert backends["custom"].stream_argv == ("--stream",)


def test_auth_flavors():
    assert "ANTHROPIC_API_KEY" in BUILTIN["claude-code"].drop_env
    assert BUILTIN["claude-api"].require_env == ("ANTHROPIC_API_KEY",)
    assert "ANTHROPIC_API_KEY" in BUILTIN["claude-gen"].drop_env
    assert BUILTIN["claude-gen"].mode == "generate"


def test_drop_env_scrubs_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECRET_TOKEN", "leaky")
    backend = Backend(
        "fake",
        ("sh", "-c", 'printf "%s" "${SECRET_TOKEN:-clean}"'),
        "generate",
        drop_env=("SECRET_TOKEN",),
    )
    run_backend(backend, "ignored", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "clean"


def test_env_sets_child(tmp_path: Path):
    backend = Backend(
        "fake",
        ("sh", "-c", 'printf "%s" "$EXTRA"'),
        "generate",
        env=(("EXTRA", "value"),),
    )
    run_backend(backend, "ignored", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "value"


def test_require_env_fails_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DEFINITELY_MISSING", raising=False)
    backend = Backend("fake", ("true",), require_env=("DEFINITELY_MISSING",))
    with pytest.raises(BackendError, match="DEFINITELY_MISSING"):
        run_backend(backend, "ignored", tmp_path)


def test_config_spec_env_keys(tmp_path: Path):
    config = tmp_path / "paritex.toml"
    config.write_text(
        "[backends.custom]\n"
        'argv = ["mytool"]\n'
        "[backends.custom.env]\n"
        'MY_MODEL = "large"\n'
    )
    backends, _ = load_backends(config)
    assert backends["custom"].env == (("MY_MODEL", "large"),)


def test_strip_fences():
    assert strip_fences("chatter\n```latex\n\\doc{x}\n```\ntrailer") == "\\doc{x}\n"
    assert strip_fences("\\doc{x}\n") == "\\doc{x}\n"


def test_fill_keeps_latex_braces():
    assert fill("use \\emph{x} for {pdf}", pdf="a.pdf") == "use \\emph{x} for a.pdf"
