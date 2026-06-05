"""Tests for CMSIS-SVD import."""
from __future__ import annotations

from pathlib import Path

from datasheet_wiki.config import Config
from datasheet_wiki.pipeline import run
from datasheet_wiki.svd import parse_svd

SVD = """<?xml version="1.0"?>
<device schemaVersion="1.3"><name>FOO85</name><peripherals>
  <peripheral><name>PORTB</name><baseAddress>0x40000400</baseAddress><registers>
    <register><name>DDRB</name><addressOffset>0x4</addressOffset><fields>
      <field><name>DDB</name><bitRange>[7:0]</bitRange><access>read-write</access></field>
    </fields></register>
    <register><name>PINB</name><addressOffset>0x8</addressOffset><fields>
      <field><name>PIN7</name><bitOffset>7</bitOffset><bitWidth>1</bitWidth><access>read-only</access></field>
    </fields></register>
  </registers></peripheral>
</peripherals></device>"""


def _write_svd(tmp_path: Path) -> Path:
    p = tmp_path / "foo.svd"
    p.write_text(SVD)
    return p


def test_parse_svd(tmp_path: Path):
    groups = parse_svd(_write_svd(tmp_path))
    assert len(groups) == 1 and groups[0]["title"] == "PORTB"
    ddrb, pinb = groups[0]["registers"]
    assert ddrb.name == "DDRB" and ddrb.address == "0x40000404"   # base + offset
    assert ddrb.fields[0].bits == "7:0" and ddrb.fields[0].access == "R/W"
    assert pinb.address == "0x40000408"
    assert pinb.fields[0].bits == "7" and pinb.fields[0].access == "R"


def test_svd_drives_register_map_and_export(tmp_path: Path, sample_pdf: Path):
    out = tmp_path / "wiki"
    cfg = Config.from_tier(sample_pdf, out, "small", progress=False, svd_path=_write_svd(tmp_path))
    run(cfg)
    regs = (out / "registers.html").read_text()
    assert "Authoritative register data" in regs and ">PORTB</h2>" in regs
    assert "0x40000404" in regs
    header = (out / "device.h").read_text()
    assert "DDRB_ADDR        (0x40000404u)" in header
    assert (out / "device.svd").exists()
