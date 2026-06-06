"""Per-page extraction for the LLM-formatted view.

Where :mod:`datasheet_wiki.pdf.layout` produces heuristic web blocks, this module
splits a page into an ordered list of :class:`PageItem`s where every figure and
detected *table* is **cropped to an image** instead of being left as scrambled
OCR text. The prose items feed the LLM; the asset items become embedded images.

It reuses the pure helpers from :mod:`layout` (body-size, bold detection,
table/figure heuristics) so the two paths stay consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from ..utils import ensure_dir
from .layout import (
    _block_text_and_meta,
    _body_size,
    _gap_figures,
    _save_image_block,
    _single_column,
    is_table_block,
    looks_like_table_page,
    strip_bold,
)

Rect = Tuple[float, float, float, float]


@dataclass
class PageItem:
    kind: str            # 'text' | 'figure' | 'table'
    text: str = ""       # prose (text) or the asset's OCR text (figure/table)
    image_rel: str = ""  # asset image path, relative to the site root
    top: float = 0.0     # vertical position, for ordering
    page: int = 0        # 0-based source page


def _cluster_table_rects(
    rects: List[Tuple[Rect, str]], x_gap: float = 72.0, y_gap: float = 24.0
) -> List[Tuple[Rect, str]]:
    """Merge the per-column/per-cell blocks of one table into single regions.

    PDF extraction hands back a table as several short-token blocks — one per
    column (side by side) or per band (stacked). Cropping each individually gives
    ugly slivers, so we union any two blocks that are near each other in *both*
    axes (within ``x_gap`` horizontally and ``y_gap`` vertically) into one
    bounding rectangle, repeating until nothing else merges.
    """
    items = [([float(c) for c in bb], ocr) for bb, ocr in rects]
    changed = True
    while changed:
        changed = False
        out: List[Tuple[List[float], str]] = []
        for bb, ocr in items:
            for m in out:
                mb = m[0]
                near = not (
                    bb[2] + x_gap < mb[0] or mb[2] + x_gap < bb[0]
                    or bb[3] + y_gap < mb[1] or mb[3] + y_gap < bb[1]
                )
                if near:
                    mb[0], mb[1] = min(mb[0], bb[0]), min(mb[1], bb[1])
                    mb[2], mb[3] = max(mb[2], bb[2]), max(mb[3], bb[3])
                    out[out.index(m)] = (mb, (m[1] + "\n" + ocr).strip())
                    changed = True
                    break
            else:
                out.append((list(bb), ocr))
        items = out
    merged = [((b[0], b[1], b[2], b[3]), ocr) for b, ocr in items]
    merged.sort(key=lambda r: r[0][1])
    return merged


def _crop_rect(
    page, rect: Rect, page_index: int, figures_dir: Path, zoom: float,
    resume: bool, tag: str, idx: int, min_w: float = 40.0, min_h: float = 16.0,
) -> Optional[str]:
    """Rasterise a region of the page to a PNG; return its relative path or None."""
    import fitz

    r = fitz.Rect(rect) & page.rect
    if r.is_empty or r.width < min_w or r.height < min_h:
        return None
    pad = 4
    r = fitz.Rect(
        max(page.rect.x0, r.x0 - pad), max(page.rect.y0, r.y0 - pad),
        min(page.rect.x1, r.x1 + pad), min(page.rect.y1, r.y1 + pad),
    )
    ensure_dir(figures_dir)
    name = f"{tag}-p{page_index + 1:04d}-{idx}.png"
    target = figures_dir / name
    if not (resume and target.exists() and target.stat().st_size > 0):
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=r, alpha=False)
            pix.save(target)
        except Exception:
            return None
    return f"figures/{name}"


def extract_page_items(
    page, page_index: int, figures_dir: Path, fig_dpi: int = 130,
    min_fig_px: int = 48, resume: bool = True,
) -> List[PageItem]:
    pd = page.get_text("dict")
    _body_size(pd)  # (kept for parity with layout; body size unused here)
    zoom = fig_dpi / 72.0

    entries: List[Tuple[float, PageItem]] = []
    image_y: List[Tuple[float, float]] = []
    tbl_blocks: List[Tuple[Rect, str]] = []
    lefts: List[float] = []
    text_only: List[str] = []

    for b in pd.get("blocks", []):
        bb = b.get("bbox", (0, 0, 0, 0))
        if b.get("type") == 1:  # embedded raster image
            fig = _save_image_block(b, page_index, figures_dir, min_fig_px, page)
            if fig:
                entries.append((bb[1], PageItem("figure", text=fig.text, image_rel=fig.image_rel,
                                                top=bb[1], page=page_index)))
                image_y.append((bb[1], bb[3]))
            continue
        text, _max_size, _bold_frac, raw_lines = _block_text_and_meta(b)
        if not strip_bold(text).strip():
            continue
        text_only.append(text)
        lefts.append(bb[0])
        if is_table_block(raw_lines):
            ocr = "\n".join(strip_bold(ln).strip() for ln in raw_lines if strip_bold(ln).strip())
            tbl_blocks.append((tuple(bb), ocr))
        else:
            entries.append((bb[1], PageItem("text", text=text, top=bb[1], page=page_index)))

    # A page that is essentially one big table: crop the whole content as one image.
    if looks_like_table_page(text_only):
        rel = _crop_rect(page, tuple(page.rect), page_index, figures_dir, zoom, resume, "tblpage", 0)
        ocr = page.get_text("text").strip()
        if rel:
            return [PageItem("table", text=ocr, image_rel=rel, top=0.0, page=page_index)]
        return [PageItem("text", text=ocr, top=0.0, page=page_index)]

    # Merge the scattered table blocks into regions and crop each to one image.
    for i, (rect, ocr) in enumerate(_cluster_table_rects(tbl_blocks)):
        rel = _crop_rect(page, rect, page_index, figures_dir, zoom, resume, "tbl", i)
        if rel:
            entries.append((rect[1], PageItem("table", text=ocr, image_rel=rel, top=rect[1], page=page_index)))
        else:  # too small to crop usefully — keep the text so nothing is lost
            entries.append((rect[1], PageItem("text", text=ocr, top=rect[1], page=page_index)))

    # Vector/drawn figures sitting in blank gaps (single-column pages only).
    if _single_column(lefts):
        gap_entries = [(top, top, None) for top, _it in entries]
        for mid, _mid2, blk in _gap_figures(page, page_index, gap_entries, image_y,
                                             figures_dir, fig_dpi, resume):
            entries.append((mid, PageItem("figure", image_rel=blk.image_rel, top=mid, page=page_index)))

    entries.sort(key=lambda e: e[0])
    return [it for _top, it in entries]
