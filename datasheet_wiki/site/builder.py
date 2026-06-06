"""Render the static site with Jinja2."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..enrich.base import Enrichment
from ..glossary import annotate as gloss_annotate, present_terms
from ..pdf.structure import Section
from ..utils import Progress, ensure_dir, slugify
from .render import (
    build_number_index,
    build_page_index,
    render_blocks,
    render_body,
    render_formatted_page,
)

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"


class SiteBuilder:
    def __init__(self, out_dir: Path, meta: dict):
        self.out = ensure_dir(Path(out_dir))
        self.meta = meta
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # -- helpers ------------------------------------------------------------
    def _breadcrumbs(self, sec: Section, by_id: Dict[str, Section]) -> List[dict]:
        chain: List[Section] = []
        cur: Optional[Section] = sec
        while cur is not None:
            chain.append(cur)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        chain.reverse()
        return [{"title": s.title, "url": s.url} for s in chain]

    def _nav_tree(self, sections: List[Section], by_id: Dict[str, Section]) -> List[dict]:
        nodes = {s.id: {"id": s.id, "title": s.short_title, "url": s.url, "number": s.number, "children": []}
                 for s in sections}
        roots: List[dict] = []
        for s in sections:
            if s.parent_id and s.parent_id in nodes:
                nodes[s.parent_id]["children"].append(nodes[s.id])
            else:
                roots.append(nodes[s.id])
        return roots

    def copy_static(self) -> None:
        dest = ensure_dir(self.out / "assets")
        for f in STATIC.glob("*"):
            if f.is_file():
                shutil.copy2(f, dest / f.name)

    # -- main build ---------------------------------------------------------
    def build(
        self,
        sections: List[Section],
        enrichments: Dict[str, Enrichment],
        pages_manifest: Optional[List[dict]] = None,
        svd_reg_groups: Optional[List[dict]] = None,
        formats: Optional[Dict[int, object]] = None,
        progress: bool = True,
    ) -> None:
        by_id = {s.id: s for s in sections}
        number_index = build_number_index(sections)
        page_index = build_page_index(sections)
        nav = self._nav_tree(sections, by_id)

        self.copy_static()
        # Clear stale section pages from a previous build (ids can change between
        # runs); images and caches are preserved for resumability.
        sections_dir = self.out / "sections"
        if sections_dir.exists():
            for old in sections_dir.glob("*.html"):
                old.unlink()
        ensure_dir(sections_dir)

        wiki_id = slugify(self.meta.get("source_name") or self.meta.get("title") or "datasheet")
        # page manifest as a JS global (works over file://)
        ensure_dir(self.out / "assets")
        (self.out / "assets" / "pages.js").write_text(
            "window.DSW_ID=" + json.dumps(wiki_id) + ";\n"
            "window.DSW_PAGES=" + json.dumps(pages_manifest or [], ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )

        # PWA: web manifest + a service worker (must sit at the site root so its
        # scope covers every page) for installable, fully-offline use.
        title = self.meta.get("title") or "Datasheet"
        (self.out / "manifest.webmanifest").write_text(json.dumps({
            "name": title, "short_name": title[:24], "start_url": "./index.html",
            "display": "standalone", "background_color": "#0f1115", "theme_color": "#0f1115",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        # Stamp a per-build id into the service-worker cache name so a rebuild
        # invalidates the previously-cached assets (otherwise the cache-first SW
        # would keep serving a stale CSS/JS after you regenerate the wiki).
        sw_src = (STATIC / "sw.js").read_text(encoding="utf-8")
        build_id = f"{wiki_id}-{uuid.uuid4().hex[:12]}"
        (self.out / "sw.js").write_text(sw_src.replace("__DSW_BUILD__", build_id), encoding="utf-8")
        (self.out / "assets" / "sw.js").unlink(missing_ok=True)  # only the root copy is used
        # quick-jump palette index (sections + registers + key pages)
        palette = []
        for s in sections:
            label = (f"{s.number} " if s.number else "") + s.short_title
            palette.append({"t": label, "u": s.url, "k": "section"})
        for sec in sections:
            for r in (enrichments.get(sec.id) or Enrichment()).registers:
                palette.append({"t": r.name, "u": f"{sec.url}#registers", "k": "register", "s": sec.short_title})
        for label, url in [("Register map", "registers.html"), ("Code examples", "code.html"),
                           ("Reference builder", "reference.html"), ("Personal Reference", "starred.html"),
                           ("Search", "search.html"), ("How it's generated", "how.html")]:
            palette.append({"t": label, "u": url, "k": "page"})
        sec_map = {s.id: {"t": (f"{s.number} " if s.number else "") + s.short_title, "u": s.url} for s in sections}
        (self.out / "assets" / "palette-data.js").write_text(
            "window.DSW_PALETTE=" + json.dumps(palette, ensure_ascii=False, separators=(",", ":")) + ";\n"
            "window.DSW_SECTIONS=" + json.dumps(sec_map, ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )

        common = {
            "meta": self.meta,
            "nav": nav,
            "generated": date.today().isoformat(),
            "section_count": len(sections),
            "wiki_id": wiki_id,
        }

        # register map source: authoritative SVD (if supplied) or PDF heuristics
        if svd_reg_groups:
            reg_groups = [
                {"id": slugify(g["title"]) or f"periph-{i}", "title": g["title"],
                 "number": "", "url": "", "registers": g["registers"]}
                for i, g in enumerate(svd_reg_groups)
            ]
            register_source = "svd"
        else:
            reg_groups = [
                {"id": sec.id, "title": sec.short_title, "number": sec.number,
                 "url": sec.url, "registers": (enrichments.get(sec.id) or Enrichment()).registers}
                for sec in sections if (enrichments.get(sec.id) or Enrichment()).registers
            ]
            register_source = "heuristic"
        register_count = sum(len(g["registers"]) for g in reg_groups)

        # index page
        total_code = sum(len(e.code_examples) for e in enrichments.values())
        top_sections = [
            {"title": s.short_title, "url": s.url, "number": s.number, "page": s.page_label}
            for s in sections
            if s.level == 1
        ]
        self._write(
            "index.html",
            self.env.get_template("index.html").render(
                root="", page="home", current_url="",
                top_sections=top_sections,
                stats={"sections": len(sections), "registers": register_count,
                       "code": total_code, "pages": self.meta.get("page_count", 0)},
                **common,
            ),
        )
        self._write("search.html", self.env.get_template("search.html").render(root="", page="search", current_url="", **common))

        # glossary of the embedded acronyms that appear in this datasheet
        glossary_terms = present_terms(" ".join(s.text for s in sections))
        self._write(
            "glossary.html",
            self.env.get_template("glossary.html").render(
                root="", page="glossary", current_url="", glossary=glossary_terms, **common,
            ),
        )

        # code-examples table of contents
        code_groups = []
        for sec in sections:
            ex = (enrichments.get(sec.id) or Enrichment()).code_examples
            if ex:
                code_groups.append({"id": sec.id, "title": sec.title, "url": sec.url, "examples": ex})
        self._write(
            "code.html",
            self.env.get_template("code.html").render(
                root="", page="code", current_url="",
                code_groups=code_groups, code_count=total_code, **common,
            ),
        )
        # register map index + generated C header / SVD
        from ..codegen import build_c_header, build_svd

        device = (self.meta.get("title") or "device").split()[0]
        c_header = build_c_header(reg_groups, device, self.meta.get("source_name", "")) if reg_groups else ""
        svd = build_svd(reg_groups, device, self.meta.get("source_name", "")) if reg_groups else None
        if c_header:
            self._write("device.h", c_header)
        if svd:
            self._write("device.svd", svd)
        self._write(
            "registers.html",
            self.env.get_template("registers.html").render(
                root="", page="registers", current_url="",
                reg_groups=reg_groups, register_count=register_count,
                register_source=register_source,
                c_header=c_header, has_svd=bool(svd), **common,
            ),
        )

        # reference builder + personal (starred) reference — both client-side
        self._write("reference.html", self.env.get_template("reference.html").render(root="", page="reference", current_url="", **common))
        self._write("starred.html", self.env.get_template("starred.html").render(root="", page="starred", current_url="", **common))

        self._write("notes.html", self.env.get_template("notes.html").render(root="", page="notes", current_url="", **common))
        self._write("how.html", self.env.get_template("how.html").render(root="", page="how", current_url="", **common))
        self._write("about.html", self.env.get_template("about.html").render(root="", page="about", current_url="", **common))

        # section pages
        tmpl = self.env.get_template("section.html")
        prog = Progress(len(sections), "render html", enabled=progress)
        for i, sec in enumerate(sections):
            enr = enrichments.get(sec.id) or Enrichment()
            formatted = render_blocks(sec.blocks, number_index, page_index, root="../")
            # LLM-formatted view (when available): reflowed HTML per page in this
            # section, with figures/tables embedded as images.
            sec_pages = [formats[p] for p in range(sec.start_page, sec.end_page + 1)
                         if formats and p in formats] if formats else []
            multi = len(sec_pages) > 1
            llm_formatted = "\n".join(
                render_formatted_page(fp, number_index, page_index, root="../", show_page_label=multi)
                for fp in sec_pages
            )
            format_backend = next((fp.backend for fp in sec_pages if fp.backend != "none"),
                                  ("none" if sec_pages else ""))
            body = render_body(sec.text, number_index, page_index, root="../")
            prev_s = sections[i - 1] if i > 0 else None
            next_s = sections[i + 1] if i < len(sections) - 1 else None
            html_out = tmpl.render(
                root="../",
                page="section",
                current_url=sec.url,
                section=sec,
                breadcrumbs=self._breadcrumbs(sec, by_id),
                body=body,
                formatted=formatted,
                llm_formatted=llm_formatted,
                format_backend=format_backend,
                summary_html=gloss_annotate(enr.summary) if enr.summary else "",
                enrichment=enr,
                images=sec.page_images,
                prev=({"title": prev_s.title, "url": prev_s.url} if prev_s else None),
                next=({"title": next_s.title, "url": next_s.url} if next_s else None),
                **common,
            )
            self._write(f"sections/{sec.id}.html", html_out)
            prog.update()
        prog.close()

    def _write(self, rel: str, content: str) -> None:
        path = self.out / rel
        ensure_dir(path.parent)
        path.write_text(content, encoding="utf-8")
