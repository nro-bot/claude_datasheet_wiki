"""Sanity checks for the shared fixtures in conftest.py.

These confirm the fixtures themselves are wired correctly, independently of the
end-to-end assertions in test_pipeline.py.
"""
from __future__ import annotations

from pathlib import Path

from datasheet_wiki.config import Config
from datasheet_wiki.pdf.extract import PdfDocument


def test_sample_pdf_fixture(sample_pdf: Path):
    assert sample_pdf.suffix == ".pdf"
    assert sample_pdf.exists() and sample_pdf.stat().st_size > 0
    doc = PdfDocument(sample_pdf)
    try:
        assert doc.page_count == 5
        assert len(doc.outline()) == 5  # the synthetic datasheet has a real TOC
    finally:
        doc.close()


def test_small_config_fixture(small_config: Config):
    assert small_config.compute == "small"
    assert small_config.backend == "none"  # no LLM in the small tier
    assert small_config.render_images is True


def test_wiki_fixture_is_built(wiki: Path):
    assert wiki.is_dir()
    assert (wiki / "index.html").exists()
    assert list((wiki / "sections").glob("*.html"))
