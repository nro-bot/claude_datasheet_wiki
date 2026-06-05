"""PDF extraction built on PyMuPDF (fitz).

Responsible for everything we can get *for free*, with no LLM, from the source
PDF: page images, per-page text, the document outline (table of contents) and —
crucially — the internal hyperlinks the datasheet authors already embedded
(TOC links, "see Section x.y" cross references, register links, etc.). Those
become real wiki hyperlinks in the small/no-LLM tier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from ..utils import Progress, ensure_dir, log


@dataclass
class OutlineItem:
    level: int
    title: str
    page: int  # 0-based page index


@dataclass
class Link:
    """An internal GoTo link found on a page (PDF coordinates, 0-based pages)."""

    src_page: int
    dest_page: int
    rect: Tuple[float, float, float, float]
    text: str = ""  # the text under the link rectangle, if any


@dataclass
class PageInfo:
    index: int
    width: float
    height: float
    text: str
    image_rel: Optional[str] = None  # path relative to the images dir


class PdfDocument:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.doc = fitz.open(self.path)

    # -- metadata -----------------------------------------------------------
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def title(self) -> str:
        meta = self.doc.metadata or {}
        return (meta.get("title") or "").strip() or self.path.stem

    def metadata(self) -> dict:
        return dict(self.doc.metadata or {})

    # -- outline / TOC ------------------------------------------------------
    def outline(self) -> List[OutlineItem]:
        items: List[OutlineItem] = []
        for level, title, page in self.doc.get_toc(simple=True):
            # get_toc pages are 1-based; -1 means "no destination".
            idx = max(page - 1, 0)
            title = " ".join(str(title).split())
            if title:
                items.append(OutlineItem(level=level, title=title, page=idx))
        return items

    # -- text ---------------------------------------------------------------
    def page_text(self, index: int) -> str:
        return self.doc[index].get_text("text")

    def pages_text(self, limit: int = 0) -> List[PageInfo]:
        n = self.page_count if not limit else min(limit, self.page_count)
        out: List[PageInfo] = []
        prog = Progress(n, "extract text")
        for i in range(n):
            page = self.doc[i]
            rect = page.rect
            out.append(
                PageInfo(index=i, width=rect.width, height=rect.height, text=page.get_text("text"))
            )
            prog.update()
        prog.close()
        return out

    # -- links --------------------------------------------------------------
    def internal_links(self, limit: int = 0) -> List[Link]:
        """Extract internal GoTo links (cross references) embedded in the PDF."""
        n = self.page_count if not limit else min(limit, self.page_count)
        links: List[Link] = []
        for i in range(n):
            page = self.doc[i]
            for lk in page.get_links():
                if lk.get("kind") != fitz.LINK_GOTO:
                    continue
                dest = lk.get("page", -1)
                if dest is None or dest < 0:
                    continue
                rect = lk.get("from")
                if rect is None:
                    continue
                rtuple = (rect.x0, rect.y0, rect.x1, rect.y1)
                text = page.get_textbox(rect).strip() if rect else ""
                links.append(Link(src_page=i, dest_page=dest, rect=rtuple, text=text))
        return links

    # -- images -------------------------------------------------------------
    def render_pages(
        self,
        out_dir: Path,
        dpi: int = 120,
        fmt: str = "png",
        limit: int = 0,
        resume: bool = True,
    ) -> List[str]:
        """Render each page to an image. Returns relative filenames.

        Resumable: existing images are skipped, which matters a lot for the
        600-page datasheets where a render can take a long time.
        """
        out_dir = ensure_dir(Path(out_dir))
        n = self.page_count if not limit else min(limit, self.page_count)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        rels: List[str] = []
        prog = Progress(n, "render pages")
        for i in range(n):
            name = f"page-{i + 1:04d}.{fmt}"
            target = out_dir / name
            if not (resume and target.exists() and target.stat().st_size > 0):
                pix = self.doc[i].get_pixmap(matrix=matrix, alpha=False)
                pix.save(target)
            rels.append(name)
            prog.update()
        prog.close()
        return rels

    def close(self) -> None:
        self.doc.close()

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
