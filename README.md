# paritex

[![pypi](https://img.shields.io/pypi/v/paritex.svg)](https://pypi.org/project/paritex/)

Reconstruct papers as LaTeX with an AI backend, re-render with [tectonic](https://tectonic-typesetting.github.io), and measure how faithful the reconstruction is.

Companion to [hallubib](https://github.com/endremborza/hallubib): hallubib asks *are your references real?*, paritex asks *is this LaTeX really your paper?*

## Usage

```bash
paritex fetch                        # download the demo paper set into papers/
paritex reconstruct papers/bitcoin.pdf --rounds 3   # init + AI reconstruct + render + eval
```

`reconstruct` on a PDF creates a *reconstruction project* directory (`bitcoin/`) and runs the loop: AI backend writes `main.tex` (+ `refs.bib`), tectonic renders it to `main.pdf`, and the result is compared word-level against the original. Render failures and text divergences are fed back to the backend for up to `--rounds` passes, stopping early at `--target` parity.

A project directory is self-contained:

```
bitcoin/
  original.pdf   # the source paper
  assets/        # raster images extracted from it, for \includegraphics
  main.tex       # the reconstruction (backend-written)
  refs.bib       # its bibliography
  main.pdf       # tectonic render
  report.json    # parity ratio, page counts, all divergences
```

The steps are also available separately:

```bash
paritex init papers/attention.pdf    # just create the project dir + extract assets
paritex render attention             # tectonic main.tex
paritex eval attention               # compare main.pdf to original.pdf
paritex parity original.pdf other.pdf  # bare two-PDF comparison
```

## The report

`report.json` is a serialization contract — version-stamped, deterministically ordered, meant to be committed and rendered by consumers:

```json
{
 "paritex_version": "0.1.0",
 "parity": {
  "ratio": 0.992,
  "divergences": [
   {"kind": "missing", "original": "...", "rebuilt": "...", "page": 3}
  ]
 },
 "pages_original": 15,
 "pages_rebuilt": 15
}
```

`kind` is `missing` / `added` / `changed`, `page` is where the divergence sits in the original — enough context to show which parts of the paper survived reconstruction verbatim.

## Backends

The AI backend is a configured command; three are built in (`paritex backends` lists them):

- `claude-code` (default) — runs the [Claude Code](https://claude.com/claude-code) CLI as an agent inside the project dir; it reads `original.pdf` itself, writes `main.tex`/`refs.bib`, and may run tectonic to self-check. **Auth: the box's Claude Code login.** The Anthropic auth env vars (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`) are scrubbed from the child environment, so a key exported in your shell can never silently take precedence over the login and bill your API account.
- `claude-api` — the same agent command, but **billed to the API**: it refuses to start unless `ANTHROPIC_API_KEY` is set, and passes it through. Spending credits is an explicit choice of backend, never a side effect of the environment.
- `claude-gen` — plain one-shot generation on the box login: the prompt (with the extracted paper text) goes in, LaTeX comes out on stdout; the bibliography arrives as a `filecontents*` block that paritex materializes as `refs.bib`.

All three come from one factory, `claude_backend(name, auth="login"|"api", allowed_tools=..., mode=...)`, which consumers use to build their own flavors (e.g. with extra allowed tools). Auth is expressed through three generic spec keys any backend can use: `env` (a table of variables set for the child), `drop_env` (variables scrubbed from it), and `require_env` (variables that must be present or the run fails before spawning).

Any command can be a backend via `paritex.toml` (looked up in the working directory, then `~/.config/paritex.toml`, or passed with `--config`):

```toml
default = "codex"

[backends.codex]
mode = "agent"                 # the command writes main.tex itself, cwd = project dir
argv = ["codex", "exec", "--full-auto", "{prompt}"]
timeout = 3600

[backends.llm-cli]
mode = "generate"              # stdout becomes main.tex (code fences stripped)
argv = ["llm", "-m", "gpt-5"]  # no {prompt} in argv -> prompt is piped to stdin
prompt_file = "my-prompt.txt"  # override the default prompt template
```

Per-backend `prompt`, `feedback`, and `compile_feedback` templates (inline or `*_file`) override the defaults in `paritex/prompts.py`; placeholders like `{pdf}`, `{assets}`, `{text}`, `{ratio}`, `{feedback}`, `{log}` are substituted literally, so LaTeX braces are safe.

Tables, figures, and bibliographies are covered by the default prompts: tables must be rebuilt as `tabular` content, extracted `assets/` images are offered for `\includegraphics` (with TikZ as the fallback for vector diagrams), and references go through `refs.bib` so tectonic's bibtex pass reproduces the reference list — all of which the word-level parity check then verifies.

## Demo papers

`paritex fetch` downloads a small set of famous, shortish, layout-diverse papers to exercise the loop: attention (Transformers; single-column, tables), gan, word2vec, resnet (two-column CVPR), gw150914 (LIGO; two-column REVTeX), bitcoin (whitepaper with diagrams).

## Python API

```python
from paritex import init_project, load_backends, reconstruct

backends, default = load_backends()
project = init_project(Path("papers/gan.pdf"))
report = reconstruct(project, backends[default], rounds=3, target=0.98, on_event=print)
print(report.parity.ratio, report.pages_original, report.pages_rebuilt)
```

`on_event` receives a `Progress` per step — backend start, render ok/fail, gate ok/fail, parity ratio and divergence count per round — so a consumer can stream run progress to a terminal or UI instead of wrapping the loop in threads.
