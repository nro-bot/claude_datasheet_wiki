"""Shared pytest fixtures for the datasheet-wiki test suite.

These build a synthetic datasheet once per session and run the small (no-LLM)
pipeline over it, so every test module can depend on a ready-made wiki without
re-rendering. Nothing here touches the network or any copyrighted PDF.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from datasheet_wiki.config import Config
from datasheet_wiki.pipeline import run
from tests.make_sample_pdf import make_sample


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Path to a generated synthetic 'datasheet' PDF (built once per session)."""
    pdf = make_sample(tmp_path_factory.mktemp("pdf") / "sample-datasheet.pdf")
    assert pdf.exists() and pdf.stat().st_size > 0
    return pdf


@pytest.fixture(scope="session")
def small_config(sample_pdf: Path, tmp_path_factory: pytest.TempPathFactory) -> Config:
    """A small-tier (heuristics-only) build config pointed at the sample PDF."""
    out = tmp_path_factory.mktemp("wiki")
    return Config.from_tier(sample_pdf, out, "small", progress=False)


@pytest.fixture(scope="session")
def wiki(small_config: Config) -> Path:
    """A fully built small-tier wiki directory, reused across the whole session."""
    run(small_config)
    return small_config.out_dir
