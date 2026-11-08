# Stratum CFB rebrand and Production publication

- **Status:** Implemented
- **Created:** 2026-10-27
- **Planner:** Sol
- **Approval source:** Owner explicitly requested implementation of this exact plan in chat, including dev push and Production publication.
- **Implementation log:** `session_logs/2026-10-27/02-stratum-cfb-rebrand.md`
- **Commit policy:** Commit contract with implementation; owner explicitly authorized commits, dev push and dev-to-main release as necessary to publish this plan.

## Goal and acceptance

Replace the public Crest identity with Stratum CFB across the application, exported graphics, metadata, small assets and current documentation. Retain the existing collegiate serif/sans lettering, navy #20344D in light mode and white #F8FAFC in dark mode, the existing site address and active football-data release. Success includes reproducible licensed vector assets, no stale current-facing Crest labels, responsive rendering and successful verified Production publication.

## Baseline and constraints

Implementation starts from dev b13f8c53 in an isolated managed worktree. Public identity is centralized in web/src/lib/brand.ts; Wordmark.tsx holds generated SVG paths and accessibility text. Favicon/social images and export labels consume brand constants; tests contain hardcoded old labels/filenames. The existing generator uses checksum-pinned Charter Bold and Arimo Bold fonts.

Repository/package names, Python modules, database identifiers, credentials, storage paths, automation identities, Vercel project names and site URL are compatibility identifiers and remain unchanged. Historical logs, decisions, completed contracts and Crest design studies retain historical names, with explicit supersession where appropriate. No new domain, model changes, migrations, pipeline runs or data publication.

## Ordered changes

1. Reconcile this contract, then implement in a fresh Terra worker context. Central brand becomes Stratum / Stratum CFB / S, export prefix stratum; public URL unchanged.
2. Create design/stratum-wordmarks/ with the STRATUM CFB outlined wordmark, reproducible generator, checksum/provenance and license notices. Preserve Crest studies. Use same font sources, baseline, cap sizes, tracking and palette; generated bounds accommodate longer lettering. Runtime loads no new font. Update Wordmark.tsx to the new paths/accessibility label, using brand constant for accessible identity where practical.
3. Audit desktop header, mobile app bar, footer, browser/application/OpenGraph/Twitter metadata, favicon, social image, chart footers and matchup summaries. Verify S monogram and stratum-prefixed downloads. Preserve content and image dimensions. Size the longer mark to fit 320px through desktop without clipping.
4. Update hardcoded brand expectations and add regression coverage for brand constants, metadata, favicon/social images and export labels. Retain real geometry, theme, accessibility, download and mobile behavior checks. Audit remaining old-name matches individually.
5. Update README, web README, docs landing page, MkDocs title and current architecture introduction. Add dated Stratum brand decision, mark Crest decision superseded, update naming evaluation selection and decision/plan navigation. Preserve history and annotate it instead of wholesale replacement.
6. Run validation and review locally on Production data. Commit and push dev; await successful CI. Create dev-to-main PR and merge with a merge commit after all PR checks pass. Verify Vercel Production commit, public rendering/exports and health; update docs/status.md and session evidence after publication. Record live data identifiers only in docs/status.md.

## Validation

- Generator --check reproduces vector and runtime wordmark; checksum mismatch refuses inputs.
- Desktop/mobile both themes at 320,390,1280,1440: readable lettering, no overflow/clipping, keyboard focus, accessible name, home navigation and stable theme changes.
- Inspect favicon and social-preview images. Download chart and matchup PNGs: Stratum labels and filenames, unchanged dimensions and no canvas overflow; light/dark export behavior retained.
- make check, make web-e2e, git diff --check, plus generator --check and actual visual inspection.
- Production-data local review before release, then successful dev/PR CI, merge-commit release, Vercel READY at intended main commit, live page/image/export readback and unchanged active data release/health.

## Handoff/amendments

The current owner request authorizes this contract and release. Parent persists the plan and documentation; a fresh Terra worker implements product changes under implement-plan. Preserve pre-existing work. Mechanical amendments may proceed only without changing scope, interfaces or acceptance; record reason and impact here. Material deviations return to planning before implementation. Mark Implemented only after validation and Production verification are complete.

## Completion evidence

Implemented and published 2026-10-27 through PR #17, merge commit `ab74daca7ba538a03d5fd0e0c7525391f0fb6232`. Full `make check` and `make web-e2e` passed; generator and invalid-font checks passed; eight wordmark screenshots, generated images and PNG exports inspected. Local Production-data review passed. Dev and PR CI passed. Vercel Production READY at the expected commit; public pages show Stratum, live favicon/social PNGs exactly match inspected images, and the actual Production matchup download uses Stratum branding/filename. Active data release and coverage unchanged. Detailed evidence is in the implementation session log; live data identifiers remain in Current Status.
