"""Build a client-side full-text search index.

The index is emitted as a JavaScript file that assigns a global
(`window.DSW_SEARCH = {...}`). Loading it via a <script> tag — rather than
fetch()ing JSON — means search works even when the wiki is opened directly from
disk over file:// (browsers block fetch of local files, but not <script src>).

The format is a compact inverted index; scoring (tf-idf) happens in the browser
(see site/static/search.js).
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Tuple

from ..pdf.structure import Section
from ..utils import ensure_dir
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = set(
    "the a an and or of to in for on with as by is are be this that it its from at "
    "if then else when which who will can may not no".split()
)


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in _STOP]


def _snippet(text: str, limit: int = 160) -> str:
    s = re.sub(r"\s+", " ", text).strip()
    return s[:limit]


def build_search_index(sections: List[Section], breadcrumbs: Dict[str, str], summaries: Dict[str, str]):
    """Return a JSON-serialisable inverted index over the sections."""
    docs = []
    postings: Dict[str, List[Tuple[int, int]]] = {}
    for i, sec in enumerate(sections):
        summary = summaries.get(sec.id, "")
        docs.append(
            {
                "i": i,
                "t": sec.title,
                "u": sec.url,
                "b": breadcrumbs.get(sec.id, ""),
                "p": sec.page_label,
                "s": _snippet(summary or sec.text),
            }
        )
        # term frequencies for this doc; weight the title higher
        tf: Dict[str, int] = {}
        for tok in _tokenize(sec.title) * 3 + _tokenize(summary) * 2 + _tokenize(sec.text):
            tf[tok] = tf.get(tok, 0) + 1
        for term, freq in tf.items():
            postings.setdefault(term, []).append((i, freq))

    index = {term: [[i, f] for i, f in plist] for term, plist in postings.items()}
    return {"docs": docs, "index": index, "n": len(docs)}


def write_search_index(data: dict, out_path: Path) -> int:
    ensure_dir(out_path.parent)
    payload = "window.DSW_SEARCH = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    out_path.write_text(payload, encoding="utf-8")
    return len(payload)
