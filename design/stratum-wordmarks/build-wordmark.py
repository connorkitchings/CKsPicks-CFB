#!/usr/bin/env python3
"""Regenerate the Stratum CFB wordmark (C / Balance) as outlined SVG paths.

STRATUM: Bitstream Charter Bold (bchb8a.pfb), cap height 66 units.
CFB:   Arimo Bold (Arimo-Bold.ttf, SIL OFL 1.1), cap height 30 units.
Both sit on one baseline (y = 78), CFB to the right of STRATUM.

Usage (fonts are not stored in the repository; see PROVENANCE.md for URLs):

  uv run --with fonttools python -I design/stratum-wordmarks/build-wordmark.py \
      --charter PATH/bchb8a.pfb --arimo PATH/Arimo-Bold.ttf            # write
  uv run --with fonttools python -I design/stratum-wordmarks/build-wordmark.py \
      --charter PATH/bchb8a.pfb --arimo PATH/Arimo-Bold.ttf --check    # compare

Without --charter/--arimo the paths default to the FONT_DIR environment variable
(expects FONT_DIR/bchb8a.pfb and FONT_DIR/Arimo-Bold.ttf). The font files are
verified against pinned SHA-256 digests before any outline is read.
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.t1Lib import T1Font
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
SVG_OUT = HERE / "stratum-c.svg"
TSX_OUT = HERE.parent.parent / "web" / "src" / "components" / "Wordmark.tsx"

PINNED = {
    "charter": "c50fd6e717599f306b8b3261d309c56849f4366771c1983c875eabf46bc2b956",
    "arimo": "d7a8b187cf8444d4cfee102e8eae9e3043682fd5106d5d33ed677fe268a0e2ba",
}

BASELINE = 78.0
STRATUM_CAP = 66.0
CFB_CAP = 30.0
STRATUM_TRACKING = -1.05  # units added after each STRATUM glyph advance
CFB_TRACKING = -0.4  # units added after each CFB glyph advance
STRATUM_X0 = 0.0  # STRATUM pen origin
GAP = 18.98  # STRATUM ink right edge to CFB ink left edge
# Ink-box padding retained from the earlier Crest wordmark.
PAD_LEFT, PAD_TOP, PAD_RIGHT, PAD_BOTTOM = 6.99, 3.52, 7.06, 5.81


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def verify(role: str, path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PINNED[role]:
        sys.exit(
            f"{role} font {path.name}: SHA-256 {digest} does not match "
            f"pinned {PINNED[role]} (checksum mismatch)"
        )


def layout(glyphset, names, cap_height, cap_units, tracking, x0):
    """Return [(path_d, (xmin, ymin, xmax, ymax))] in SVG coordinates, plus nothing else."""
    scale = cap_units / cap_height
    out, pen_x = [], x0
    for name in names:
        glyph = glyphset[name]
        # font y-up -> SVG y-down, baseline at BASELINE
        t = (scale, 0, 0, -scale, pen_x, BASELINE)
        svg = SVGPathPen(glyphset, ntos=num)
        glyph.draw(TransformPen(svg, t))
        bp = BoundsPen(glyphset)
        glyph.draw(TransformPen(bp, t))
        out.append((svg.getCommands(), bp.bounds))
        pen_x += glyph.width * scale + tracking
    return out


def build(charter_path: Path, arimo_path: Path):
    verify("charter", charter_path)
    verify("arimo", arimo_path)
    charter = T1Font(str(charter_path))
    charter.parse()
    cs = charter.getGlyphSet()
    stratum = layout(
        cs,
        list("STRATUM"),
        cap_height=671,
        cap_units=STRATUM_CAP,
        tracking=STRATUM_TRACKING,
        x0=STRATUM_X0,
    )
    stratum_right = max(b[2] for _, b in stratum)

    arimo = TTFont(str(arimo_path))
    ag = arimo.getGlyphSet()
    cmap = arimo.getBestCmap()
    cap = arimo["OS/2"].sCapHeight
    scale = CFB_CAP / cap
    bp = BoundsPen(ag)
    ag[cmap[ord("C")]].draw(bp)
    x0 = stratum_right + GAP - bp.bounds[0] * scale
    cfb = layout(
        ag,
        [cmap[ord(c)] for c in "CFB"],
        cap_height=cap,
        cap_units=CFB_CAP,
        tracking=CFB_TRACKING,
        x0=x0,
    )

    glyphs = stratum + cfb
    xmin = min(b[0] for _, b in glyphs)
    ymin = min(b[1] for _, b in glyphs)
    xmax = max(b[2] for _, b in glyphs)
    ymax = max(b[3] for _, b in glyphs)
    vx, vy = xmin - PAD_LEFT, ymin - PAD_TOP
    vw = (xmax + PAD_RIGHT) - vx
    vh = (ymax + PAD_BOTTOM) - vy
    viewbox = f"{num(vx)} {num(vy)} {num(vw)} {num(vh)}"
    paths = "".join(f'<path d="{d}"/>' for d, _ in glyphs)
    return viewbox, paths


def svg_text(viewbox: str, paths: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Stratum CFB" '
        f'viewBox="{viewbox}" fill="currentColor">{paths}</svg>\n'
    )


def tsx_svg(viewbox: str, paths: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label={BRAND_FULL} '
        f'viewBox="{viewbox}" fill="currentColor" className={{className}}>{paths}</svg>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    fd = os.environ.get("FONT_DIR")
    ap.add_argument(
        "--charter", type=Path, default=Path(fd) / "bchb8a.pfb" if fd else None
    )
    ap.add_argument(
        "--arimo", type=Path, default=Path(fd) / "Arimo-Bold.ttf" if fd else None
    )
    ap.add_argument("--check", action="store_true", help="compare, do not write")
    args = ap.parse_args()
    if not args.charter or not args.arimo:
        ap.error("--charter and --arimo are required (or set FONT_DIR)")

    viewbox, paths = build(args.charter, args.arimo)
    svg = svg_text(viewbox, paths)
    tsx_inner = tsx_svg(viewbox, paths)
    digest = hashlib.sha256(svg.encode()).hexdigest()

    if args.check:
        ok = SVG_OUT.read_text() == svg and tsx_inner in TSX_OUT.read_text()
        print(
            f"{'OK' if ok else 'MISMATCH'}: stratum-c.svg + Wordmark.tsx, sha256 {digest}, viewBox {viewbox}"
        )
        return 0 if ok else 1

    SVG_OUT.write_text(svg)
    text = TSX_OUT.read_text()
    start = text.index("<svg ")
    end = text.index("</svg>") + len("</svg>")
    TSX_OUT.write_text(text[:start] + tsx_inner + text[end:])
    print(f"wrote stratum-c.svg sha256 {digest}, viewBox {viewbox}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
