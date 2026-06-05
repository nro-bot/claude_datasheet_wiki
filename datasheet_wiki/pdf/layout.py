"""Turn a PDF page into structured, web-ready :class:`Block`s.

The goal is to undo the "newline after every visual line" that plain PDF text
extraction produces, and to recover light structure (headings, bold, bullets),
inline figures, and whole-page tables — without an LLM.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from ..utils import ensure_dir
from .blocks import BOLD_END, BOLD_START, Block

BULLETS = "•·–—*▪◦‣"
_BULLET_RE = re.compile(r"^\s*(?:[" + re.escape(BULLETS) + r"]|-\s|\(\d+\)|\d+[.)])\s*")
_SENT_END = (".", ":", ";", "!", "?")


# ---------------------------------------------------------------------------
# Pure text helpers (unit-tested without a PDF)
# ---------------------------------------------------------------------------
def join_lines(lines: List[str]) -> str:
    """Reflow a block's visual lines into one string.

    Collapses the "Bit / 7 / 6 / 5 / 4" column fragmentation into "Bit 7 6 5 4",
    and de-hyphenates words broken across lines.
    """
    out = ""
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif out.endswith("-") and len(out) > 1 and out[-2].isalpha():
            out = out[:-1] + ln  # de-hyphenate
        else:
            out = out + " " + ln
    # tidy bold sentinels: merge adjacent bold runs
    out = out.replace(BOLD_END + " " + BOLD_START, " ").replace(BOLD_END + BOLD_START, "")
    return out.strip()


def strip_bold(text: str) -> str:
    return text.replace(BOLD_START, "").replace(BOLD_END, "")


def is_data_like(text: str) -> bool:
    """A short, value-ish fragment (table cell), not prose."""
    t = strip_bold(text).strip()
    if not t or len(t) > 14 or t.endswith(_SENT_END):
        return False
    return " " not in t or len(t) <= 8


def merge_short_blocks(blocks: List[Block]) -> List[Block]:
    """Merge runs of >=3 consecutive short, data-like paragraphs (the scattered
    cells of a small table) into one collapsed code block: the compact line is
    shown while collapsed, the raw cells when expanded."""
    out: List[Block] = []
    run: List[Block] = []

    def flush():
        if len(run) >= 3:
            cells = [strip_bold(b.text) for b in run if b.text]
            out.append(
                Block(
                    kind="codefold",
                    summary=" ".join(cells),
                    text="\n".join(cells),
                    page=run[0].page,
                )
            )
        else:
            out.extend(run)
        run.clear()

    for b in blocks:
        if b.kind == "para" and is_data_like(b.text):
            run.append(b)
        else:
            flush()
            out.append(b)
    flush()
    return out


def looks_like_table_page(block_texts: List[str]) -> bool:
    """True when a page is dominated by short table cells rather than prose."""
    texts = [strip_bold(t).strip() for t in block_texts if strip_bold(t).strip()]
    if len(texts) < 10:
        return False
    short = sum(1 for t in texts if len(t) <= 8)
    words = sum(len(t.split()) for t in texts)
    return short / len(texts) >= 0.7 and words < 3 * len(texts)


def classify_block(text: str, max_size: float, body_size: float, bold_frac: float) -> Block:
    """Decide whether a reflowed block is a heading, a list, or a paragraph."""
    plain = strip_bold(text).strip()
    if not plain:
        return Block(kind="para", text="")

    if _BULLET_RE.match(plain):
        items = _split_list(text)
        if items:
            return Block(kind="list", items=items)

    big = bool(body_size) and max_size >= body_size * 1.18
    numbered = bool(re.match(r"^\d+(\.\d+)*\s+\S", plain))
    short = len(plain) <= 90
    heading = short and not plain.endswith((".", ";")) and (
        big or bold_frac > 0.6 or (numbered and bold_frac > 0.3)
    )
    if heading:
        if body_size and max_size >= body_size * 1.6:
            level = 2
        elif big:
            level = 3
        else:
            level = 4
        return Block(kind="heading", text=text, level=level)

    return Block(kind="para", text=text)


def _split_list(text: str) -> List[str]:
    plain = strip_bold(text)
    parts = re.split(r"\s+(?=[" + re.escape(BULLETS) + r"]\s|\(\d+\)\s|\d+[.)]\s|-\s)", plain)
    items = [_BULLET_RE.sub("", p).strip() for p in parts]
    return [i for i in items if i]


# ---------------------------------------------------------------------------
# PDF-dependent extraction
# ---------------------------------------------------------------------------
def _is_bold(span: dict) -> bool:
    if span.get("flags", 0) & 16:
        return True
    font = (span.get("font") or "").lower()
    return any(k in font for k in ("bold", "black", "heavy", "semibold"))


def _block_text_and_meta(block: dict) -> Tuple[str, float, float, List[str]]:
    """Return (reflowed text w/ bold sentinels, max font size, bold char frac,
    the raw per-line strings)."""
    lines: List[str] = []
    max_size = 0.0
    bold_chars = total_chars = 0
    for line in block.get("lines", []):
        parts: List[str] = []
        for span in line.get("spans", []):
            t = span.get("text", "")
            if not t:
                continue
            max_size = max(max_size, span.get("size", 0.0))
            total_chars += len(t)
            if _is_bold(span):
                bold_chars += len(t)
                t = BOLD_START + t + BOLD_END
            parts.append(t)
        if parts:
            lines.append("".join(parts))
    frac = (bold_chars / total_chars) if total_chars else 0.0
    return join_lines(lines), max_size, frac, lines


def is_table_block(lines: List[str]) -> bool:
    """A single text block that is really a table column/grid: many lines that
    are each a short token."""
    cleaned = [strip_bold(ln).strip() for ln in lines]
    cleaned = [c for c in cleaned if c]
    if len(cleaned) < 3:
        return False
    short = sum(1 for c in cleaned if len(c) <= 8 and len(c.split()) <= 2)
    return short / len(cleaned) >= 0.6


def _body_size(page_dict: dict) -> float:
    counts: Counter = Counter()
    for b in page_dict.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                counts[round(span.get("size", 0), 1)] += len(span.get("text", ""))
    return counts.most_common(1)[0][0] if counts else 11.0


def _variance(pix) -> int:
    data = pix.samples
    if not data:
        return 0
    step = max(1, len(data) // 4000)
    sample = data[::step]
    return max(sample) - min(sample)


def extract_page_blocks(
    page,
    page_index: int,
    figures_dir: Optional[Path] = None,
    fig_dpi: int = 110,
    min_fig_px: int = 48,
    extract_figures: bool = True,
    resume: bool = True,
) -> List[Block]:
    pd = page.get_text("dict")
    body = _body_size(pd)

    # walk blocks in document order, keeping (top, bottom, Block)
    entries: List[Tuple[float, float, Block]] = []
    text_only: List[str] = []
    image_y: List[Tuple[float, float]] = []
    lefts: List[float] = []

    for b in pd.get("blocks", []):
        bb = b.get("bbox", (0, 0, 0, 0))
        if b.get("type") == 1:
            if extract_figures and figures_dir is not None:
                fig = _save_image_block(b, page_index, figures_dir, min_fig_px, page)
                if fig:
                    entries.append((bb[1], bb[3], fig))
                    image_y.append((bb[1], bb[3]))
            continue
        text, max_size, bold_frac, raw_lines = _block_text_and_meta(b)
        if not strip_bold(text).strip():
            continue
        text_only.append(text)
        lefts.append(bb[0])
        if is_table_block(raw_lines):
            cells = [strip_bold(ln).strip() for ln in raw_lines if strip_bold(ln).strip()]
            blk = Block(kind="codefold", summary=" ".join(cells),
                        text="\n".join(cells), page=page_index)
        else:
            blk = classify_block(text, max_size, body, bold_frac)
            blk.page = page_index
        entries.append((bb[1], bb[3], blk))

    if looks_like_table_page(text_only):
        raw = page.get_text("text").strip()
        out = [Block(kind="table_note", page=page_index)]
        if raw:
            out.append(Block(kind="codefold", text=raw, page=page_index))
        return out

    # inline (vector) figures: large blank-looking gaps that actually contain
    # drawing. Only attempt on roughly single-column pages to stay safe.
    if extract_figures and figures_dir is not None and _single_column(lefts):
        entries += _gap_figures(page, page_index, entries, image_y, figures_dir, fig_dpi, resume)

    entries.sort(key=lambda e: e[0])
    blocks = [e[2] for e in entries]
    return merge_short_blocks(blocks)


def _single_column(lefts: List[float]) -> bool:
    if len(lefts) < 2:
        return True
    lo, hi = min(lefts), max(lefts)
    return (hi - lo) < 120  # all text starts at a similar x


def _save_image_block(
    b: dict, page_index: int, figures_dir: Path, min_fig_px: int, page=None
) -> Optional[Block]:
    if b.get("width", 0) < min_fig_px or b.get("height", 0) < min_fig_px:
        return None
    img = b.get("image")
    if not img:
        return None
    ext = b.get("ext", "png")
    ensure_dir(figures_dir)
    name = f"fig-p{page_index + 1:04d}-{b.get('number', 0)}.{ext}"
    (figures_dir / name).write_bytes(img)
    # any text overlaid on the figure -> show it as a collapsed code block
    region_text = ""
    if page is not None and b.get("bbox"):
        try:
            import fitz

            region_text = page.get_textbox(fitz.Rect(b["bbox"])).strip()
        except Exception:
            region_text = ""
    return Block(kind="figure", image_rel=f"figures/{name}", text=region_text, page=page_index)


def _gap_figures(
    page, page_index, entries, image_y, figures_dir, fig_dpi, resume
) -> List[Tuple[float, float, Block]]:
    import fitz

    rows = sorted([(t, b) for (t, b, _blk) in entries], key=lambda r: r[0])
    if len(rows) < 2:
        return []
    left = page.rect.x0 + 36
    right = page.rect.x1 - 36
    page_h = page.rect.height
    zoom = fig_dpi / 72.0
    found: List[Tuple[float, float, Block]] = []

    for (t0, b0), (t1, _b1) in zip(rows, rows[1:]):
        gap_top, gap_bot = b0, t1
        if gap_bot - gap_top < max(64.0, page_h * 0.12):
            continue
        if any(not (gap_bot <= iy0 or gap_top >= iy1) for iy0, iy1 in image_y):
            continue
        rect = fitz.Rect(left, gap_top + 2, right, gap_bot - 2)
        if rect.is_empty or rect.width < 60 or rect.height < 50:
            continue
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        except Exception:
            continue
        if _variance(pix) < 22:  # blank gap, no drawing
            continue
        ensure_dir(figures_dir)
        name = f"fig-p{page_index + 1:04d}-gap{int(gap_top)}.png"
        target = figures_dir / name
        if not (resume and target.exists()):
            pix.save(target)
        mid = (gap_top + gap_bot) / 2
        found.append((mid, mid, Block(kind="figure", image_rel=f"figures/{name}", page=page_index)))
    return found
