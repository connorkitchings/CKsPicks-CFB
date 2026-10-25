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
- `design/crest-wordmarks/navy.html`: reviewed light/dark desktop and phone specimens.
- `design/crest-wordmarks/navy-comparison.svg`: compact comparison; the selected pair is B.

The selected SVG's SHA-256 is `b0d06ae0fd956b4e182962cf61c101a97d645d58c726b63d55dacd8d96b57a76`.

The prototypes use 66 vector units for the CREST cap height and 30 for CFB, with a shared baseline. Desktop and phone specimens were shown at 32px and 26px overall SVG height respectively. Those display sizes are review references; final integration must verify fit and legibility within the existing header and phone app bar.

## Deferred implementation and acceptance

No application integration, deployment, or production change is authorized by this documentation request. The prototype remains separate from the application. Before implementing, obtain the owner's instruction to proceed and preserve this selected appearance.

Future integration should use the same scalable vector geometry in the desktop header and phone app bar, with theme-aware foreground colors and an accessible name of “Crest CFB.” Preserve existing home-link behavior and visible keyboard focus. Confirm production use rights for the font-derived asset before shipping; the studies contain outlines rather than bundled font files, and do not themselves establish licensing clearance.

Verify both themes at desktop and phone sizes, including a 320px viewport, for contrast, clipping, baseline alignment, CFB legibility, and theme changes without a font-loading shift. Prototype browser inspection is complete; actual application and real-device acceptance remain pending. Favicon, social images, exports, broader typography, and other brand surfaces need a separately defined scope.

Session evidence: `session_logs/2026-10-25/02-crest-wordmark-concepts.md` (repository file outside the published documentation site).
