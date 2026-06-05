"""End-to-end test of the small (no-LLM) tier on a synthetic datasheet.

The `wiki` fixture (a built small-tier wiki) lives in tests/conftest.py.
"""
from __future__ import annotations

from pathlib import Path


def test_core_pages_exist(wiki: Path):
    for name in ("index.html", "search.html", "about.html"):
        assert (wiki / name).exists()
    assert (wiki / "data" / "search-index.js").exists()
    assert len(list((wiki / "sections").glob("*.html"))) == 5


def test_sidebar_nav_is_server_rendered(wiki: Path):
    # Navigation must work without JS: the section tree is in the HTML itself.
    index = (wiki / "index.html").read_text()
    assert 'id="nav-tree"' in index
    assert "sections/1-overview.html" in index  # a nav link, server-side


def test_page_images_rendered(wiki: Path):
    imgs = list((wiki / "images").glob("*.png"))
    assert len(imgs) == 5
    assert all(i.stat().st_size > 0 for i in imgs)


def test_cross_reference_links(wiki: Path):
    overview = (wiki / "sections" / "1-overview.html").read_text()
    # "see Section 2" / "see Section 3" / "page 4" should become wiki links
    assert "2-pin-configuration.html" in overview
    assert "3-timer-counter.html" in overview
    assert 'class="xref"' in overview


def test_register_detection(wiki: Path):
    pinconf = (wiki / "sections" / "2-pin-configuration.html").read_text()
    assert "DDRB" in pinconf
    assert 'class="bits"' in pinconf  # bit-field table rendered


def test_code_detection(wiki: Path):
    timer = (wiki / "sections" / "3-timer-counter.html").read_text()
    assert "code-examples" in timer
    assert "avr/io.h" in timer


def test_section_layout_and_provenance(wiki: Path):
    html = (wiki / "sections" / "3-timer-counter.html").read_text()
    # source page images moved up: after summary, before the formatted text
    assert html.index('class="summary"') < html.index('class="pageimages"') < html.index('class="formatted"')
    # it is clear which pages the summary/section comes from
    assert "generated from p.4" in html
    assert "Page 4" in html  # captioned page image


def test_lightbox_wired(wiki: Path):
    assert (wiki / "assets" / "lightbox.js").exists()
    section = (wiki / "sections" / "2-pin-configuration.html").read_text()
    assert "assets/lightbox.js" in section
    # no-JS fallback: page-image thumbnails are still real links to the image
    assert 'class="thumb"' in section and "images/page-0002.png" in section


def test_how_page(wiki: Path):
    how = (wiki / "how.html").read_text()
    assert "How this wiki is generated" in how
    assert "Cross-reference links" in how and "Registers" in how
    assert "120 DPI" in how  # the small tier's render DPI


def test_code_toc_page(wiki: Path):
    code = (wiki / "code.html").read_text()
    assert "Code examples" in code
    # lists the timer section and shows its code, linked back to the section
    assert "3-timer-counter.html" in code
    assert "avr/io.h" in code


def test_search_index_has_terms(wiki: Path):
    js = (wiki / "data" / "search-index.js").read_text()
    assert js.startswith("window.DSW_SEARCH = ")
    assert "timer" in js.lower()
