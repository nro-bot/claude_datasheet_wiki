# datasheet-wiki

Turn a microcontroller **datasheet PDF** into a **searchable, hyperlinked,
self-hosted wiki** — with an image of every source page, auto-linked cross
references ("see Section 4.3", "page 42"), detected registers/bit-fields, and
optional LLM-generated summaries and code examples.

Built for everything from the 30-page ATtiny85 datasheet to the 600-page RP2040
datasheet. Parsing can take minutes to hours depending on the tier you pick;
that's fine — you only do it once per datasheet.

> **Copyright-friendly by design.** The tool ships *only code*. You run it on
> *your own* copy of a PDF, on *your own* machine, and the generated wiki stays
> local. Datasheet PDFs and generated sites are git-ignored, so nothing
> copyrighted ever lands in this repo.

---

## Why

Manufacturer datasheets are giant PDFs with poor search, no deep links, and no
code. This builds a personal wiki out of one: fast full-text search, a clickable
section tree, the original page images side-by-side with cleaned-up text, and —
if you want — AI summaries and usage examples. Host it locally, link to it, grep
it, keep it forever.

## Three compute tiers (incl. fully local, no API)

| Tier | Backend | What you get | Needs |
|------|---------|--------------|-------|
| **small** | none (heuristics) | Page images, full-text search, auto cross-reference links, register/bit-field detection, code-block detection. **No LLM, runs on any laptop in minutes.** | nothing extra |
| **medium** | **local LLM via [Ollama](https://ollama.com)** | Everything in small **+** per-section plain-English summaries, structured register extraction, generated code examples, **+ local semantic search**. **Nothing leaves your machine.** | `ollama` + `uv sync --extra local` |
| **large** | **Claude API** | Highest-quality summaries, register extraction, and code examples. | `uv sync --extra api` + `ANTHROPIC_API_KEY` |

The cross-reference linking, register/code detection, page images, and full-text
search are **always** available — even in the no-LLM `small` tier — because they
come from parsing the PDF itself (text, the table of contents, and the
hyperlinks the datasheet authors already embedded).

---

## Quickstart

Uses [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
git clone https://github.com/nro-bot/claude_datasheet_wiki
cd claude_datasheet_wiki
uv sync                                # creates .venv and installs the CLI

# Build (small tier, no LLM, fast):
uv run datasheet-wiki build path/to/attiny85.pdf

# Serve it locally:
uv run datasheet-wiki serve wiki/attiny85
# → http://127.0.0.1:8000
```

`uv run` auto-syncs the environment, so the first command bootstraps everything.
(Prefer an activated venv? `source .venv/bin/activate` and drop the `uv run`
prefix. Prefer plain pip semantics? `uv pip install -e .` works too.)

No PDF handy? Generate a tiny synthetic one to see the whole thing work:

```bash
uv run python tests/make_sample_pdf.py sample.pdf
uv run datasheet-wiki build sample.pdf -o wiki/sample
uv run datasheet-wiki serve wiki/sample
```

### Medium tier (local LLM, nothing leaves your machine)

```bash
uv sync --extra local
ollama pull llama3.1          # or qwen2.5, mistral, phi3 …
uv run datasheet-wiki build rp2040.pdf --compute medium --model llama3.1
```

### Large tier (Claude API)

```bash
uv sync --extra api
export ANTHROPIC_API_KEY=sk-ant-...
uv run datasheet-wiki build rp2040.pdf --compute large
# For a 600-page datasheet with thousands of sections, a cheaper model saves a lot:
uv run datasheet-wiki build rp2040.pdf --compute large --model claude-haiku-4-5
```

---

## CLI

```
datasheet-wiki build  <pdf> [-o OUT] [-c {small,medium,large}] [options]
datasheet-wiki serve  <dir> [-p PORT]
datasheet-wiki info   <pdf> [--limit N]      # print the PDF outline & page count
```

Useful `build` options:

| Option | Effect |
|--------|--------|
| `--compute {small,medium,large}` | Pick a tier (default `small`). |
| `--backend {none,ollama,anthropic}` | Override the tier's backend. |
| `--model NAME` | LLM model id (Ollama or Claude). |
| `--dpi N` | Page-image resolution (tier default 120/150/200). |
| `--semantic` | Add local semantic search (needs `[local]` extra). |
| `--no-images` | Skip page images (smaller, faster). |
| `--max-pages N` | Only process the first N pages — great for a quick test on a 600-page PDF. |
| `--no-resume` | Ignore caches and rebuild from scratch. |

---

## How it works

```
PDF ─┬─ render every page → images/            (PyMuPDF)
     ├─ extract text + table of contents + embedded hyperlinks
     ├─ build a section tree from the outline
     ├─ enrich each section  ──►  none | ollama | anthropic   (cached to disk)
     ├─ build full-text search index (+ optional local embeddings)
     └─ render a static site (Jinja2)  →  index.html, sections/, search.html
```

- **Resumable.** Page rendering and per-section enrichment are cached in
  `.dsw-cache/`, keyed by content. Interrupt a multi-hour RP2040 run and
  re-run — it picks up where it left off.
- **Fully static output.** The wiki is plain HTML/CSS/JS with no build step and
  no server requirement. The search index and nav are emitted as JS globals, so
  search even works when you open the files directly (`file://`), not just via
  `datasheet-wiki serve`.
- **Cross-reference linking** turns "see Section 4.3", "Table 10-1", and
  "page 42" into real wiki links, with zero LLM calls.

## Output layout

```
wiki/<name>/
├── index.html              # overview + stats + table of contents
├── search.html             # client-side full-text (+ optional semantic) search
├── about.html              # provenance + copyright notice
├── sections/<id>.html      # one page per datasheet section
├── images/page-NNNN.png    # rendered source pages
├── data/search-index.js    # prebuilt search index (JS global)
└── assets/                 # css + js + nav.js
```

## Requirements

- Python 3.9+
- Core: `PyMuPDF`, `Jinja2` (installed automatically).
- `[local]` extra: `sentence-transformers`, `numpy` (medium-tier semantic search).
- `[api]` extra: `anthropic` (large tier).

## Hosting your own datasheet wiki

Each person processes their own legally-obtained PDF locally. To keep a wiki
around, just keep the generated `wiki/<name>/` directory — it's self-contained.
Serve it with `datasheet-wiki serve`, any static file server, or open
`index.html` directly. **Do not commit datasheet PDFs or generated wikis to a
public repo** (the included `.gitignore` blocks them by default).

## Development

```bash
uv sync --extra dev
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE). The license covers the generator code only, not
any datasheet you process with it.
