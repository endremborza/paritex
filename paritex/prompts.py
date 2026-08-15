"""Default prompt templates.

Placeholders are filled by literal replacement (LaTeX braces are safe):
{pdf} original file name, {assets} extracted image listing, {text} extracted
PDF text, {tex} current main.tex, {ratio} parity percentage, {feedback}
divergence listing, {log} tectonic output tail.
"""

_RULES = """Requirements:
- Reproduce all text exactly: title, authors, affiliations, abstract, every section, footnotes, equations, table contents, figure captions, and the reference list.
- Recreate every table as a LaTeX tabular with identical content.
- Figures: raster images extracted from the original are available under assets/ ({assets}); include matching ones via \\includegraphics. Recreate simple vector diagrams or plots with TikZ/pgfplots when no asset fits.
- Match the original layout: document class, column count, font sizes, and page count as closely as possible.
- Do not invent, summarize, or omit content."""

AGENT_RECONSTRUCT = f"""Reconstruct the research paper {{pdf}} (in the current directory) as a LaTeX project rendering into a PDF that matches the original as closely as possible.

Write in the current directory:
- main.tex — the full document; it must compile standalone with `tectonic main.tex` (run it to verify and fix any errors).
- refs.bib — the bibliography, cited from main.tex, so the rendered reference list textually matches the original's.

{_RULES}"""

AGENT_FEEDBACK = """Your LaTeX reconstruction of {pdf} (main.tex in the current directory) reaches {ratio} word-level parity with the original PDF. Edit main.tex (and refs.bib) to fix the divergences listed below, then verify `tectonic main.tex` still compiles.

Divergences (original -> rebuilt):
{feedback}"""

AGENT_COMPILE_FEEDBACK = """`tectonic main.tex` fails for the reconstruction in the current directory. Fix main.tex so it compiles without losing content, and verify with `tectonic main.tex`. Tectonic output tail:
{log}"""

GENERATE_RECONSTRUCT = f"""Produce a complete LaTeX document reconstructing the research paper whose extracted text follows. Output only the LaTeX source, nothing else.

It must compile standalone with tectonic as a single file: embed the bibliography via a filecontents* block or thebibliography so the rendered reference list textually matches the original's.

{_RULES}

Extracted text of the paper:
{{text}}"""

GENERATE_FEEDBACK = """The LaTeX document below reaches {ratio} word-level parity with the original paper. Output the full corrected LaTeX source (only the source, nothing else), fixing these divergences (original -> rebuilt):
{feedback}

Current source:
{tex}"""

GENERATE_COMPILE_FEEDBACK = """The LaTeX document below fails to compile with tectonic. Output the full corrected LaTeX source (only the source, nothing else) without losing content. Tectonic output tail:
{log}

Current source:
{tex}"""

DEFAULTS = {
    "agent": {
        "prompt": AGENT_RECONSTRUCT,
        "feedback": AGENT_FEEDBACK,
        "compile_feedback": AGENT_COMPILE_FEEDBACK,
    },
    "generate": {
        "prompt": GENERATE_RECONSTRUCT,
        "feedback": GENERATE_FEEDBACK,
        "compile_feedback": GENERATE_COMPILE_FEEDBACK,
    },
}


def fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template
