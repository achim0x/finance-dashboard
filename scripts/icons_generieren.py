"""Generate the PWA icons (192/512 + maskable) without external tooling.

Draws a simple flat "chart bars" logo on the brand color using pure Python
(zlib/struct PNG writer) — no Pillow dependency. Run once at scaffold time;
replace the icons with real artwork whenever available.

Usage: python scripts/icons_generieren.py
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

HINTERGRUND = (19, 64, 116)   # #134074 (theme color)
BALKEN = (141, 169, 196)      # #8da9c4
AKZENT = (255, 255, 255)


def _png_schreiben(pfad: Path, pixel: list[list[tuple[int, int, int]]]) -> None:
    hoehe = len(pixel)
    breite = len(pixel[0])
    roh = b"".join(
        b"\x00" + b"".join(struct.pack("BBB", *px) for px in zeile) for zeile in pixel
    )

    def _chunk(typ: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + typ
            + daten
            + struct.pack(">I", zlib.crc32(typ + daten) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(roh, 9))
        + _chunk(b"IEND", b"")
    )
    pfad.write_bytes(png)


def _icon(groesse: int, maskable: bool) -> list[list[tuple[int, int, int]]]:
    pixel = [[HINTERGRUND] * groesse for _ in range(groesse)]
    # Maskable icons need ~20% safe zone; draw the logo smaller then.
    rand = int(groesse * (0.28 if maskable else 0.18))
    innen = groesse - 2 * rand
    balken_breite = innen // 5
    hoehen = (0.45, 0.7, 1.0)  # three rising bars
    for i, anteil in enumerate(hoehen):
        x0 = rand + i * (balken_breite + balken_breite // 2)
        hoehe = int(innen * anteil)
        y0 = groesse - rand - hoehe
        farbe = AKZENT if i == len(hoehen) - 1 else BALKEN
        for y in range(y0, groesse - rand):
            for x in range(x0, min(x0 + balken_breite, groesse)):
                pixel[y][x] = farbe
    return pixel


def main() -> int:
    ziel = Path(__file__).resolve().parent.parent / "static" / "icons"
    ziel.mkdir(parents=True, exist_ok=True)
    for groesse in (192, 512):
        _png_schreiben(ziel / f"icon-{groesse}.png", _icon(groesse, maskable=False))
        _png_schreiben(ziel / f"icon-maskable-{groesse}.png", _icon(groesse, maskable=True))
    print(f"Icons written to {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
