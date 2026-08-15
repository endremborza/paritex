from pathlib import Path

from paritex.backends import load_backends, run_backend, strip_fences
from paritex.prompts import fill
from paritex.types import Backend


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
        "timeout = 5\n"
    )
    backends, default = load_backends(config)
    assert default == "mine"
    assert backends["claude"].mode == "agent"
    mine = backends["mine"]
    assert mine.argv == ("cat", "src.tex")
    assert mine.prompt == "do it: {pdf}"
    assert mine.feedback == "fix: {feedback}"
    assert mine.timeout == 5


def test_run_generate_captures_stdout(tmp_path: Path):
    (tmp_path / "src.tex").write_text("content\n")
    run_backend(Backend("fake", ("cat", "src.tex"), "generate"), "ignored", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "content\n"


def test_run_prompt_on_stdin(tmp_path: Path):
    run_backend(Backend("fake", ("cat",), "generate"), "the prompt", tmp_path)
    assert (tmp_path / "main.tex").read_text() == "the prompt"


def test_strip_fences():
    assert strip_fences("chatter\n```latex\n\\doc{x}\n```\ntrailer") == "\\doc{x}\n"
    assert strip_fences("\\doc{x}\n") == "\\doc{x}\n"


def test_fill_keeps_latex_braces():
    assert fill("use \\emph{x} for {pdf}", pdf="a.pdf") == "use \\emph{x} for a.pdf"
