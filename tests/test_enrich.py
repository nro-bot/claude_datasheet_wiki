"""Tests for enrichment provenance tagging."""
from __future__ import annotations

from datasheet_wiki.enrich.base import get_backend


def test_heuristic_backend_tagged_none():
    enr = get_backend("none").enrich("Timers", "The 8-bit timer supports PWM.")
    assert enr.backend == "none"


def test_llm_fallback_tagged_none_not_backend_name():
    # an Ollama backend pointed at a dead host must fall back to heuristics and
    # be tagged 'none' (heuristic), NOT 'ollama' — provenance must not overclaim.
    be = get_backend("ollama", model="llama3.1", ollama_host="http://127.0.0.1:1")
    enr = be.enrich("Timers", "The 8-bit timer supports PWM.")
    assert enr.backend == "none"
    assert enr.summary  # heuristic summary still produced
