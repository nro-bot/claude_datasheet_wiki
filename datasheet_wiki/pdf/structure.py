"""Turn the raw PDF (outline + pages + links) into a tree of wiki sections.

A *section* is a node in the table of contents that owns a contiguous page
range. Its text is the concatenation of the pages it spans, and it carries the
list of page images to display alongside that text.

If a PDF has no usable outline (some scanned datasheets), we fall back to fixed
page-group sections so the tool still produces a usable wiki.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils import slugify
from .blocks import Block
from .extract import Link, OutlineItem, PageInfo


@dataclass
class Section:
    id: str
    slug: str
    title: str
    level: int
    start_page: int          # 0-based inclusive
    end_page: int            # 0-based inclusive
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    number: str = ""         # e.g. "4.3" parsed from the title if present
    text: str = ""
    page_images: List[str] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"sections/{self.id}.html"

    @property
    def short_title(self) -> str:
        """Title with the leading section number removed (it's shown separately,
        so this avoids "6 6. GPIO")."""
        t = self.title.strip()
        if self.number:
            stripped = re.sub(r"^" + re.escape(self.number) + r"\.?(?:\s+|$)", "", t)
            return stripped or t
        return t

    @property
    def page_label(self) -> str:
        if self.start_page == self.end_page:
            return f"p.{self.start_page + 1}"
        return f"pp.{self.start_page + 1}-{self.end_page + 1}"


def _unique(slug: str, used: Dict[str, int]) -> str:
    if slug not in used:
        used[slug] = 0
        return slug
    used[slug] += 1
    return f"{slug}-{used[slug]}"


def _parse_number(title: str) -> str:
    head = title.strip().split(None, 1)[0] if title.strip() else ""
    cleaned = head.rstrip(".")
    if cleaned and all(c.isdigit() or c == "." for c in cleaned) and any(c.isdigit() for c in cleaned):
        return cleaned
    return ""


def build_sections(
    outline: List[OutlineItem],
    pages: List[PageInfo],
    page_images: List[str],
    max_pages: int = 0,
    page_blocks: Optional[List[List[Block]]] = None,
) -> List[Section]:
    n_pages = len(pages)
    if max_pages:
        n_pages = min(n_pages, max_pages)

    if not outline:
        return _fallback_sections(pages, page_images, n_pages, page_blocks=page_blocks)

    # Keep only outline entries that point into our (possibly truncated) range.
    items = [o for o in outline if o.page < n_pages]
    if not items:
        return _fallback_sections(pages, page_images, n_pages, page_blocks=page_blocks)

    used: Dict[str, int] = {}
    sections: List[Section] = []
    # Each section starts at its page and ends just before the next entry whose
    # level is <= its own level (so a parent ends when the next sibling/uncle
    # begins, while its text still covers any intro before the first child).
    for i, item in enumerate(items):
        start = item.page
        end = n_pages - 1
        for j in range(i + 1, len(items)):
            if items[j].page > start:
                end = items[j].page - 1
                break
            if items[j].page == start:
                # sibling on the same page: this node owns only its start page
                end = start
                break
        end = max(end, start)
        sid = _unique(slugify(f"{item.title}") or f"sec-{i}", used)
        sections.append(
            Section(
                id=sid,
                slug=sid,
                title=item.title,
                level=item.level,
                start_page=start,
                end_page=end,
                number=_parse_number(item.title),
            )
        )

    _assign_parents(sections)
    _attach_content(sections, pages, page_images, n_pages, page_blocks)
    return sections


def _fallback_sections(
    pages: List[PageInfo], page_images: List[str], n_pages: int, group: int = 4,
    page_blocks: Optional[List[List[Block]]] = None,
) -> List[Section]:
    used: Dict[str, int] = {}
    sections: List[Section] = []
    for start in range(0, n_pages, group):
        end = min(start + group - 1, n_pages - 1)
        title = f"Pages {start + 1}-{end + 1}"
        sid = _unique(slugify(title), used)
        sections.append(
            Section(id=sid, slug=sid, title=title, level=1, start_page=start, end_page=end)
        )
    _attach_content(sections, pages, page_images, n_pages, page_blocks)
    return sections


def _assign_parents(sections: List[Section]) -> None:
    stack: List[Section] = []
    for sec in sections:
        while stack and stack[-1].level >= sec.level:
            stack.pop()
        if stack:
            sec.parent_id = stack[-1].id
            stack[-1].children.append(sec.id)
        stack.append(sec)


def _attach_content(
    sections: List[Section], pages: List[PageInfo], page_images: List[str], n_pages: int,
    page_blocks: Optional[List[List[Block]]] = None,
) -> None:
    for sec in sections:
        parts: List[str] = []
        imgs: List[str] = []
        blocks: List[Block] = []
        for p in range(sec.start_page, min(sec.end_page, n_pages - 1) + 1):
            parts.append(pages[p].text)
            if p < len(page_images):
                imgs.append(page_images[p])
            if page_blocks is not None and p < len(page_blocks):
                blocks.extend(page_blocks[p])
        sec.text = "\n".join(parts).strip()
        sec.page_images = imgs
        sec.blocks = blocks


def map_links_to_sections(links: List[Link], sections: List[Section]) -> Dict[int, str]:
    """Map a destination page -> the id of the most specific section owning it."""
    page_to_section: Dict[int, str] = {}
    # Sort so deeper (more specific) sections win for a given page.
    ordered = sorted(sections, key=lambda s: (s.start_page, -s.level))
    for sec in ordered:
        for p in range(sec.start_page, sec.end_page + 1):
            # prefer the deepest section; since ordered by -level, later writes
            # for the same page are shallower, so only set if unset or deeper.
            cur = page_to_section.get(p)
            if cur is None:
                page_to_section[p] = sec.id
    # second pass: prefer deepest section per page
    best: Dict[int, Section] = {}
    for sec in sections:
        for p in range(sec.start_page, sec.end_page + 1):
            if p not in best or sec.level > best[p].level:
                best[p] = sec
    return {p: s.id for p, s in best.items()}
