# Stratum CFB wordmark provenance

`stratum-c.svg` (and the identical geometry inlined in `web/src/components/Wordmark.tsx`) is generated from two openly licensed fonts. No font file is stored in this repository; the SVG contains outlined paths only.

SHA-256 of `stratum-c.svg`: `f5f07e3d1894af5a85384983bda74a40eeeb3b374e29a4652b1d617816f78ba7`

## Sources

| Part | Font | File | Source | Licence |
| --- | --- | --- | --- | --- |
| `STRATUM` (cap height 66 units) | Bitstream Charter Bold (`CharterBT-Bold`, Type 1, renamed for TeX) | `bchb8a.pfb`, SHA-256 `c50fd6e717599f306b8b3261d309c56849f4366771c1983c875eabf46bc2b956`, file dated 1998-11-27 | https://mirrors.ctan.org/fonts/charter/bchb8a.pfb (CTAN package [`charter`](https://ctan.org/pkg/charter), https://ctan.org/tex-archive/fonts/charter) | Bitstream Charter licence in `readme.charter`; verbatim copy in [`licenses/Bitstream-Charter-readme.charter.txt`](licenses/Bitstream-Charter-readme.charter.txt) (SHA-256 `373f0fa4fc79653b3c1e7c6862cb9f242702c6bb9d8d7783c86d0aaf8414b0e7`, file dated 2001-02-21) |
| `CFB` (cap height 30 units) | Arimo Bold, version 1.33 | `Arimo-Bold.ttf`, SHA-256 `d7a8b187cf8444d4cfee102e8eae9e3043682fd5106d5d33ed677fe268a0e2ba` | https://raw.githubusercontent.com/googlefonts/Arimo/4a6255f269916ae7ad3fc2706b0935e7621396b8/fonts/ttf/Arimo-Bold.ttf (repository https://github.com/googlefonts/Arimo, commit `4a6255f269916ae7ad3fc2706b0935e7621396b8`, 2026-04-27, the latest commit touching this file) | SIL Open Font License 1.1; verbatim copy in [`licenses/Arimo-OFL.txt`](licenses/Arimo-OFL.txt) (SHA-256 `c46fda6859efb80c0a3c1faa868908a3d2fcb26eb7fd9602d73bebeec21bca3a`), from https://raw.githubusercontent.com/googlefonts/Arimo/4a6255f269916ae7ad3fc2706b0935e7621396b8/OFL.txt |

Arimo font-file copyright (name table): `Copyright 2020 The Arimo Project Authors (https://github.com/googlefonts/arimo)`. The repository `OFL.txt` header reads `Copyright 2026 The Arimo Project Authors (https://github.com/googlefonts/Arimo)`. Both are retained.

## Licence notices

### Bitstream Charter (verbatim from `readme.charter`)

```text
This is a copy of the Charter Type-1 fonts which Bitstream contributed
to the X consortium, renamed for use with TeX.

  (c) Copyright 1989-1992, Bitstream Inc., Cambridge, MA.

  You are hereby granted permission under all Bitstream propriety rights
  to use, copy, modify, sublicense, sell, and redistribute the 4
  Bitstream Charter (r) Type 1 outline fonts for any purpose and without
  restriction; provided, that this notice is left intact on all copies
  of such fonts and that Bitstream's trademark is acknowledged as shown
  below on all unmodified copies of the 4 Charter Type 1 fonts.

    BITSTREAM CHARTER is a registered trademark of Bitstream Inc.

TeX metrics, virtual fonts and LaTeX font definition files can be found
in the archive CTAN:fonts/metrics/freenfss.zip.

-- finis
```

The notice is retained here and in `licenses/`. The outlines in `stratum-c.svg` are modified (scaled, tracked, converted to cubic SVG paths), not unmodified copies of the font. The Type 1 file itself also carries an internal `Notice` string (`Copyright 1990 as an unpublished work by Bitstream Inc. All rights reserved. Confidential.`) from the original Bitstream release; the CTAN readme above is the licence grant that accompanies that file.

### Arimo (SIL Open Font License 1.1)

The complete licence text, with its copyright line, is in [`licenses/Arimo-OFL.txt`](licenses/Arimo-OFL.txt) and is reproduced unchanged from the upstream repository. The OFL permits use, modification and redistribution of derivatives (outlined glyph shapes here) provided the copyright notice and licence travel with them; the font is not sold on its own.

## Reproduce

Download the two font files into a directory outside the repository (for example `$FONTS`), confirm their SHA-256 values above, then run from the repository root:

```sh
uv run --with fonttools python -I design/stratum-wordmarks/build-wordmark.py \
  --charter "$FONTS/bchb8a.pfb" --arimo "$FONTS/Arimo-Bold.ttf"
```

Add `--check` to regenerate in memory and compare against `stratum-c.svg` and the inline SVG in `web/src/components/Wordmark.tsx` (exit code 1 on mismatch). The script refuses fonts whose SHA-256 differs from the pinned values. The original tooling was tested with `fonttools` resolved by `uv` on 2026-10-25; the Stratum generator check passed on 2026-10-27.

## Layout parameters

- Shared baseline at `y = 78`; SVG y-axis flipped from font units.
- `STRATUM`: Charter cap height 671 font units scaled to 66 units; tracking -1.05 units per glyph; pen origin `x = 0`.
- `CFB`: Arimo cap height 1409 font units (2048 em) scaled to 30 units; tracking -0.4 units; placed so its ink starts 18.98 units after the ink end of `STRATUM`.
- Tracking, gap, and ink-box padding (6.99 left, 3.52 top, 7.06 right, 5.81 bottom) retain the parameters of the earlier Crest wordmark.
- The generated Stratum viewBox is `-1.19 7.3 564.73 77.69`.
