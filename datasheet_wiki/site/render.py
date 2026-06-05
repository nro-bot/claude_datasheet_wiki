"""Render section text into safe, hyperlinked HTML.

The headline feature of the no-LLM tier lives here: datasheet cross references
("see Section 4.3", "Table 10-1", "page 42") are turned into real wiki links by
matching them against the section tree. This works with zero LLM calls.
"""
from __future__ import annotations

import html
import re
from typing import Dict, List, Optional

from ..pdf.blocks import BOLD_END, BOLD_START, Block
from ..pdf.structure import Section

# "Section 4.3", "section 4.3.1", "Chapter 5", "see 4.3"
_REF_SECTION = re.compile(
    r"\b(?:(?:see\s+)?(?:Section|Sections|Chapter|Chapters)\s+)(\d+(?:\.\d+)*)", re.IGNORECASE
)
# "Table 10-1", "Figure 4-2", "Table 10.1"
_REF_FIGTAB = re.compile(r"\b((?:Table|Figure)\s+\d+[.\-]\d+[A-Za-z]?)\b", re.IGNORECASE)
# "page 42", "pages 42-44"
_REF_PAGE = re.compile(r"\bpages?\s+(\d+)", re.IGNORECASE)


def build_number_index(sections: List[Section]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for sec in sections:
        if sec.number and sec.number not in idx:
            idx[sec.number] = sec.id
    return idx


def build_page_index(sections: List[Section]) -> Dict[int, str]:
    best: Dict[int, Section] = {}
    for sec in sections:
        for p in range(sec.start_page, sec.end_page + 1):
            if p not in best or sec.level > best[p].level:
                best[p] = sec
    return {p: s.id for p, s in best.items()}


def _link(target_id: str, label: str, root: str = "") -> str:
    return f'<a class="xref" href="{root}sections/{html.escape(target_id)}.html">{label}</a>'


def linkify(text: str, number_index: Dict[str, str], page_index: Dict[int, str], root: str = "") -> str:
    """Escape text, then turn datasheet cross references into links."""
    escaped = html.escape(text)

    def sec_sub(m: re.Match) -> str:
        num = m.group(1)
        tgt = number_index.get(num)
        if not tgt:
            # try trimming to a parent number (e.g. 4.3.2 -> 4.3)
            parts = num.split(".")
            while len(parts) > 1 and ".".join(parts) not in number_index:
                parts = parts[:-1]
            tgt = number_index.get(".".join(parts))
        return _link(tgt, m.group(0), root) if tgt else m.group(0)

    def page_sub(m: re.Match) -> str:
        try:
            page0 = int(m.group(1)) - 1
        except ValueError:
            return m.group(0)
        tgt = page_index.get(page0)
        return _link(tgt, m.group(0), root) if tgt else m.group(0)

    escaped = _REF_SECTION.sub(sec_sub, escaped)
    escaped = _REF_PAGE.sub(page_sub, escaped)
    return escaped


_HEADING_TAG = {2: "h4", 3: "h5", 4: "h6"}


def _inline(text: str, number_index: Dict[str, str], page_index: Dict[int, str], root: str) -> str:
    """Escape + cross-reference-link text, then turn bold sentinels into <strong>."""
    out = linkify(text, number_index, page_index, root)
    out = out.replace(html.escape(BOLD_START), "<strong>").replace(html.escape(BOLD_END), "</strong>")
    out = out.replace(BOLD_START, "<strong>").replace(BOLD_END, "</strong>")
    return out


def render_blocks(
    blocks: List[Block], number_index: Dict[str, str], page_index: Dict[int, str], root: str = ""
) -> str:
    """Render reflowed/structured blocks (headings, paragraphs, lists, figures,
    whole-page-table notes) into web HTML."""
    if not blocks:
        return ""
    out: List[str] = []
    for b in blocks:
        if b.kind == "heading":
            tag = _HEADING_TAG.get(b.level, "h5")
            out.append(f"<{tag} class=\"fmt-h\">{_inline(b.text, number_index, page_index, root)}</{tag}>")
        elif b.kind == "list":
            lis = "".join(f"<li>{_inline(i, number_index, page_index, root)}</li>" for i in b.items)
            out.append(f"<ul class=\"fmt-list\">{lis}</ul>")
        elif b.kind == "figure":
            out.append(
                f'<figure class="dsfig"><img loading="lazy" src="{root}{html.escape(b.image_rel)}" '
                f'alt="Figure from page {b.page + 1}"></figure>'
            )
        elif b.kind == "table_note":
            if b.image_rel:
                link = f'<a href="{root}{html.escape(b.image_rel)}" target="_blank" rel="noopener">image of page {b.page + 1}</a>'
            else:
                link = f"image of page {b.page + 1}"
            out.append(f'<p class="tablenote">Detected table — see {link}.</p>')
        else:  # para
            txt = _inline(b.text, number_index, page_index, root)
            if txt.strip():
                out.append(f"<p>{txt}</p>")
    return "\n".join(out)


def render_body(
    text: str, number_index: Dict[str, str], page_index: Dict[int, str], root: str = ""
) -> str:
    """Turn raw section text into linked HTML paragraphs."""
    if not text.strip():
        return '<p class="muted">No extractable text on these pages — see the page images below.</p>'
    blocks = re.split(r"\n\s*\n", text)
    out: List[str] = []
    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue
        linked = linkify(blk, number_index, page_index, root)
        linked = linked.replace("\n", "<br>")
        out.append(f"<p>{linked}</p>")
    return "\n".join(out)
