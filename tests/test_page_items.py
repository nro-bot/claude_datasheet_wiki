"""Tests for the per-page item extraction (LLM-formatted view source)."""
from __future__ import annotations

import fitz

from datasheet_wiki.pdf.page_items import _cluster_table_rects, extract_page_items


def test_cluster_merges_side_by_side_columns():
    # two columns of a table at the same height, side by side -> one region
    rects = [((50, 100, 90, 200), "col1"), ((100, 100, 140, 200), "col2")]
    merged = _cluster_table_rects(rects)
    assert len(merged) == 1
    (x0, y0, x1, y1), ocr = merged[0]
    assert (x0, y0, x1, y1) == (50, 100, 140, 200)
    assert "col1" in ocr and "col2" in ocr


def test_cluster_merges_stacked_rows():
    rects = [((50, 100, 140, 120), "r1"), ((50, 124, 140, 144), "r2")]
    merged = _cluster_table_rects(rects)
    assert len(merged) == 1
    assert merged[0][0] == (50, 100, 140, 144)


def test_cluster_keeps_far_apart_blocks_separate():
    rects = [((50, 100, 90, 120), "a"), ((50, 600, 90, 620), "b")]
    merged = _cluster_table_rects(rects)
    assert len(merged) == 2


def test_extract_items_returns_prose_text(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(50, 50, 545, 200),
        "The FOO85 is a low-power 8-bit microcontroller with three timers.",
        fontsize=11, fontname="helv",
    )
    items = extract_page_items(page, 0, figures_dir=tmp_path / "figures")
    doc.close()
    assert items, "expected at least one item"
    assert any(it.kind == "text" and "microcontroller" in it.text for it in items)
    # pure prose -> no asset images cropped
    assert all(it.kind == "text" for it in items)


def test_extract_items_crops_a_table_region(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    # two short-token columns side by side -> detected as a table, cropped to img
    page.insert_textbox(fitz.Rect(70, 100, 120, 200), "0x00\n0x01\n0x02\n0x03",
                        fontsize=11, fontname="helv")
    page.insert_textbox(fitz.Rect(130, 100, 180, 200), "R/W\nR/W\nR\nW",
                        fontsize=11, fontname="helv")
    figs = tmp_path / "figures"
    items = extract_page_items(page, 3, figures_dir=figs)
    doc.close()
    tables = [it for it in items if it.kind == "table"]
    assert tables, "expected a cropped table item"
    assert tables[0].image_rel.startswith("figures/tbl-p0004-")
    assert (tmp_path / tables[0].image_rel).exists()
