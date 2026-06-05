"""Unit tests for the C-header / CMSIS-SVD generators."""
from __future__ import annotations

from datasheet_wiki.codegen import build_c_header, build_svd
from datasheet_wiki.enrich.base import Register, RegisterField


def _groups(address=""):
    return [{
        "title": "Timer/Counter",
        "registers": [Register(
            name="TCCR0B", address=address, description="control",
            fields=[RegisterField(bits="2", name="CS02", access="R/W", description="clk"),
                    RegisterField(bits="7:0", name="ALL", access="R/W", description="all")],
        )],
    }]


def test_c_header_fields_and_guard():
    h = build_c_header(_groups(), "FOO85", "ds.pdf")
    assert "#ifndef FOO85_H" in h and "#endif" in h
    assert "#define TCCR0B_CS02_Pos    (2u)" in h
    assert "#define TCCR0B_ALL_Msk    (0xFFu << TCCR0B_ALL_Pos)" in h


def test_c_header_address_define_only_when_present():
    assert "TCCR0B_ADDR" not in build_c_header(_groups(""), "D", "x")
    assert "TCCR0B_ADDR        (0x40u)" in build_c_header(_groups("0x40"), "D", "x")


def test_svd_requires_address():
    assert build_svd(_groups(""), "D", "x") is None
    svd = build_svd(_groups("0x40"), "FOO85", "ds.pdf")
    assert svd and "<addressOffset>0x40</addressOffset>" in svd
    assert "<bitOffset>0</bitOffset><bitWidth>8</bitWidth>" in svd
    assert "<access>read-write</access>" in svd
