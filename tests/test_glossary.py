"""Unit tests for the acronym glossary."""
from __future__ import annotations

from datasheet_wiki.glossary import annotate, present_terms


def test_present_terms_sorted_unique():
    terms = present_terms("The ADC and PWM, plus more PWM and an I2C bus.")
    keys = [t[0] for t in terms]
    assert keys == ["ADC", "I2C", "PWM"]
    assert dict(terms)["PWM"] == "Pulse-Width Modulation"


def test_present_terms_ignores_non_glossary_words():
    assert present_terms("the quick brown fox") == []


def test_annotate_wraps_first_occurrence_only():
    out = annotate("PWM drives PWM")
    assert out.count("<abbr") == 1
    assert '<abbr class="gloss" title="Pulse-Width Modulation">PWM</abbr> drives PWM' == out


def test_annotate_escapes_html():
    out = annotate("a < b & ADC")
    assert "&lt;" in out and "&amp;" in out
    assert '<abbr class="gloss" title="Analog-to-Digital Converter">ADC</abbr>' in out


def test_annotate_handles_i2c_superscript():
    # "I²C" should resolve to the I2C entry
    out = annotate("the I²C bus")
    assert 'title="Inter-Integrated Circuit (two-wire serial bus)"' in out
