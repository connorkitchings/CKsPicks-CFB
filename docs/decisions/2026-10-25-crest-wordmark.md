# Crest CFB wordmark decision

**Date:** 2026-10-25  
**Status:** Design selected by the owner; implementation deferred.  
**Authority:** The owner selected lettering C, then navy color option B, and explicitly requested documentation without implementation.

## Selected design

Retain the name **Crest CFB**. Use the **C / Balance** wordmark: uppercase **CREST** in Charter Bold-derived serif lettering, paired with smaller uppercase **CFB** in Arial Bold-derived sans-serif lettering on a shared baseline. The intended character combines collegiate heritage with a clean analytical feel.

Both parts form one horizontal mark and use the same solid foreground color. Preserve the selected outlined lettering, spacing, and proportions rather than approximating it with a live system-font stack. This decision applies to the wordmark; it does not change typography throughout the site.

## Theme colors

| Theme | Wordmark foreground | Reference preview background |
| --- | --- | --- |
| Light | Navy `#20344D` | Neutral light `#FAFAFA` |
| Dark | Crisp white `#F8FAFC` | Neutral dark `#09090B` |

This is **B / Navy + crisp white** from the navy comparison. The light and dark versions share identical lettering and geometry; only the foreground changes. Do not add the accent stripe from the earlier palette studies. The background values identify the reviewed mockups, not a decision to replace the site's surface colors. Publication status and data colors are outside this decision.

The owner preferred this pairing over the pale blue-gray dark-mode option. Earlier evergreen, ivory, and oxblood studies are exploration evidence, not the selected specification. Lettering C and navy pairing B refer to different rounds of comparison.

## Retained reference

The repository-relative prototype files are:

- `design/crest-wordmarks/crest-c.svg`: selected vector geometry, using paths and `currentColor`.
- `design/crest-wordmarks/navy.html`: light/dark desktop and phone specimens (the selected pair is B); it now embeds the regenerated outlines from `crest-c.svg`.

The SVG originally selected by the owner (superseded original, SHA-256 `b0d06ae0fd956b4e182962cf61c101a97d645d58c726b63d55dacd8d96b57a76`) was outlined from Charter Bold and Arial Bold, which are proprietary. It was removed from the tree on 2026-10-25 and remains only in git history of the dev branch.

**Font-source cleanup (2026-10-25):** to clear licensing, `crest-c.svg` was regenerated with the same arrangement (CREST at 66 units, CFB at 30 units, shared baseline, CFB to the right) from Arimo Bold (SIL Open Font License 1.1) for CFB and Bitstream Charter Bold (CTAN distribution with an explicit permissive licence) for CREST. The current `crest-c.svg` SHA-256 is `cfef1f48ac6c9fbd78ad7f1c8d099c244d67d4912a1535d0fad01f651661a4d6`, with `viewBox="-2.96 7.3 411.42 77.69"` (previously `-3 8 408.48 77`). Sources, checksums, licence notices, and the reproducible generator (`design/crest-wordmarks/build-wordmark.py --check`) are in `design/crest-wordmarks/PROVENANCE.md`. The `navy.html` specimens were regenerated from the new outlines.

The prototypes use 66 vector units for the CREST cap height and 30 for CFB, with a shared baseline. Desktop and phone specimens were shown at 32px and 26px overall SVG height respectively. Those display sizes are review references; final integration must verify fit and legibility within the existing header and phone app bar.

## Deferred implementation and acceptance

No application integration, deployment, or production change is authorized by this documentation request. The prototype remains separate from the application. Before implementing, obtain the owner's instruction to proceed and preserve this selected appearance.

Future integration should use the same scalable vector geometry in the desktop header and phone app bar, with theme-aware foreground colors and an accessible name of “Crest CFB.” Preserve existing home-link behavior and visible keyboard focus. Licensing and provenance of the font-derived outlines are documented in `design/crest-wordmarks/PROVENANCE.md`; no font files are bundled. Deployment has not happened; the app integration remains pending the usual release process.

Verify both themes at desktop and phone sizes, including a 320px viewport, for contrast, clipping, baseline alignment, CFB legibility, and theme changes without a font-loading shift. Prototype browser inspection is complete; actual application and real-device acceptance remain pending. Favicon, social images, exports, broader typography, and other brand surfaces need a separately defined scope.

Session evidence: `session_logs/2026-10-25/02-crest-wordmark-concepts.md` (repository file outside the published documentation site).
