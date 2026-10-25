# Crest wordmark studies

Standalone design prototype. No application branding, routes, data, dependencies, or deployment configuration changed.

**Selected 2026-10-25:** lettering C / Balance with navy pairing B: navy `#20344D` in light mode and crisp white `#F8FAFC` in dark mode, without an accent stripe. See the [decision record](../../docs/decisions/2026-10-25-crest-wordmark.md). The owner requested documentation only; application integration is deferred. Earlier recommendations below describe the exploration sequence.

- **A — Heritage:** Rockwell Bold outlines. Strong slab serifs and a collegiate rhythm.
- **B — Precision:** Copperplate Bold outlines. Wedge serifs with an engraved, architectural character.
- **C — Balance (recommended):** Charter Bold outlines. Contemporary serif forms with warmth and clarity.

Main cap heights are normalized to 66 vector units across faces; suffix capitals use 30 units on the same baseline. All three pair uppercase CREST with smaller Arial Bold CFB on a shared baseline. Each SVG uses outlined glyph paths and `currentColor`; there are no runtime font requests or bundled font binaries. These are concept studies based on fonts available on the design machine. Production lettering and its asset licensing must be finalized after the owner selects a direction.

Open `index.html` through any static server. The page has a theme toggle, concept selector, enlarged specimens, and representative desktop and phone header contexts with explicitly marked fictional demo content. Header arrangements are static reproductions for visual comparison, not live app routes.

`outline.swift` regenerates the three SVGs on macOS using CoreText. `build-preview.py` embeds them into the self-contained comparison page. To regenerate from this directory:

```sh
swift -module-cache-path /tmp/crest-swift-cache outline.swift .
python3 build-preview.py
```

For local review, serve this folder on an available port (for example `python3 -m http.server 3211 --bind 127.0.0.1`).

## Color studies

The owner selected C / Balance. `colors.html` compares evergreen (recommended), navy, and oxblood in light and dark representative headers. `colors-comparison.svg` is a compact presentation sheet. Regenerate both with `python3 build-colors.py`. Dark marks share warm ivory; brand accents remain independent of data and publication colors.

## Navy exploration

`navy.html` and `navy-comparison.svg` compare C in navy on neutral light headers with either pale blue-gray or crisp white on neutral dark headers. Desktop and 26px phone specimens use the same outlined mark. Regenerate with `python3 build-navy.py`. This remains a standalone prototype; no app integration is included.
