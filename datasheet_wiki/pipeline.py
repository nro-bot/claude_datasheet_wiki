"""End-to-end build pipeline: PDF -> static datasheet wiki.

Stages:
  1. open PDF + extract outline/text/links
  2. render every page to an image (resumable)
  3. build the section tree
  4. enrich each section (cached to disk, so multi-hour runs resume cleanly)
  5. build the full-text search index (+ optional local semantic vectors)
  6. render the static site

Designed so the expensive stages (image render, enrichment) are incremental:
re-running with the same output dir skips work already done.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

from .config import Config
from .enrich.base import Enrichment, get_backend
from .pdf.extract import PdfDocument
from .pdf.structure import build_sections
from .search.index import build_search_index, write_search_index
from .site.builder import SiteBuilder
from .utils import Progress, ensure_dir, log, read_json, sha1_text, write_json


def _enrich_cache_key(cfg: Config, title: str, text: str) -> str:
    sig = f"{cfg.backend}|{cfg.model or ''}|{title}|{text}"
    return sha1_text(sig)


def run(cfg: Config) -> Path:
    t0 = time.time()
    ensure_dir(cfg.out_dir)
    ensure_dir(cfg.cache_dir)

    log(f"Opening {cfg.pdf_path} (compute={cfg.compute}, backend={cfg.backend})")
    doc = PdfDocument(cfg.pdf_path)
    page_count = doc.page_count
    limit = cfg.max_pages if cfg.max_pages else 0
    effective_pages = min(page_count, limit) if limit else page_count
    title = cfg.title or doc.title
    log(f"{page_count} pages; processing {effective_pages}; title: {title!r}")

    # 1+2. text + images
    pages = doc.pages_text(limit=limit)
    images = []
    if cfg.render_images:
        images = doc.render_pages(
            cfg.out_dir / "images", dpi=cfg.dpi, fmt=cfg.image_format, limit=limit, resume=cfg.resume
        )
    else:
        images = [None] * effective_pages

    # 2b. structured (reflowed) content + inline figures
    page_blocks = doc.layout_pages(
        cfg.out_dir / "figures", limit=limit, extract_figures=True, resume=cfg.resume
    )

    # 3. structure
    outline = doc.outline()
    log(f"Outline entries: {len(outline)}")
    sections = build_sections(outline, pages, images, max_pages=limit, page_blocks=page_blocks)
    log(f"Built {len(sections)} sections")
    doc.close()

    # link whole-page "table" notes to the rendered page image
    for sec in sections:
        for blk in sec.blocks:
            if blk.kind == "table_note" and blk.page < len(images) and images[blk.page]:
                blk.image_rel = f"images/{images[blk.page]}"

    # 4. enrichment (cached)
    backend = get_backend(cfg.backend, model=cfg.model, ollama_host=cfg.ollama_host)
    if cfg.backend != "none":
        if backend.available():
            log(f"Enrichment backend '{cfg.backend}' is available.")
        else:
            log(f"WARNING: backend '{cfg.backend}' is NOT available; using heuristics where it fails.")
    enrich_cache = ensure_dir(cfg.cache_dir / "enrich")
    enrichments: Dict[str, Enrichment] = {}
    prog = Progress(len(sections), "enrich", enabled=cfg.progress)
    for sec in sections:
        key = _enrich_cache_key(cfg, sec.title, sec.text)
        cpath = enrich_cache / f"{key}.json"
        cached = read_json(cpath) if cfg.resume else None
        if cached is not None:
            enrichments[sec.id] = Enrichment.from_dict(cached)
        else:
            enr = backend.enrich(sec.title, sec.text)
            enrichments[sec.id] = enr
            write_json(cpath, enr.to_dict())
        prog.update()
    prog.close()

    # 5. search index
    log("Building search index...")
    by_id = {s.id: s for s in sections}

    def breadcrumb(s):
        chain, cur = [], s
        while cur is not None:
            chain.append(cur.title)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return " › ".join(reversed(chain))

    breadcrumbs = {s.id: breadcrumb(s) for s in sections}
    summaries = {sid: e.summary for sid, e in enrichments.items()}
    index = build_search_index(sections, breadcrumbs, summaries)
    size = write_search_index(index, cfg.out_dir / "data" / "search-index.js")
    log(f"Search index: {len(sections)} docs, {len(index['index'])} terms ({size // 1024} KB)")

    semantic_ok = False
    if cfg.semantic:
        from .search import embeddings as emb

        n = emb.build_embeddings(
            sections,
            cfg.out_dir / "data" / "vectors.js",
            model_name=cfg.embed_model,
            chunk_chars=cfg.chunk_chars,
            progress=cfg.progress,
        )
        if n:
            semantic_ok = True
            log(f"Semantic index: {n} chunks embedded locally.")

    # page manifest: maps every page -> its image, owning section, and text
    # (used by the reference/bookmark pages and page-level search).
    page_to_sec = {}
    for sec in sections:
        for p in range(sec.start_page, sec.end_page + 1):
            cur = page_to_sec.get(p)
            if cur is None or sec.level > cur.level:
                page_to_sec[p] = sec
    pages_manifest = []
    for p in range(effective_pages):
        sec = page_to_sec.get(p)
        img = images[p] if p < len(images) and images[p] else ""
        pages_manifest.append({
            "n": p + 1,
            "img": f"images/{img}" if img else "",
            "sec": sec.short_title if sec else "",
            "num": sec.number if sec else "",
            "url": sec.url if sec else "",
            "t": (pages[p].text or "")[:2500] if p < len(pages) else "",
        })

    # 6. site
    log("Rendering site...")
    meta = {
        "title": title,
        "source_name": cfg.pdf_path.name,
        "page_count": page_count,
        "compute": cfg.compute,
        "backend": cfg.backend,
        "model": cfg.model,
        "dpi": cfg.dpi,
        "semantic": semantic_ok,
    }
    SiteBuilder(cfg.out_dir, meta).build(
        sections, enrichments, pages_manifest=pages_manifest, progress=cfg.progress
    )

    dt = time.time() - t0
    log(f"Done in {dt:.0f}s → {cfg.out_dir}/index.html")
    return cfg.out_dir / "index.html"
