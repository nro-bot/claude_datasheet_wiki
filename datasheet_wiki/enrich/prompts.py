"""Prompts shared by the LLM backends (Ollama + Anthropic).

We ask the model for a single JSON object so the same parser works regardless
of which backend produced it.
"""
from __future__ import annotations

SYSTEM = (
    "You are an expert embedded-systems engineer writing a concise, accurate "
    "wiki entry for one section of a microcontroller datasheet. Be precise and "
    "never invent register names, bit fields, or addresses that are not present "
    "in the provided text."
)

JSON_INSTRUCTIONS = """\
Return ONLY a single JSON object (no markdown fences, no prose) with this shape:
{
  "summary": "2-4 sentence plain-English explanation of what this section covers and why it matters to a developer",
  "keywords": ["short", "search", "terms"],
  "registers": [
    {
      "name": "REGISTER_NAME",
      "address": "0x.. if stated, else empty",
      "description": "one line",
      "fields": [
        {"bits": "7", "name": "FIELD", "access": "R/W if stated", "description": "one line"}
      ]
    }
  ],
  "code_examples": [
    {"title": "short title", "language": "c|asm|python", "code": "a minimal, correct usage example"}
  ]
}
Rules:
- Only include registers/fields that are clearly described in the text.
- code_examples: include at most 1 short, practical example IF the section
  describes a peripheral a developer would program; otherwise use [].
- Keep summary under 80 words.
"""


def build_user_prompt(title: str, text: str, max_chars: int = 8000) -> str:
    snippet = text.strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n...[truncated]..."
    return (
        f"Datasheet section title: {title}\n\n"
        f"Section text:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
        f"{JSON_INSTRUCTIONS}"
    )


# --- page formatting (the "LLM-formatted" page view) -----------------------
# A separate task from enrichment: reflow one page's raw extracted text into
# clean, readable HTML. Figures and detected tables are passed in as opaque
# [[DSWASSET_n]] markers (they are rendered as embedded images), so the model
# never has to deal with — or leak — their scrambled OCR text.
FORMAT_SYSTEM = (
    "You reformat one page of a microcontroller datasheet into clean, readable "
    "HTML. You preserve the original wording and technical detail exactly — you "
    "never summarise, invent, translate, or drop technical content. You output "
    "only an HTML fragment using these tags: <h2>-<h6>, <p>, <ul>, <ol>, <li>, "
    "<strong>, <em>, <code>, <pre>. You never output <html>, <body>, <table>, "
    "<img>, links, styles, or scripts."
)

FORMAT_INSTRUCTIONS = """\
Reflow the page text above into clean HTML:
- Join lines that the PDF split mid-sentence back into proper paragraphs, and
  de-hyphenate words broken across a line break.
- Use a heading tag for a section title, a list for bulleted or numbered items,
  and <pre><code> for code or assembly listings (keep their line breaks).
- Markers like [[DSWASSET_0]] stand for a figure or table that is shown as an
  image. Keep every marker EXACTLY as written, on its own line, in its original
  position. Do not describe, expand, renumber, or remove them.
- Drop running headers/footers, bare page numbers, and stray OCR fragments.
Return ONLY the HTML fragment — no markdown code fences and no commentary."""


def build_format_prompt(text: str, max_chars: int = 12000) -> str:
    snippet = text.strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n...[truncated]..."
    return (
        f"Page text:\n\"\"\"\n{snippet}\n\"\"\"\n\n{FORMAT_INSTRUCTIONS}"
    )
