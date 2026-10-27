# Stratum CFB brand decision

**Date:** 2026-10-27  
**Status:** Accepted; implementation and Production publication authorized by the owner.

## Identity

The public product name is **Stratum CFB**, with **STRATUM CFB** as the primary wordmark, **S** as the small monogram and **stratum** as the download filename prefix. The owner selected Stratum after rejecting Crest because of its toothpaste association. This decision supersedes the [Crest wordmark decision](2026-10-25-crest-wordmark.md); previous studies and release evidence remain historical records.

## Visual specification

Retain the collegiate serif/sans balance: STRATUM outlined from Bitstream Charter Bold, CFB outlined from Arimo Bold on a shared baseline. Use navy `#20344D` in light mode and white `#F8FAFC` in dark mode, without a decorative stripe. Preserve the existing site typography, surfaces, rank colors and team colors.

The new assets, checksum-pinned generator, license notices and provenance live in repository directory `design/stratum-wordmarks/`. Runtime lettering is outlined SVG, requiring no font downloads. The longer lettering must remain legible and contained at 320px, 390px and desktop widths.

## Public surfaces and compatibility

The identity covers headers, phone app bar, accessibility labels, footer, metadata, favicon, social preview, chart and matchup export labels and filenames, and current documentation. Export content and dimensions remain unchanged.

The existing [website address](https://c-ks-picks-cfb.vercel.app) remains in use. Repository/package names, Python imports, database/storage identifiers, credentials, automation identities and Vercel project names are compatibility identifiers and retain their existing names. This is a web rebrand only: no new domain, migrations, modeling changes, pipeline runs or active data-release change.

## Validation and release authority

The owner authorized implementation and dev-to-main Production publication in chat. Follow the [approved implementation contract](../plans/2026-10-27/stratum-cfb-rebrand.md), including generator reproducibility, visual review, `make check`, `make web-e2e`, passing CI and merge-commit release. Live deployment evidence belongs in [Current Status](../status.md), with details in session log `session_logs/2026-10-27/02-stratum-cfb-rebrand.md`.
