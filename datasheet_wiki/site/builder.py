"""Render the static site with Jinja2."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..enrich.base import Enrichment
from ..pdf.structure import Section
from ..utils import Progress, ensure_dir, log
from .render import build_number_index, build_page_index, render_blocks, render_body

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
        progress: bool = True,
    ) -> None:
        import json

        from ..utils import slugify

        by_id = {s.id: s for s in sections}
        number_index = build_number_index(sections)
        page_index = build_page_index(sections)
        nav = self._nav_tree(sections, by_id)
        breadcrumbs_map = {s.id: " › ".join(b["title"] for b in self._breadcrumbs(s, by_id)) for s in sections}

        self.copy_static()
        # Clear stale section pages from a previous build (ids can change between
        # runs); images and caches are preserved for resumability.
        sections_dir = self.out / "sections"
        if sections_dir.exists():
            for old in sections_dir.glob("*.html"):
                old.unlink()
        ensure_dir(sections_dir)

        wiki_id = slugify(self.meta.get("source_name") or self.meta.get("title") or "datasheet")
        has_pages = bool(pages_manifest)
        # page manifest as a JS global (works over file://)
        ensure_dir(self.out / "assets")
        (self.out / "assets" / "pages.js").write_text(
            "window.DSW_ID=" + json.dumps(wiki_id) + ";\n"
            "window.DSW_PAGES=" + json.dumps(pages_manifest or [], ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )

        common = {
            "meta": self.meta,
            "nav": nav,
            "generated": date.today().isoformat(),
            "section_count": len(sections),
            "wiki_id": wiki_id,
            "has_pages": has_pages,
        }

        # index page
        total_regs = sum(len(e.registers) for e in enrichments.values())
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
                stats={"sections": len(sections), "registers": total_regs,
                       "code": total_code, "pages": self.meta.get("page_count", 0)},
                **common,
            ),
        )
        self._write("search.html", self.env.get_template("search.html").render(root="", page="search", current_url="", **common))

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
        # register map index
        reg_groups = []
        for sec in sections:
            regs = (enrichments.get(sec.id) or Enrichment()).registers
            if regs:
                reg_groups.append({"id": sec.id, "title": sec.short_title, "number": sec.number,
                                   "url": sec.url, "registers": regs})
        self._write(
            "registers.html",
            self.env.get_template("registers.html").render(
                root="", page="registers", current_url="",
                reg_groups=reg_groups, register_count=total_regs, **common,
            ),
        )

        # reference builder + personal (starred) reference — both client-side
        self._write("reference.html", self.env.get_template("reference.html").render(root="", page="reference", current_url="", **common))
        self._write("starred.html", self.env.get_template("starred.html").render(root="", page="starred", current_url="", **common))

        self._write("how.html", self.env.get_template("how.html").render(root="", page="how", current_url="", **common))
        self._write("about.html", self.env.get_template("about.html").render(root="", page="about", current_url="", **common))

        # section pages
        tmpl = self.env.get_template("section.html")
        prog = Progress(len(sections), "render html", enabled=progress)
        for i, sec in enumerate(sections):
            enr = enrichments.get(sec.id) or Enrichment()
            formatted = render_blocks(sec.blocks, number_index, page_index, root="../")
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
