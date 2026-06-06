"""Render section text into safe, hyperlinked HTML.

The headline feature of the no-LLM tier lives here: datasheet cross references
("see Section 4.3", "Table 10-1", "page 42") are turned into real wiki links by
matching them against the section tree. This works with zero LLM calls.
"""
from __future__ import annotations

import html
import re
from typing import Dict, List

from ..enrich.format import TOKEN_RE, FormattedPage
from ..pdf.blocks import BOLD_END, BOLD_START, Block
from ..pdf.structure import Section

# "Section 4.3", "section 4.3.1", "Chapter 5", "see 4.3"
_REF_SECTION = re.compile(
    r"\b(?:(?:see\s+)?(?:Section|Sections|Chapter|Chapters)\s+)(\d+(?:\.\d+)*)", re.IGNORECASE
)
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


def _ref_subbers(number_index: Dict[str, str], page_index: Dict[int, str], root: str):
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

    return sec_sub, page_sub


def linkify(text: str, number_index: Dict[str, str], page_index: Dict[int, str], root: str = "") -> str:
    """Escape text, then turn datasheet cross references into links."""
    escaped = html.escape(text)
    sec_sub, page_sub = _ref_subbers(number_index, page_index, root)
    escaped = _REF_SECTION.sub(sec_sub, escaped)
    escaped = _REF_PAGE.sub(page_sub, escaped)
    return escaped


def linkify_html(html_str: str, number_index: Dict[str, str], page_index: Dict[int, str], root: str = "") -> str:
    """Cross-reference-link text that is *already* safe HTML (do not re-escape).

    The reference patterns ("Section 4.3", "page 42") contain no HTML-special
    characters and our LLM HTML is sanitised to attribute-free tags, so applying
    them directly to the markup cannot corrupt a tag."""
    sec_sub, page_sub = _ref_subbers(number_index, page_index, root)
    html_str = _REF_SECTION.sub(sec_sub, html_str)
    html_str = _REF_PAGE.sub(page_sub, html_str)
    return html_str


_HEADING_TAG = {2: "h4", 3: "h5", 4: "h6"}


def _codefold(text: str, summary: str, kind: str) -> str:
    """A monospace block that starts collapsed showing one line, expandable."""
    text = (text or "").strip()
    if not text:
        return ""
    peek = (summary or "").strip() or next((ln for ln in text.splitlines() if ln.strip()), "")
    peek = " ".join(peek.split())
    if len(peek) > 90:
        peek = peek[:90].rstrip() + "…"
    label = "Table text" if kind == "table" else "Figure text"
    return (
        f'<details class="codefold codefold-{kind}">'
        f'<summary><span class="cf-label">{label}</span> '
        f'<code>{html.escape(peek)}</code></summary>'
        f"<pre><code>{html.escape(text)}</code></pre></details>"
    )


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
            if b.text.strip():
                out.append(_codefold(b.text, "Text in figure", "fig"))
        elif b.kind == "codefold":
            cf = _codefold(b.text, b.summary, "table")
            if cf:
                out.append(cf)
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


# --- LLM-formatted page view ----------------------------------------------
# (format.py imports site.sanitize but not site.render, so there is no cycle.)
_P_WRAPPED_TOKEN = re.compile(r"<p>\s*(" + TOKEN_RE.pattern + r")\s*</p>")


def _asset_html(asset, root: str) -> str:
    """An embedded figure/table image, with its OCR text tucked into a codefold."""
    label = "Figure" if asset.kind == "figure" else "Table"
    cap = f"{label} — page {asset.page + 1}"
    img = (f'<img loading="lazy" src="{root}{html.escape(asset.image_rel)}" '
           f'alt="{label} on page {asset.page + 1}">')
    fig = (f'<figure class="dsfig dsasset dsasset-{asset.kind}">'
           f'<a href="{root}{html.escape(asset.image_rel)}" target="_blank" rel="noopener">{img}</a>'
           f'<figcaption>{cap}</figcaption></figure>')
    if (asset.text or "").strip():
        fig += _codefold(asset.text, None, "table" if asset.kind == "table" else "fig")
    return fig


def render_formatted_page(
    fp: "FormattedPage", number_index: Dict[str, str], page_index: Dict[int, str],
    root: str = "", show_page_label: bool = False,
) -> str:
    """Substitute a page's asset markers with embedded images and cross-link it."""
    assets = fp.assets

    def swap(i: int) -> str:
        return _asset_html(assets[i], root) if 0 <= i < len(assets) else ""

    out = fp.html
    # Promote `<p>[[marker]]</p>` to a block-level swap so a <figure> never nests
    # inside a <p> (which the HTML parser would auto-close, breaking layout). In
    # this pattern group 1 is the whole marker and group 2 its numeric index.
    out = _P_WRAPPED_TOKEN.sub(lambda m: swap(int(m.group(2))), out)
    out = TOKEN_RE.sub(lambda m: swap(int(m.group(1))), out)
    out = linkify_html(out, number_index, page_index, root)
    if show_page_label:
        out = (f'<p class="fmt-page" id="fmt-p{fp.page + 1}">'
               f'<span class="fmt-page-n">Page {fp.page + 1}</span></p>') + out
    return out


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
