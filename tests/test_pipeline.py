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
    # compact in-page ToC under the summary
    assert 'class="section-toc"' in html
    for label in ("Source Pages", "Formatted Text", "Raw Text"):
        assert label in html
    for anchor in ('id="source"', 'id="formatted"', 'id="rawtext"'):
        assert anchor in html
    # per-page provenance blurb + page-label lines removed
    assert "how is this generated?" not in html
    assert "Everything on this page" not in html
    assert "Datasheet p.4" not in html          # header page label gone
    assert 'Source pages <a class="permalink"' in html  # no page label by the heading
    # permalinks to deep-link each section
    assert html.count('class="permalink"') >= 4
    for anchor in ('id="summary"', 'id="registers"'):
        assert anchor in html


def test_section_number_not_duplicated(wiki: Path):
    html = (wiki / "sections" / "3-timer-counter.html").read_text()
    # heading shows the number once: "3" (secnum) + "Timer/Counter", not "3 3 …"
    assert '<span class="secnum">3</span> Timer/Counter</h1>' in html
    assert "3 3 Timer" not in html
    # ...and the same in the sidebar nav / overview TOC
    index = (wiki / "index.html").read_text()
    assert '<span class="secnum">2</span> Pin Configuration' in index
    assert "2 2 Pin Configuration" not in index


def test_page_manifest(wiki: Path):
    js = (wiki / "assets" / "pages.js").read_text()
    assert "window.DSW_PAGES=" in js and "window.DSW_ID=" in js
    assert "page-0001.png" in js  # page image referenced
    assert '"n":1' in js


def test_provenance_badges(wiki: Path):
    html = (wiki / "sections" / "3-timer-counter.html").read_text()
    # small tier -> heuristic badge on summary, registers and code headings
    assert html.count('class="prov prov-heuristic"') == 3
    assert "prov-llm" not in html


def test_glossary_page_and_summary_tooltips(wiki: Path):
    gloss = (wiki / "glossary.html").read_text()
    assert "Glossary" in gloss
    assert "<dt id=\"g-PWM\">PWM</dt>" in gloss  # PWM appears in the sample
    # acronyms are tooltipped in section summaries
    timer = (wiki / "sections" / "3-timer-counter.html").read_text()
    assert '<abbr class="gloss" title="Pulse-Width Modulation">PWM</abbr>' in timer
    assert "glossary.html" in (wiki / "index.html").read_text()  # nav link


def test_personal_notes(wiki: Path):
    assert (wiki / "assets" / "notes.js").exists()
    sec = (wiki / "sections" / "3-timer-counter.html").read_text()
    assert 'id="note" data-section="3-timer-counter"' in sec
    notes = (wiki / "notes.html").read_text()
    assert 'id="notes-list"' in notes
    assert "DSW_SECTIONS=" in (wiki / "assets" / "palette-data.js").read_text()
    assert "notes.html" in (wiki / "index.html").read_text()


def test_command_palette(wiki: Path):
    data = (wiki / "assets" / "palette-data.js").read_text()
    assert data.startswith("window.DSW_PALETTE=")
    assert '"k":"section"' in data and '"k":"register"' in data
    assert "DDRB" in data  # a register is jump-able
    index = (wiki / "index.html").read_text()
    assert "assets/palette.js" in index and 'id="cmdk"' in index


def test_register_export_files(wiki: Path):
    assert (wiki / "device.h").exists()
    h = (wiki / "device.h").read_text()
    assert "#define DDRB_DDB7_Pos" in h
    reg = (wiki / "registers.html").read_text()
    assert 'href="device.h" download' in reg


def test_register_map_page(wiki: Path):
    reg = (wiki / "registers.html").read_text()
    assert "Register map" in reg
    assert "DDRB" in reg and 'table class="bits"' in reg
    assert "registers.html" in (wiki / "index.html").read_text()  # nav link


def test_reference_and_starred_pages(wiki: Path):
    for name in ("reference.html", "starred.html"):
        html = (wiki / name).read_text()
        assert "assets/pages.js" in html and "assets/gallery.js" in html
        assert 'id="gallery"' in html
    ref = (wiki / "reference.html").read_text()
    assert 'id="pagespec"' in ref and 'id="page-search"' in ref
    # bookmark/calculator engines load everywhere
    assert (wiki / "assets" / "bookmarks.js").exists()
    assert (wiki / "assets" / "calc.js").exists()
    assert (wiki / "assets" / "gallery.js").exists()


def test_thumbnails_carry_page_number(wiki: Path):
    sec = (wiki / "sections" / "2-pin-configuration.html").read_text()
    assert 'class="thumb" data-page="2"' in sec  # star toggle target


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
