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

    # 2c. decide on LLM page formatting and (while the PDF is still open) extract
    # the per-page items, cropping every figure/table to an image.
    backend = get_backend(cfg.backend, model=cfg.model, ollama_host=cfg.ollama_host)
    backend_avail = backend.available() if cfg.backend != "none" else False
    do_format = bool(
        cfg.llm_format and cfg.backend != "none"
        and backend.supports_formatting() and backend_avail
    )
    if cfg.llm_format and not do_format:
        if cfg.backend == "none":
            log("NOTE: --llm-format needs an LLM backend (use --compute medium/large "
                "or --backend); skipping page formatting.")
        elif not backend_avail:
            log(f"WARNING: --llm-format requested but backend '{cfg.backend}' is "
                "unavailable; skipping LLM page formatting.")
    page_items = (
        doc.layout_page_items(cfg.out_dir / "figures", limit=limit, resume=cfg.resume)
        if do_format else None
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
    if cfg.backend != "none":
        if backend_avail:
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

    # 4b. LLM-formatted pages (reflowed HTML; figures/tables as images). Cached
    # per page so an interrupted run resumes without re-calling the model.
    formats: Dict[int, "FormattedPage"] = {}
    if do_format and page_items is not None:
        from .enrich.format import PageFormatter
        from .utils import parse_page_spec

        # Optional preview: only LLM-format the requested pages so you can see the
        # result without processing the whole datasheet. A section renders the
        # formatted view for whichever of its pages were formatted, and sections
        # with none keep the heuristic reflow — so a preview stays cheap.
        if cfg.llm_format_pages:
            selected = parse_page_spec(cfg.llm_format_pages, len(page_items))
            todo = [p for p in sorted(selected) if page_items[p]]
            log(f"LLM page-format preview: {len(todo)} page(s) "
                f"({[p + 1 for p in todo]}).")
        else:
            todo = [p for p, items in enumerate(page_items) if items]

        fmt_cache = ensure_dir(cfg.cache_dir / "format")
        pf = PageFormatter(backend)
        prog = Progress(len(todo), "llm format", enabled=cfg.progress)
        for p in todo:
            items = page_items[p]
            src = pf.source_text(items)
            raw = ""
            if src.strip():
                key = sha1_text(f"{cfg.backend}|{cfg.model or ''}|fmt|{src}")
                cpath = fmt_cache / f"{key}.json"
                cached = read_json(cpath) if cfg.resume else None
                if cached is not None:
                    raw = cached.get("html", "")
                else:
                    raw = backend.format_html(src) or ""
                    write_json(cpath, {"html": raw})
            formats[p] = pf.format(p, items, raw)
            prog.update()
        prog.close()
        n_llm = sum(1 for f in formats.values() if f.backend != "none")
        log(f"LLM-formatted {n_llm}/{len(formats)} pages.")

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

    # authoritative registers from a CMSIS-SVD, if supplied
    svd_reg_groups = None
    if cfg.svd_path:
        from .svd import parse_svd

        try:
            svd_reg_groups = parse_svd(cfg.svd_path)
            log(f"SVD: {sum(len(g['registers']) for g in svd_reg_groups)} registers "
                f"across {len(svd_reg_groups)} peripherals from {cfg.svd_path.name}")
        except Exception as exc:
            log(f"WARNING: could not parse SVD {cfg.svd_path} ({exc}); using PDF heuristics.")

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
        "llm_format": do_format,
        "svd_name": cfg.svd_path.name if cfg.svd_path else None,
    }
    SiteBuilder(cfg.out_dir, meta).build(
        sections, enrichments, pages_manifest=pages_manifest,
        svd_reg_groups=svd_reg_groups, formats=formats, progress=cfg.progress,
    )

    dt = time.time() - t0
    log(f"Done in {dt:.0f}s → {cfg.out_dir}/index.html")
    return cfg.out_dir / "index.html"
