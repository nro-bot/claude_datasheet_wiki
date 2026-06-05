"""A small built-in glossary of common embedded / microcontroller acronyms.

Used to (a) build a Glossary page of the terms that actually appear in a given
datasheet and (b) wrap the first occurrence of each term in a section summary
with an <abbr> tooltip — handy for beginners. Entirely heuristic and local.
"""
from __future__ import annotations

import html
import re
from typing import Dict, List, Tuple

# Keyed by upper-case term. Curated to avoid 2-letter terms that collide with
# ordinary words. Datasheet-specific register names are intentionally excluded.
GLOSSARY: Dict[str, str] = {
    "ADC": "Analog-to-Digital Converter",
    "DAC": "Digital-to-Analog Converter",
    "PWM": "Pulse-Width Modulation",
    "GPIO": "General-Purpose Input/Output",
    "UART": "Universal Asynchronous Receiver/Transmitter",
    "USART": "Universal Synchronous/Asynchronous Receiver/Transmitter",
    "SPI": "Serial Peripheral Interface",
    "I2C": "Inter-Integrated Circuit (two-wire serial bus)",
    "TWI": "Two-Wire Interface (I²C-compatible)",
    "DMA": "Direct Memory Access",
    "NVIC": "Nested Vectored Interrupt Controller",
    "ISR": "Interrupt Service Routine",
    "IRQ": "Interrupt Request",
    "WDT": "Watchdog Timer",
    "RTC": "Real-Time Clock",
    "PLL": "Phase-Locked Loop",
    "CRC": "Cyclic Redundancy Check",
    "FIFO": "First-In, First-Out buffer",
    "MISO": "Master In, Slave Out (SPI)",
    "MOSI": "Master Out, Slave In (SPI)",
    "SCK": "Serial Clock (SPI)",
    "SCL": "Serial Clock line (I²C)",
    "SDA": "Serial Data line (I²C)",
    "MCU": "Microcontroller Unit",
    "CPU": "Central Processing Unit",
    "ALU": "Arithmetic Logic Unit",
    "RAM": "Random-Access Memory",
    "ROM": "Read-Only Memory",
    "SRAM": "Static Random-Access Memory",
    "EEPROM": "Electrically Erasable Programmable Read-Only Memory",
    "FLASH": "Flash (non-volatile) program memory",
    "JTAG": "Joint Test Action Group debug interface",
    "SWD": "Serial Wire Debug",
    "LSB": "Least-Significant Bit",
    "MSB": "Most-Significant Bit",
    "OSC": "Oscillator",
    "VREF": "Reference Voltage",
    "BOD": "Brown-Out Detection",
    "POR": "Power-On Reset",
    "CMOS": "Complementary Metal-Oxide-Semiconductor",
    "TTL": "Transistor-Transistor Logic",
    "MOSFET": "Metal-Oxide-Semiconductor Field-Effect Transistor",
    "LED": "Light-Emitting Diode",
    "CTC": "Clear Timer on Compare match",
    "PRR": "Power Reduction Register",
    "SFR": "Special Function Register",
    "LDO": "Low-Dropout (voltage regulator)",
    "ESD": "Electrostatic Discharge",
    "RISC": "Reduced Instruction Set Computer",
    "AC": "Analog Comparator",
    "POT": "Power-On Threshold",
}

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9/²]*")


def present_terms(text: str) -> List[Tuple[str, str]]:
    """Glossary terms that actually appear in `text`, as sorted (term, defn)."""
    found = set()
    for m in _TOKEN.finditer(text or ""):
        key = m.group(0).upper().replace("²", "2")
        if key in GLOSSARY:
            found.add(key)
    return [(k, GLOSSARY[k]) for k in sorted(found)]


def annotate(text: str) -> str:
    """HTML-escape `text` and wrap the first occurrence of each glossary term in
    an <abbr> tooltip."""
    seen = set()
    out: List[str] = []
    last = 0
    for m in _TOKEN.finditer(text or ""):
        out.append(html.escape(text[last : m.start()]))
        w = m.group(0)
        key = w.upper().replace("²", "2")
        if key in GLOSSARY and key not in seen:
            seen.add(key)
            out.append(
                f'<abbr class="gloss" title="{html.escape(GLOSSARY[key])}">{html.escape(w)}</abbr>'
            )
        else:
            out.append(html.escape(w))
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)
