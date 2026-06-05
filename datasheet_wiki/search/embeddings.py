"""Optional local semantic search via sentence-transformers.

Used by the medium/large tiers when `--semantic` is on. Embeddings are computed
*locally* (no API) with a small sentence-transformers model, so this keeps the
"runs on your own machine" guarantee even for the semantic-search feature.

Emitted as a JS global (`window.DSW_VECTORS`) for the same file:// reason as the
text index. Cosine similarity is computed in the browser.

If sentence-transformers / numpy aren't installed, semantic search is silently
skipped and the build still produces a working full-text wiki.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ..pdf.structure import Section
from ..utils import Progress, chunked, ensure_dir, log


def available() -> bool:
    try:
        import numpy  # noqa: F401
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def _chunks_for(sec: Section, max_chars: int) -> List[str]:
    text = sec.text.strip()
    if not text:
        return []
    out, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) > max_chars and cur:
            out.append(cur.strip())
            cur = ""
        cur += para + "\n"
    if cur.strip():
        out.append(cur.strip())
    return out or [text[:max_chars]]


def build_embeddings(
    sections: List[Section],
    out_path: Path,
    model_name: str = "all-MiniLM-L6-v2",
    chunk_chars: int = 1200,
    progress: bool = True,
) -> Optional[int]:
    if not available():
        log("sentence-transformers/numpy not installed; skipping semantic search.")
        return None
    import numpy as np
    from sentence_transformers import SentenceTransformer

    log(f"Loading embedding model '{model_name}' (first run downloads it)...")
    model = SentenceTransformer(model_name)

    chunk_texts: List[str] = []
    chunk_meta: List[dict] = []  # {sec index, snippet}
    for si, sec in enumerate(sections):
        for ch in _chunks_for(sec, chunk_chars):
            chunk_texts.append(ch)
            chunk_meta.append({"s": si, "x": ch[:160].replace("\n", " ")})

    if not chunk_texts:
        return None

    vectors: List[List[float]] = []
    prog = Progress(len(chunk_texts), "embed chunks", enabled=progress)
    for batch in chunked(chunk_texts, 64):
        emb = model.encode(batch, normalize_embeddings=True)
        vectors.extend(np.asarray(emb, dtype="float32").round(5).tolist())
        prog.update(len(batch))
    prog.close()

    docs = [{"i": i, "t": s.title, "u": s.url, "p": s.page_label} for i, s in enumerate(sections)]
    payload = {
        "model": model_name,
        "dim": len(vectors[0]),
        "docs": docs,
        "chunks": chunk_meta,
        "vectors": vectors,
    }
    ensure_dir(out_path.parent)
    js = "window.DSW_VECTORS = " + json.dumps(payload, separators=(",", ":")) + ";"
    out_path.write_text(js, encoding="utf-8")
    return len(chunk_texts)
