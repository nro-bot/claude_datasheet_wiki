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
