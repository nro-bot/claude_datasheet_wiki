"""Parse the JSON an LLM backend returns and merge it onto the heuristic base.

LLMs occasionally wrap JSON in prose or code fences, so we extract the first
balanced JSON object before parsing. If anything is malformed we keep the
deterministic heuristic baseline rather than failing the whole build.
"""
from __future__ import annotations

import json
from typing import Optional

from ..utils import log
from .base import CodeExample, Enrichment, Register, RegisterField


def _extract_json_object(raw: str) -> Optional[str]:
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return raw[start : i + 1]
    return None


def merge_llm_json(raw: str, base: Enrichment, backend: str) -> Enrichment:
    blob = _extract_json_object(raw or "")
    if not blob:
        return base
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        log("LLM returned invalid JSON; keeping heuristic baseline for section.")
        return base

    summary = (data.get("summary") or "").strip() or base.summary
    keywords = data.get("keywords") or base.keywords
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    registers = []
    for r in data.get("registers") or []:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        registers.append(
            Register(
                name=str(r.get("name", "")).strip(),
                description=str(r.get("description", "")).strip(),
                address=str(r.get("address", "")).strip(),
                fields=[
                    RegisterField(
                        bits=str(f.get("bits", "")).strip(),
                        name=str(f.get("name", "")).strip(),
                        access=str(f.get("access", "")).strip(),
                        description=str(f.get("description", "")).strip(),
                    )
                    for f in (r.get("fields") or [])
                    if isinstance(f, dict)
                ],
            )
        )
    # If the model found nothing structured, keep heuristic registers.
    if not registers:
        registers = base.registers

    code = []
    for c in data.get("code_examples") or []:
        if isinstance(c, dict) and (c.get("code") or "").strip():
            code.append(
                CodeExample(
                    title=str(c.get("title", "Example")).strip() or "Example",
                    language=str(c.get("language", "c")).strip() or "c",
                    code=str(c["code"]).rstrip(),
                )
            )
    if not code:
        code = base.code_examples

    return Enrichment(
        summary=summary,
        keywords=list(keywords)[:16],
        registers=registers,
        code_examples=code,
        backend=backend,
    )
