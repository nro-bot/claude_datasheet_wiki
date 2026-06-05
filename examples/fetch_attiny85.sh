#!/usr/bin/env bash
# Download the ATtiny85 datasheet locally for a demo build.
#
# The PDF is copyrighted by Microchip — it is downloaded to your machine for
# personal use and is git-ignored (never committed to this repo).
set -euo pipefail

DEST="${1:-attiny85.pdf}"

# Microchip's current ATtiny25/45/85 full datasheet. If this URL ever changes,
# search "ATtiny85 datasheet" on microchip.com and save the PDF as $DEST.
URL="https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-2586-AVR-8-bit-Microcontroller-ATtiny25-ATtiny45-ATtiny85_Datasheet.pdf"

echo "Downloading ATtiny85 datasheet -> $DEST"
if command -v curl >/dev/null 2>&1; then
  curl -L --fail -o "$DEST" "$URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$DEST" "$URL"
else
  echo "Need curl or wget. Or download manually from microchip.com and save as $DEST." >&2
  exit 1
fi

echo
echo "Done. Build your wiki with:"
echo "  datasheet-wiki build $DEST --compute small"
echo "  datasheet-wiki serve wiki/$(basename "${DEST%.pdf}")"
