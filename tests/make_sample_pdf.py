"""Generate a small synthetic 'datasheet' PDF for tests and demos.

Produces a multi-page PDF with a real table of contents (outline), register-like
text, a code block, and cross references ("see Section 2.1", "page 4") so the
whole pipeline can be exercised without shipping a copyrighted datasheet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz


def make_sample(path: Path) -> Path:
    doc = fitz.open()

    pages_text = [
        # page 1
        ("1 Overview",
         "1 Overview\n\nThe FOO85 is a low-power 8-bit microcontroller. This document\n"
         "describes its architecture, registers, and programming model.\n"
         "For the pinout see Section 2. For timers see Section 3 on page 4.\n"),
        # page 2
        ("2 Pin Configuration",
         "2 Pin Configuration\n\nThe device has 8 pins. Port B is bidirectional.\n\n"
         "DDRB - Port B Data Direction Register\n\n"
         "Bit 7 - DDB7: Direction bit 7\nBit 0 - DDB0: Direction bit 0\n\n"
         "See Section 2.1 for electrical characteristics.\n"),
        # page 3 (subsection of 2)
        ("2.1 Electrical Characteristics",
         "2.1 Electrical Characteristics\n\nOperating voltage is 1.8V to 5.5V.\n"
         "Maximum current per pin is 40mA. See Table 2-1 for absolute maximums.\n"),
        # page 4
        ("3 Timer/Counter",
         "3 Timer/Counter\n\nThe 8-bit Timer/Counter0 supports PWM.\n\n"
         "TCCR0B - Timer/Counter Control Register B\n\n"
         "Bit 2 - CS02: Clock Select 2\nBit 0 - CS00: Clock Select 0\n\n"
         "Example C code to start the timer:\n\n"
         "#include <avr/io.h>\nint main(void) {\n    DDRB |= (1 << DDB0);\n"
         "    TCCR0B = (1 << CS00);\n    while (1) { }\n    return 0;\n}\n"),
        # page 5
        ("4 Instruction Set",
         "4 Instruction Set\n\nThe core executes most instructions in one cycle.\n"
         "See Section 1 for an overview.\n"),
    ]

    for _, text in pages_text:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 780), text, fontsize=11, fontname="helv")

    # internal cross-reference link on page 1 -> page 4 (timers)
    doc[0].insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(50, 110, 200, 124), "page": 3})

    # table of contents (1-based pages)
    toc = [
        [1, "1 Overview", 1],
        [1, "2 Pin Configuration", 2],
        [2, "2.1 Electrical Characteristics", 3],
        [1, "3 Timer/Counter", 4],
        [1, "4 Instruction Set", 5],
    ]
    doc.set_toc(toc)
    doc.set_metadata({"title": "FOO85 8-bit Microcontroller Datasheet"})

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample-datasheet.pdf")
    print(make_sample(out))
