"""Build the "LLM-formatted" HTML for a page from its items + the model output.

The flow per page:
  1. :meth:`PageFormatter.source_text` turns the page's items into one prompt
     string: prose inline, each figure/table replaced by a ``[[DSWASSET_n]]``
     marker (so the model never sees their scrambled OCR text).
  2. A backend reflows that into clean HTML, keeping the markers in place.
  3. :meth:`PageFormatter.format` sanitises the HTML and pairs it with the
     ordered asset list. The markers are substituted with embedded images later,
     at render time (see :func:`datasheet_wiki.site.render.render_formatted_page`).

If the model is unavailable or returns nothing usable, we assemble the same
items heuristically — the view still shows images instead of OCR orphans.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import List

from ..pdf.layout import strip_bold
from ..pdf.page_items import PageItem
from ..site.sanitize import sanitize_html

# Lenient matcher: the model occasionally adds spaces or underscores.
TOKEN_RE = re.compile(r"\[\[\s*DSWASSET[_\s]*(\d+)\s*\]\]")


def asset_token(i: int) -> str:
    return f"[[DSWASSET_{i}]]"


@dataclass
class Asset:
    kind: str            # 'figure' | 'table'
    image_rel: str
    text: str = ""       # OCR text, tucked into a collapsed block at render time
    page: int = 0

    def to_dict(self) -> dict:
        return {"kind": self.kind, "image_rel": self.image_rel, "text": self.text, "page": self.page}

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        return cls(kind=d.get("kind", "figure"), image_rel=d.get("image_rel", ""),
                   text=d.get("text", ""), page=int(d.get("page", 0)))


@dataclass
class FormattedPage:
    page: int
    html: str                       # sanitised, still containing [[DSWASSET_n]] markers
    assets: List[Asset] = field(default_factory=list)
    backend: str = "none"           # 'ollama'/'anthropic' or 'none' (heuristic fallback)

    def to_dict(self) -> dict:
        return {"page": self.page, "html": self.html,
                "assets": [a.to_dict() for a in self.assets], "backend": self.backend}

    @classmethod
    def from_dict(cls, d: dict) -> "FormattedPage":
        return cls(page=int(d.get("page", 0)), html=d.get("html", ""),
                   assets=[Asset.from_dict(a) for a in d.get("assets", [])],
                   backend=d.get("backend", "none"))


class PageFormatter:
    def __init__(self, backend) -> None:
        self.backend = backend

    @staticmethod
    def assets_of(items: List[PageItem]) -> List[Asset]:
        return [Asset(it.kind, it.image_rel, it.text, it.page) for it in items if it.kind != "text"]

    @staticmethod
    def source_text(items: List[PageItem]) -> str:
        """The prompt text: prose inline, assets as ordered marker tokens."""
        parts: List[str] = []
        ai = 0
        for it in items:
            if it.kind == "text":
                t = strip_bold(it.text).strip()
                if t:
                    parts.append(t)
            else:
                parts.append(asset_token(ai))
                ai += 1
        return "\n\n".join(parts)

    def format(self, page_index: int, items: List[PageItem], raw_html: str) -> FormattedPage:
        assets = self.assets_of(items)
        if raw_html and raw_html.strip():
            cleaned = sanitize_html(raw_html)
            cleaned = self._ensure_all_assets(cleaned, len(assets))
            if cleaned.strip():
                return FormattedPage(page_index, cleaned, assets, self.backend.name)
        # Fallback: deterministic assembly (still images-not-orphans).
        return FormattedPage(page_index, self._fallback_html(items), assets, "none")

    @staticmethod
    def _ensure_all_assets(html_str: str, n_assets: int) -> str:
        """Append any asset markers the model dropped, so no image is lost."""
        present = {int(m.group(1)) for m in TOKEN_RE.finditer(html_str)}
        missing = [i for i in range(n_assets) if i not in present]
        if missing:
            html_str += "".join(f"<p>{asset_token(i)}</p>" for i in missing)
        return html_str

    @staticmethod
    def _fallback_html(items: List[PageItem]) -> str:
        out: List[str] = []
        ai = 0
        for it in items:
            if it.kind == "text":
                t = strip_bold(it.text).strip()
                if t:
                    out.append(f"<p>{html.escape(t)}</p>")
            else:
                out.append(f"<p>{asset_token(ai)}</p>")
                ai += 1
        return "".join(out)
