"""Unit tests for the text reflow / structuring logic (no PDF needed)."""
from __future__ import annotations

from datasheet_wiki.pdf.blocks import BOLD_END, BOLD_START, Block
from datasheet_wiki.pdf.layout import (
    classify_block,
    join_lines,
    looks_like_table_page,
    merge_short_blocks,
)
from datasheet_wiki.site.render import render_blocks


def test_reflow_collapses_table_column():
    # "Bit / 7 / 6 / 5 / 4" (one block, many lines) -> a single line
    assert join_lines(["Bit", "7", "6", "5", "4"]) == "Bit 7 6 5 4"


def test_reflow_dehyphenates():
    assert join_lines(["micro-", "controller runs"]) == "microcontroller runs"


def test_reflow_joins_paragraph_lines():
    assert join_lines(["The 8-bit timer", "supports PWM."]) == "The 8-bit timer supports PWM."


def test_merge_short_blocks_combines_scattered_cells():
    # scattered single-cell blocks (as a real table column extracts) become a
    # collapsed code block: one compact line shown, raw cells when expanded
    cells = [Block(kind="para", text=t) for t in ("Bit", "7", "6", "5", "4")]
    merged = merge_short_blocks(cells)
    assert len(merged) == 1
    assert merged[0].kind == "codefold"
    assert merged[0].summary == "Bit 7 6 5 4"
    assert merged[0].text == "Bit\n7\n6\n5\n4"


def test_merge_keeps_prose():
    blocks = [Block(kind="para", text="This is a full sentence of prose that should not merge.")]
    assert merge_short_blocks(blocks) == blocks


def test_classify_heading_by_size_and_bold():
    h = classify_block(f"{BOLD_START}Timer/Counter{BOLD_END}", max_size=18.0, body_size=11.0, bold_frac=1.0)
    assert h.kind == "heading"
    assert h.level == 2
    # bold but body-sized -> still a heading, just a smaller level
    h2 = classify_block(f"{BOLD_START}Bit Description{BOLD_END}", max_size=11.0, body_size=11.0, bold_frac=1.0)
    assert h2.kind == "heading" and h2.level == 4


def test_classify_paragraph():
    p = classify_block("The device supports three timers and a watchdog.", 11.0, 11.0, 0.0)
    assert p.kind == "para"


def test_classify_bullet_list():
    b = classify_block("• first item • second item • third", 11.0, 11.0, 0.0)
    assert b.kind == "list"
    assert b.items == ["first item", "second item", "third"]


def test_table_page_detection():
    table = ["Bit", "7", "6", "5", "4", "3", "2", "1", "0", "R/W", "R", "W"]
    assert looks_like_table_page(table) is True
    prose = ["The 8-bit Timer/Counter0 supports pulse width modulation and is clocked from the prescaler."]
    assert looks_like_table_page(prose) is False


def test_render_blocks_html():
    blocks = [
        Block(kind="heading", text="Registers", level=2),
        Block(kind="para", text=f"Set the {BOLD_START}CS00{BOLD_END} bit."),
        Block(kind="list", items=["one", "two"]),
        Block(kind="figure", image_rel="figures/fig-p0004-0.png", page=3),
        Block(kind="table_note", page=4, image_rel="images/page-0005.png"),
    ]
    html = render_blocks(blocks, {}, {}, root="../")
    assert "<h4" in html and "Registers" in html
    assert "<strong>CS00</strong>" in html
    assert "<ul" in html and "<li>one</li>" in html
    assert 'src="../figures/fig-p0004-0.png"' in html
    assert "Detected table" in html and "image of page 5" in html


def test_render_codefold_collapsed_one_line():
    blocks = [Block(kind="codefold", summary="Bit 7 6 5 4", text="Bit\n7\n6\n5\n4", page=1)]
    html = render_blocks(blocks, {}, {}, root="")
    # a <details> (collapsed by default — no `open`) with the one-line peek in the
    # summary and the full text in a <pre>
    assert "<details" in html and "codefold" in html and " open" not in html
    assert "<summary>" in html and "Bit 7 6 5 4" in html
    assert "<pre><code>Bit\n7\n6\n5\n4</code></pre>" in html


def test_render_codefold_skips_empty():
    assert render_blocks([Block(kind="codefold", text="  ")], {}, {}, root="") == ""
