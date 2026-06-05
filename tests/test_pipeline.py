"""End-to-end test of the small (no-LLM) tier on a synthetic datasheet.

The `wiki` fixture (a built small-tier wiki) lives in tests/conftest.py.
"""
from __future__ import annotations

from pathlib import Path


def test_core_pages_exist(wiki: Path):
    for name in ("index.html", "search.html", "about.html"):
        assert (wiki / name).exists()
    assert (wiki / "data" / "search-index.js").exists()
    assert (wiki / "assets" / "nav.js").exists()
    assert len(list((wiki / "sections").glob("*.html"))) == 5


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


def test_search_index_has_terms(wiki: Path):
    js = (wiki / "data" / "search-index.js").read_text()
    assert js.startswith("window.DSW_SEARCH = ")
    assert "timer" in js.lower()
