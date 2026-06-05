"""No-LLM enrichment: summaries, keywords, registers and code, by heuristics.

This is the engine of the "small" tier and the baseline for every other tier.
Everything here is deterministic, fast, and runs offline on any machine.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List

from .base import Backend, CodeExample, Enrichment, Register, RegisterField

# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------
_STOP = set(
    """a an the and or of to in for on with as by is are be this that these those
    it its from at if then else when which who whom whose will shall can may
    not no all any each per such into out over under up down off above below
    bit bits register value values data set reset read write address mode
    figure table section chapter page note see also etc using used use one two
    three four five high low pin pins""".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")


def keywords(text: str, top: int = 12) -> List[str]:
    counts: Counter = Counter()
    for m in _WORD.finditer(text):
        w = m.group(0)
        lw = w.lower()
        if lw in _STOP:
            continue
        # favour ALLCAPS / mixedCase identifiers common in datasheets
        weight = 2 if (w.isupper() or any(c.isupper() for c in w[1:])) else 1
        counts[w] += weight
    return [w for w, _ in counts.most_common(top)]


# ---------------------------------------------------------------------------
# Extractive summary (first substantive sentences)
# ---------------------------------------------------------------------------
_SENT = re.compile(r"(?<=[.!?])\s+")


def summarize(text: str, max_chars: int = 320) -> str:
    # collapse whitespace and drop obvious page furniture
    lines = [ln.strip() for ln in text.splitlines()]
    body = " ".join(ln for ln in lines if len(ln) > 30)
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return ""
    out = ""
    for sent in _SENT.split(body):
        if len(out) + len(sent) > max_chars and out:
            break
        out = (out + " " + sent).strip()
    return out


# ---------------------------------------------------------------------------
# Register detection
# ---------------------------------------------------------------------------
# Headings like:  "GIMSK – General Interrupt Mask Register"
#                 "DDRB - Port B Data Direction Register"
#                 "10.3  TIMSK0 – Timer/Counter Interrupt Mask Register 0"
_REG_HEADING = re.compile(
    r"(?m)^\s*(?:\d+(?:\.\d+)*\s+)?"
    r"(?P<name>[A-Z][A-Z0-9_]{1,15})\s*[–—:-]\s*"
    r"(?P<desc>[A-Z][^\n]{0,80}?Register[A-Za-z0-9 ]*)\s*$"
)
# bit field rows like:  "Bit 7 – GIE: Global Interrupt Enable"
_REG_BIT = re.compile(
    r"(?m)^\s*Bits?\s+(?P<bits>\d+(?:\s*[:\-]\s*\d+)?)\s*[–—:-]\s*"
    r"(?P<name>[A-Za-z0-9_/]+)\s*[:–—-]?\s*(?P<desc>[^\n]{0,80})"
)


def detect_registers(text: str, limit: int = 30) -> List[Register]:
    regs: List[Register] = []
    seen = set()
    for m in _REG_HEADING.finditer(text):
        name = m.group("name")
        if name in seen:
            continue
        seen.add(name)
        desc = " ".join(m.group("desc").split())
        # gather bit fields appearing shortly after the heading
        window = text[m.end() : m.end() + 1500]
        fields = [
            RegisterField(
                bits=b.group("bits").replace(" ", ""),
                name=b.group("name"),
                description=" ".join(b.group("desc").split()),
            )
            for b in _REG_BIT.finditer(window)
        ][:16]
        regs.append(Register(name=name, description=desc, fields=fields))
        if len(regs) >= limit:
            break
    return regs


# ---------------------------------------------------------------------------
# Code-block detection
# ---------------------------------------------------------------------------
_C_HINTS = ("#include", "void ", "int ", "uint", "return", "for (", "while (",
            "if (", "{", "}", ";", "PORT", "DDR", "0x")
_ASM_HINTS = (" ldi ", " out ", " in ", " rjmp ", " sbi ", " cbi ", " mov ", ".org", ".equ")


def _looks_like_code(block: str) -> str:
    """Return a language guess ('c'|'asm'|'') for a candidate block."""
    low = block.lower()
    asm = sum(h in (" " + low + " ") for h in _ASM_HINTS)
    c = sum(h in block for h in _C_HINTS)
    if asm >= 2 and asm >= c:
        return "asm"
    if c >= 3:
        return "c"
    return ""


def detect_code(text: str, limit: int = 6) -> List[CodeExample]:
    examples: List[CodeExample] = []
    # candidate blocks separated by blank lines
    blocks = re.split(r"\n\s*\n", text)
    for blk in blocks:
        lines = blk.splitlines()
        if len(lines) < 2 or len(blk) > 1500:
            continue
        lang = _looks_like_code(blk)
        if not lang:
            continue
        code = "\n".join(ln.rstrip() for ln in lines).strip()
        examples.append(CodeExample(title="Example from datasheet", language=lang, code=code))
        if len(examples) >= limit:
            break
    return examples


# ---------------------------------------------------------------------------
class HeuristicBackend(Backend):
    name = "none"

    def available(self) -> bool:
        return True

    def enrich(self, title: str, text: str) -> Enrichment:
        return baseline(title, text, backend=self.name)


def baseline(title: str, text: str, backend: str = "none") -> Enrichment:
    """The deterministic baseline every backend builds on."""
    return Enrichment(
        summary=summarize(text),
        keywords=keywords(text),
        registers=detect_registers(text),
        code_examples=detect_code(text),
        backend=backend,
    )
