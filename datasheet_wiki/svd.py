"""Parse a CMSIS-SVD file into the register model used by the wiki.

Many vendors ship an authoritative .svd for ARM Cortex-M parts; when one is
supplied (`--svd`), its peripherals/registers/fields drive the Register map and
the C-header export instead of the PDF heuristics.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

from .enrich.base import Register, RegisterField


def _text(el, tag: str, default: str = "") -> str:
    if el is None:
        return default
    v = el.findtext(tag)
    return " ".join(v.split()) if v else default


def _int(s: str, default: int = 0) -> int:
    s = (s or "").strip().lower()
    if not s:
        return default
    try:
        if s.startswith("0x"):
            return int(s, 16)
        if s.startswith("#"):  # SVD binary literal e.g. #1010
            return int(s[1:], 2)
        return int(s, 0)
    except ValueError:
        return default


def _access(a: str) -> str:
    a = (a or "").strip().lower()
    return {"read-write": "R/W", "read-only": "R", "write-only": "W",
            "writeonce": "W", "read-writeonce": "R/W"}.get(a, "")


def _field_bits(f) -> Optional[Tuple[int, int]]:
    """Return (lsb, width) from any of the SVD bit-range encodings."""
    off = f.findtext("bitOffset")
    if off is not None:
        return _int(off), _int(f.findtext("bitWidth") or "1", 1)
    br = f.findtext("bitRange")
    if br:
        m = re.match(r"\[?\s*(\d+)\s*:\s*(\d+)\s*\]?", br)
        if m:
            hi, lo = int(m.group(1)), int(m.group(2))
            return min(hi, lo), abs(hi - lo) + 1
    lsb, msb = f.findtext("lsb"), f.findtext("msb")
    if lsb is not None and msb is not None:
        lo, hi = _int(lsb), _int(msb)
        return min(lo, hi), abs(hi - lo) + 1
    return None


def parse_svd(path: Path) -> List[dict]:
    """Return register groups [{title, registers:[Register]}] — one per peripheral."""
    root = ET.parse(str(path)).getroot()
    groups: List[dict] = []
    for periph in root.iter("peripheral"):
        name = _text(periph, "name")
        base = _int(periph.findtext("baseAddress") or "0")
        regs_el = periph.find("registers")
        if regs_el is None:
            continue
        registers: List[Register] = []
        for reg in regs_el.findall("register"):
            rname = _text(reg, "name")
            addr = base + _int(reg.findtext("addressOffset") or "0")
            fields: List[RegisterField] = []
            fields_el = reg.find("fields")
            if fields_el is not None:
                for f in fields_el.findall("field"):
                    bw = _field_bits(f)
                    if not bw:
                        continue
                    lo, width = bw
                    bits = str(lo) if width == 1 else f"{lo + width - 1}:{lo}"
                    fields.append(RegisterField(
                        bits=bits, name=_text(f, "name"),
                        access=_access(f.findtext("access") or ""),
                        description=_text(f, "description"),
                    ))
            registers.append(Register(name=rname, address=f"0x{addr:X}",
                                      description=_text(reg, "description"), fields=fields))
        if registers:
            groups.append({"title": name, "registers": registers})
    return groups
