"""Default prompt templates.

Placeholders are filled by literal replacement (LaTeX braces are safe):
{pdf}, {main_tex}, {refs_bib} the contract file names, {assets} extracted
image listing, {text} extracted PDF text, {tex} current main.tex, {ratio}
parity percentage, {feedback} divergence listing, {instruction} a caller-supplied
refinement request, {violations} bib gate findings, {log} tectonic output tail.
"""

_RULES = """Requirements:
- Reproduce all text exactly: title, authors, affiliations, abstract, every section, footnotes, equations, table contents, figure captions, and the reference list.
- Recreate every table as a LaTeX tabular with identical content.
- Figures: raster images extracted from the original are available under assets/ ({assets}); include matching ones via \\includegraphics. Recreate simple vector diagrams or plots with TikZ/pgfplots when no asset fits.
- References must live in {refs_bib} and be cited from the text; never inline a thebibliography.
- Match the original layout: document class, column count, font sizes, and page count as closely as possible.
- Do not invent, summarize, or omit content."""

AGENT_RECONSTRUCT = f"""Reconstruct the research paper {{pdf}} (in the current directory) as a LaTeX project rendering into a PDF that matches the original as closely as possible.

Write in the current directory:
- {{main_tex}} — the full document; it must compile standalone with `tectonic {{main_tex}}` (run it to verify and fix any errors).
- {{refs_bib}} — the bibliography, cited from {{main_tex}}, so the rendered reference list textually matches the original's.

{_RULES}"""

AGENT_FEEDBACK = """Your LaTeX reconstruction of {pdf} ({main_tex} in the current directory) reaches {ratio} word-level parity with the original PDF. Edit {main_tex} (and {refs_bib}) to fix the divergences listed below, then verify `tectonic {main_tex}` still compiles.

Divergences (original -> rebuilt):
{feedback}"""

AGENT_REFINE = """Your LaTeX reconstruction of {pdf} ({main_tex} in the current directory) reaches {ratio} word-level parity with the original PDF. Rework it according to this instruction, staying faithful to the original everywhere else:

{instruction}

Edit {main_tex} (and {refs_bib}), then verify `tectonic {main_tex}` still compiles. Divergences measured against the original (original -> rebuilt), for context:
{feedback}"""

AGENT_COMPILE_FEEDBACK = """`tectonic {main_tex}` fails for the reconstruction in the current directory. Fix {main_tex} so it compiles without losing content, and verify with `tectonic {main_tex}`. Tectonic output tail:
{log}"""

AGENT_BIB_FEEDBACK = """Your LaTeX reconstruction of {pdf} ({main_tex} in the current directory) fails the bibliography check:
{violations}

The bibliography must live in {refs_bib} with every cited key present as an entry. Fix {main_tex} and {refs_bib} without losing content, then verify `tectonic {main_tex}` still compiles."""

GENERATE_RECONSTRUCT = f"""Produce a complete LaTeX document reconstructing the research paper whose extracted text follows. Output only the LaTeX source, nothing else.

It must compile standalone with tectonic as a single file: start with a filecontents* block writing {{refs_bib}}, cite its entries from the text, so the rendered reference list textually matches the original's.

{_RULES}

Extracted text of the paper:
{{text}}"""

GENERATE_FEEDBACK = """The LaTeX document below reaches {ratio} word-level parity with the original paper. Output the full corrected LaTeX source (only the source, nothing else), fixing these divergences (original -> rebuilt):
{feedback}

Current source:
{tex}"""

GENERATE_REFINE = """The LaTeX document below reaches {ratio} word-level parity with the original paper. Output the full corrected LaTeX source (only the source, nothing else), reworked according to this instruction while staying faithful to the original everywhere else:

{instruction}

Divergences (original -> rebuilt), for context:
{feedback}

Current source:
{tex}"""

GENERATE_COMPILE_FEEDBACK = """The LaTeX document below fails to compile with tectonic. Output the full corrected LaTeX source (only the source, nothing else) without losing content. Tectonic output tail:
{log}

Current source:
{tex}"""

GENERATE_BIB_FEEDBACK = """The LaTeX document below fails the bibliography check:
{violations}

Output the full corrected LaTeX source (only the source, nothing else) without losing content: the bibliography must be a filecontents* block writing {refs_bib}, with every cited key present as an entry.

Current source:
{tex}"""

DEFAULTS = {
    "agent": {
        "prompt": AGENT_RECONSTRUCT,
        "feedback": AGENT_FEEDBACK,
        "refine": AGENT_REFINE,
        "compile_feedback": AGENT_COMPILE_FEEDBACK,
        "bib_feedback": AGENT_BIB_FEEDBACK,
    },
    "generate": {
        "prompt": GENERATE_RECONSTRUCT,
        "feedback": GENERATE_FEEDBACK,
        "refine": GENERATE_REFINE,
        "compile_feedback": GENERATE_COMPILE_FEEDBACK,
        "bib_feedback": GENERATE_BIB_FEEDBACK,
    },
}


def fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template
