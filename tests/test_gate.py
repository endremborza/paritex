from pathlib import Path

from paritex.gate import bib_keys, check_bib, cite_keys

TEX = """\\documentclass{article}
\\begin{document}
Seen \\cite{a} and \\citep[p.~3]{b,c}, \\Citet{d}, \\nocite{*}.
% a comment with \\cite{ghost}
Escaped 5\\% then \\cite{e}.
\\end{document}
"""


def test_cite_keys():
    assert cite_keys(TEX) == {"a", "b", "c", "d", "e"}


def test_bib_keys_skip_directives():
    bib = (
        '@string{jn = "Journal"}\n'
        "@article{real, title={T}, year={2020}}\n"
        "@comment{ignored}\n"
    )
    assert bib_keys(bib) == {"real"}


def project(tmp_path: Path, tex: str, bib: str | None) -> Path:
    (tmp_path / "main.tex").write_text(tex)
    if bib is not None:
        (tmp_path / "refs.bib").write_text(bib)
    return tmp_path


def test_check_bib_passes(tmp_path: Path):
    bib = "@article{a,t}@misc{b,t}@misc{c,t}@misc{d,t}@misc{e,t}"
    assert check_bib(project(tmp_path, TEX, bib)) == []


def test_check_bib_missing_file(tmp_path: Path):
    violations = check_bib(project(tmp_path, TEX, None))
    assert violations == ["refs.bib is missing"]


def test_check_bib_empty_and_missing_keys(tmp_path: Path):
    violations = check_bib(project(tmp_path, TEX, "just noise"))
    assert any("no entries" in v for v in violations)
    assert any("a, b, c, d, e" in v for v in violations)


def test_check_bib_rejects_thebibliography(tmp_path: Path):
    tex = "\\begin{thebibliography}{9}\\bibitem{a} X\\end{thebibliography}"
    violations = check_bib(project(tmp_path, tex, "@misc{a,t}"))
    assert any("thebibliography" in v for v in violations)
