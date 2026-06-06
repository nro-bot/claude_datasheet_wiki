"""A tiny allowlist HTML sanitizer (standard library only).

LLM-formatted page HTML is injected into section pages with Jinja's ``|safe``,
so it must be reduced to a small set of structural, text-level tags with **no
attributes**, no scripts, and no styles. Anything outside the allowlist is
dropped, but its text content is kept so no prose is lost. Built on
``html.parser`` — no third-party dependency.

This deliberately drops ``<table>``/``<img>``/``<a>``: tables and figures are
shown as embedded images (substituted in for the asset markers), and the model
is instructed not to emit links or raw images.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import List, Set

# Structural, text-level tags an LLM may reasonably emit when reflowing a
# datasheet page into clean HTML. No attributes are ever kept.
ALLOWED_TAGS: Set[str] = {
    "p", "br", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "strong", "b", "em", "i", "code", "pre",
    "blockquote", "sub", "sup",
}
# Tags whose *content* is discarded entirely (not just the tag itself).
_DROP_CONTENT: Set[str] = {"script", "style", "head", "title", "meta", "link"}
# Tags that never get a closing tag.
_VOID: Set[str] = {"br"}
# A handful of synonyms the model might emit, remapped onto an allowed tag.
_REMAP = {"h1": "h2", "b": "strong", "i": "em"}

_EMPTY_P_RE = re.compile(r"<p>\s*</p>")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self._skip_depth = 0  # >0 while inside a drop-content element

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = _REMAP.get(tag, tag)
        if tag in _DROP_CONTENT:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _VOID:
            self.out.append(f"<{tag}>")
        elif tag in ALLOWED_TAGS:
            self.out.append(f"<{tag}>")
        # otherwise: drop the tag but keep its (text) children

    def handle_startendtag(self, tag: str, attrs) -> None:
        tag = _REMAP.get(tag, tag)
        if not self._skip_depth and tag in _VOID:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = _REMAP.get(tag, tag)
        if tag in _DROP_CONTENT:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in ALLOWED_TAGS and tag not in _VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        # Re-escape: convert_charrefs already decoded entities, so this neutralises
        # any stray angle brackets the model emitted as text.
        self.out.append(html.escape(data, quote=False))


def sanitize_html(raw: str) -> str:
    """Reduce arbitrary model HTML to a safe allowlist fragment."""
    if not raw:
        return ""
    p = _Sanitizer()
    p.feed(raw)
    p.close()
    cleaned = "".join(p.out)
    cleaned = _EMPTY_P_RE.sub("", cleaned)
    return cleaned.strip()
