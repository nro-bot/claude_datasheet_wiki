"""Render JPG screenshots of a built wiki without a headless browser.

Uses WeasyPrint (HTML+CSS -> PDF) and PyMuPDF (PDF -> JPG). Because WeasyPrint
doesn't run JavaScript, the site's navigation is server-rendered so it still
shows up. Handy in sandboxes where a real browser can't be installed.

    pip install weasyprint           # needs pango/cairo system libs
    python scripts/screenshots.py <built-wiki-dir> <output-dir>
"""
import sys
from pathlib import Path

import fitz
from weasyprint import HTML, CSS

# Fixed desktop "viewport"; tall page so weasyprint doesn't fragment the flex
# layout across pages (its flex pagination is weak). We auto-trim the bottom.
SHEET = CSS(string="""
@page { size: 1180px 4200px; margin: 0; }
html, body { background: #0f1115; }
.topbar { position: static; }
.sidebar { position: static; height: auto; }
.layout { align-items: stretch; }
/* WeasyPrint can't toggle <details>; show the closed (default) state */
details.rawtext > .bodytext { display: none; }
""")
def _content_height(pix, scale):
    """Find the last row with real content (trim trailing uniform background,
    whether that background renders dark or white)."""
    w, h, n = pix.width, pix.height, pix.n
    data = pix.samples
    stride = w * n
    # scan only the content column (right of the ~300px-wide sidebar) so the
    # full-height sidebar doesn't make every row look like content
    cols = list(range(int(w * 0.34) * n, w * n - n, max(n * 12, n)))
    for y in range(h - 1, -1, -4):
        base = y * stride
        lums = [data[base + x] + data[base + x + 1] + data[base + x + 2] for x in cols]
        if max(lums) - min(lums) > 30:  # row has variation -> content
            return min(h, y + int(28 * scale))
    return h


def shot(html_path: Path, out_jpg: Path, scale: float = 1.25, max_h: int = 2000):
    pdf_bytes = HTML(filename=str(html_path)).write_pdf(stylesheets=[SHEET])
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    full = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    h = min(_content_height(full, scale), int(max_h * scale))
    clip = fitz.Rect(0, 0, page.rect.width, h / scale)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    out_jpg.write_bytes(pix.tobytes(output="jpeg", jpg_quality=72))
    doc.close()
    print(f"{out_jpg}  {out_jpg.stat().st_size // 1024} KB  ({pix.width}x{pix.height})")


if __name__ == "__main__":
    wiki = Path(sys.argv[1])
    outdir = Path(sys.argv[2])
    shot(wiki / "index.html", outdir / "overview.jpg")
    shot(wiki / "sections" / "3-timer-counter.html", outdir / "section-registers-code.jpg")
    shot(wiki / "sections" / "2-pin-configuration.html", outdir / "section-pinconfig.jpg")
