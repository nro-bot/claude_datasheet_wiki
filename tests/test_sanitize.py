"""Tests for the allowlist HTML sanitizer used on LLM-formatted page HTML."""
from __future__ import annotations

from datasheet_wiki.site.sanitize import sanitize_html


def test_keeps_allowed_structural_tags():
    out = sanitize_html("<h3>Title</h3><p>Hello <strong>world</strong></p><ul><li>a</li></ul>")
    assert out == "<h3>Title</h3><p>Hello <strong>world</strong></p><ul><li>a</li></ul>"


def test_drops_scripts_and_their_content():
    out = sanitize_html("<p>ok</p><script>alert('x')</script><style>p{}</style>")
    assert "alert" not in out and "<script" not in out and "<style" not in out
    assert out == "<p>ok</p>"


def test_strips_attributes_and_event_handlers():
    out = sanitize_html('<p onclick="evil()" class="x">hi</p><a href="http://x">link</a>')
    # attributes gone; <a> not in the allowlist so the tag is dropped, text kept
    assert out == "<p>hi</p>link"
    assert "onclick" not in out and "href" not in out


def test_unknown_tags_dropped_but_text_kept():
    out = sanitize_html("<div><span>keep</span> me</div>")
    assert out == "keep me"


def test_remaps_h1_and_bold_italic_synonyms():
    out = sanitize_html("<h1>Big</h1><b>bold</b><i>it</i>")
    assert out == "<h2>Big</h2><strong>bold</strong><em>it</em>"


def test_table_tags_dropped_text_preserved():
    out = sanitize_html("<table><tr><td>A</td><td>B</td></tr></table>")
    assert "<table" not in out and "<td" not in out
    assert "A" in out and "B" in out


def test_asset_markers_survive():
    out = sanitize_html("<p>before</p>[[DSWASSET_0]]<p>after</p>")
    assert "[[DSWASSET_0]]" in out


def test_reescapes_stray_brackets_in_text():
    out = sanitize_html("<pre>a < b && c > d</pre>")
    assert "<pre>" in out and "&lt; b &amp;&amp; c &gt;" in out
