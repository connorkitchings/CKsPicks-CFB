# Session: Track 1 Production promotion preparation

## TL;DR
- **Worked On:** Approved Track 1 implementation, venue source pinning, fresh restricted Preview/Production evidence and full web release review.
- **Outcome:** Code/tests delivered, pinned Production venue dry run passed with 271/271 cities and empty business diff, local validation green. Repaired a real PostgreSQL query-shape defect. Rating-source ambiguity was resolved in a reopened pass using rendered-row provenance. Release preparation packet is HOLD for exact-SHA CI/Preview gates.
- **Plan Contract:** [Track 1](../../docs/plans/2026-10-07/01-track1-production-promotion.md).
- **Approval / Status:** Explicit exact-path implementation handoff; follow-up explicitly allowed behavior-preserving localized web query repair. In Progress; no publication or promotion approval.
- **Blockers:** No final committed candidate, PR/green CI, or candidate restricted-role Vercel Preview verification.
- **Next:** User commit/push/PR and exact-SHA real Preview verification; recapture all live evidence before either separate Production decision.

## Context and Decisions
- Started clean on `dev` at plan commit `1405f33b4853f7ac15f6050068e5e21f8c0e9f85`. No Git mutations or delegation.
- Read AGENTS.md, status, implementation skill, approved Track 1 plan, Contract 04/Appendix B, Stage 7A and recent Stage 6B/7A/7B session context. Applied Vercel deployment and React best-practices guidance to review/query repair.
- Sandbox Keychain access initially failed. Explicitly reviewed host read-only retries succeeded as `cks_prod_pipeline` and `cks_preview_pipeline`. Credentials were never printed; owner credentials were not used for data evidence. R2 environment configuration verified. No repository data directory was created.
- User follow-up authorized repair of the discovered 42P10 defect if behavior-preserving; a semantic selector change must remain a hold. The repair adds cutoff to DISTINCT and extracts the actual query for regression coverage. It retains existing source selection.

## Work Completed
- Added `--games-version`, preserving unpinned default and validated/season-scoped catalog selection. Quality identity now includes both source content hashes.
- Reject ambiguous selected Silver game/venue source duplicates before the legacy transform can discard them. Missing versions, absent games, unknown venues and missing city fail before publication; city-only international venues pass.
- Captured fresh restricted-role schema/grants, migration bytes, Week 5 designations, current pointer/selections, full current 2026 games, before/proposed venues and serving hashes in both environments.
- Reconciled newest validated Silver games and pinned venues; 271 current database games resolve with cities, zero unresolved IDs, two international rows without state. Pinned Production dry run passed. Exact before/proposed business diff is empty. Existing apply still rewrites timestamps and remains gated.
- Independently reverified existing prospective designations against authentic live sources and immutable R2 objects with read-only storage. No attestation registration, migration or serving write.
- Reviewed all 19 `main..HEAD` web files and this session's repair. `.vercelignore` stays web-only; no web code activates Window 2.
- Reproduced 42P10 in Preview and Production, repaired generated Drizzle SQL, added cutoff/scope regression, verified repaired query in both real environments.
- Found competing manifests at identical cutoffs. Provenance query is not filtered to the rating source used by rendered ratings; choosing a source requires a reviewed semantic decision. Preserved evidence and stopped promotion.
- Captured current Vercel Production URL/commit/root/branch and retained rollback target. Production matches `main`; Preview and remote `dev` are older. No open dev-to-main PR or returned dev CI runs.
- Created [reviewable hold packet](../../docs/plans/2026-10-07/track1-release-packet.md) and checksummed durable non-secret evidence, including exact before venue payloads.

## Files Modified
- `scripts/pipeline/publish_game_venues.py` — Source pin, hashes and duplicate guard.
- `tests/test_game_venues.py` — Exact lookup, missing versions and fail-before-write coverage.
- `web/src/lib/matchup.ts`, `matchup-rating-query.ts`, `matchup-rating-query.test.ts`, `web/package.json` — Behavior-preserving query-shape repair and actual Drizzle SQL regression.
- Track 1 plan, hold packet/evidence, plan index, status/Contract 04 preparation pointers, this log — Observed implementation and release gate state.

## Validation
- [x] Full Python: 2,039 passed, 12 skipped (284.82s).
- [x] Focused venue: 19 passed after final import cleanup.
- [x] Disposable PostgreSQL migration/batch/attestation/revocation/authorization: 32 passed; cluster stopped.
- [x] Full Ruff and changed-file format check; `make contracts-check` with host cache access.
- [x] Final web lint/typecheck/publication: 134 passed; production build in fixture mode.
- [x] Final Performance/matchup Playwright: 24 passed.
- [x] Pinned Production venue dry run; real generated query checks in Preview/Production; independent prospective verification.
- [x] Post-dry-run serving hashes unchanged in both environments.
- [x] MkDocs and `git diff --check` at close-out.
- [ ] Exact-SHA CI/real restricted-web Preview routes, live apply/deployment readback: held, not performed.

## Amendments and Blockers
- SQL repair explicitly authorized by user follow-up; no architecture/public-interface/cutover changes. No automatic-review rejection remains.
- Initial pass held source ambiguity pending authority clarification. The reopened user instruction and source-tagged rendered rows resolve this under the existing lineage contract; see the reopened-pass record below.
- Actual web-login deployment identity remains unverified; local `web/.env` uses an owner login and was not used as restricted Preview proof. Effective web-role grants were read from live databases.
- Current database has 271 games ending October 4 despite pointer Week 6; this is baseline evidence, not provider schedule/quote completeness or a week-opening authorization.

## Handoff Notes
- **Resume at:** Source-binding repair is complete. Commit/push/PR under user control; bind packet to the resulting SHA, green CI and real Vercel Preview. Recapture live evidence before separate venue and deployment decisions.
- **Watch out for:** Empty business diff still means timestamp writes if apply runs. Do not copy evidence into Stage 7B release authority, change selections/current week, or request Production approval before the packet gates pass.
- **Proposed commit:** `fix(release): pin venue inputs and repair matchup provenance SQL` (user-run; no stage/commit/push performed).

**tags:** ["release", "window1", "venues", "web", "production", "hold"]


## Reopened pass: rendered-source binding

The user explicitly requested resolving source ambiguity under Stage 7A/Track 1 if derivable. The owning source is present on every `getRatingsAsOf` row; qualified periods and their preseason backfills use the same owning manifest. The guard derives one source from the exact rendered teams, filters provenance by that source, and fails closed when either team is missing or sources are missing/mixed/ambiguous. No public selection/rating ownership changed.

Added same-cutoff competing-manifest regression plus an actual PostgreSQL execution regression of generated Drizzle SQL. Three focused tests pass with no skips. Real source-bound Preview/Production queries pass and exclude the competing source at the same cutoff. Full web checks rerun: lint/typecheck/build pass, publication 135 passed with one optional DB test skipped (separately passed above), Playwright 24 passed. Ruff and fresh serving fingerprint readbacks pass; disposable cluster stopped. Full Python is unchanged from the completed 2,039-pass run because this reopening edits only web/docs. Evidence and candidate file checksums refreshed. Semantic hold lifted; exact-SHA PR/CI/restricted-web Preview gate remains.

**Resume at:** User commit/push/PR, verify exact-SHA CI and real restricted-role Preview routes, and refresh the packet before either separate Production authorization. No venue apply, serving write, deployment or Git operation occurred.
