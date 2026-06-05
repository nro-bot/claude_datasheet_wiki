"""Structured content blocks extracted from a PDF page.

A page's raw text (lots of hard line breaks) is turned into a sequence of these
blocks, which the site renders as proper web content: headings, paragraphs,
bullet lists, inline figures, and "this page is a table" notes.

Bold runs inside `text` are wrapped in the private-use sentinels BOLD_START /
BOLD_END; the renderer escapes the text and then swaps those for <strong>.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

BOLD_START = ""
BOLD_END = ""


@dataclass
class Block:
    kind: str               # 'para' | 'heading' | 'list' | 'figure' | 'table_note'
    text: str = ""          # para/heading (may contain BOLD_* sentinels)
    level: int = 0          # heading level (2 = biggest, 4 = smallest)
    items: List[str] = field(default_factory=list)  # list items
    image_rel: str = ""     # figure image, or page image for a table_note
    page: int = 0           # 0-based source page
