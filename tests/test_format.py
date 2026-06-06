"""Tests for the LLM-formatted page view: marker handling, fallback, rendering."""
from __future__ import annotations

from datasheet_wiki.enrich.format import Asset, FormattedPage, PageFormatter, asset_token
from datasheet_wiki.pdf.page_items import PageItem
from datasheet_wiki.site.render import render_formatted_page
from datasheet_wiki.utils import parse_page_spec


def test_parse_page_spec_count_means_first_n():
    assert parse_page_spec("3", 10) == {0, 1, 2}
    assert parse_page_spec("3", 2) == {0, 1}  # clamps to page count


def test_parse_page_spec_ranges_and_lists_are_1_based():
    assert parse_page_spec("40-42", 100) == {39, 40, 41}
    assert parse_page_spec("1,3,5", 100) == {0, 2, 4}
    assert parse_page_spec("2-3, 7", 100) == {1, 2, 6}


def test_parse_page_spec_ignores_out_of_range_and_junk():
    assert parse_page_spec("5-7", 3) == set()  # all beyond the page count
    assert parse_page_spec("", 10) == set()


class _FakeBackend:
    name = "ollama"

    def __init__(self, html):
        self._html = html

    def supports_formatting(self):
        return True

    def format_html(self, page_text):
        return self._html


def _items():
    return [
        PageItem("text", text="The timer supports PWM.", page=3),
        PageItem("figure", image_rel="figures/fig-p0004-0.png", text="Figure 1 caption OCR", page=3),
        PageItem("table", image_rel="figures/tbl-p0004-0.png", text="Bit\n7\n6\n5", page=3),
    ]


def test_source_text_replaces_assets_with_ordered_markers():
    pf = PageFormatter(_FakeBackend(""))
    src = pf.source_text(_items())
    assert "The timer supports PWM." in src
    assert asset_token(0) in src and asset_token(1) in src
    # the OCR text of the figure/table must NOT leak into the prompt
    assert "Bit" not in src and "caption OCR" not in src


def test_format_uses_llm_html_and_keeps_assets():
    html = f"<h2>Timer</h2><p>The timer supports PWM.</p>{asset_token(0)}{asset_token(1)}"
    pf = PageFormatter(_FakeBackend(html))
    items = _items()
    fp = pf.format(3, items, pf.backend.format_html(pf.source_text(items)))
    assert fp.backend == "ollama"
    assert len(fp.assets) == 2
    assert asset_token(0) in fp.html and asset_token(1) in fp.html


def test_format_appends_missing_asset_markers():
    # model dropped the table marker -> it must be appended so the image isn't lost
    html = f"<p>prose</p>{asset_token(0)}"
    pf = PageFormatter(_FakeBackend(html))
    items = _items()
    fp = pf.format(3, items, pf.backend.format_html(pf.source_text(items)))
    assert asset_token(1) in fp.html


def test_format_falls_back_when_llm_returns_nothing():
    pf = PageFormatter(_FakeBackend(""))
    items = _items()
    fp = pf.format(3, items, "")
    assert fp.backend == "none"  # heuristic assembly
    assert "The timer supports PWM." in fp.html
    assert asset_token(0) in fp.html and asset_token(1) in fp.html


def test_render_substitutes_markers_with_images_and_codefold():
    fp = FormattedPage(
        page=3,
        html=f"<p>The timer supports PWM.</p><p>{asset_token(0)}</p>{asset_token(1)}",
        assets=[
            Asset("figure", "figures/fig-p0004-0.png", "Figure caption", 3),
            Asset("table", "figures/tbl-p0004-0.png", "Bit\n7\n6\n5", 3),
        ],
        backend="ollama",
    )
    out = render_formatted_page(fp, {}, {}, root="../")
    # both assets rendered as embedded images, not as raw markers
    assert asset_token(0) not in out and asset_token(1) not in out
    assert 'src="../figures/fig-p0004-0.png"' in out
    assert 'src="../figures/tbl-p0004-0.png"' in out
    assert "dsasset-figure" in out and "dsasset-table" in out
    # OCR text is tucked into a collapsed codefold, not shown as prose
    assert "<details" in out and "codefold" in out
    # a <p>-wrapped marker became a block-level figure (not nested in a <p>)
    assert "<p><figure" not in out


def test_render_links_cross_references_in_formatted_html():
    fp = FormattedPage(page=0, html="<p>See Section 3 for timers.</p>", assets=[], backend="ollama")
    out = render_formatted_page(fp, {"3": "3-timer-counter"}, {}, root="../")
    assert '<a class="xref" href="../sections/3-timer-counter.html">See Section 3</a>' in out


def test_page_label_added_for_multipage_sections():
    fp = FormattedPage(page=4, html="<p>x</p>", assets=[], backend="ollama")
    out = render_formatted_page(fp, {}, {}, root="../", show_page_label=True)
    assert "fmt-page" in out and "Page 5" in out
