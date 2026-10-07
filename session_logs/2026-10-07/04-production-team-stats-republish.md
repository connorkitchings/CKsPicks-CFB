# Session: Production team-stats republish (as-of weeks 1-5)

## TL;DR
- **Worked On:** Plan, pre-apply evidence and post-apply verification for republishing Production `team_season_stats` with the punt-return fix.
- **Outcome:** The user ran the apply at 2026-10-07 17:05:40Z. Production now has 11,506 rows and equals Preview on every column except `updated_at`. No other serving state changed.
- **Plan Contract:** Session plan (user-approved in Plan Mode); fast path, no `docs/plans/` contract.
- **Approval / Status:** Scope ("weeks 0-5" = as-of weeks 1-5) and dry-run diff approved by the user; the Production write was user-run. The agent made no Production write.
- **Blockers:** None for this step. The as-of-6 snapshot needs the post-Week-5 Silver refresh (`prepare-week`), which has not run.
- **Next:** Commit the evidence folder and doc edits (user); then the as-of-6 snapshot once its Silver prerequisites exist; Week 7 cutover after Week 6 finals plus 24 hours.

## Context and Decisions
- Unpinned, the publisher uses the newest validated Silver; Production's newest `game_outcomes` (`d01d92ac`, 2026-10-04) postdates the inputs of the existing stats, so every input was pinned to the versions recorded in the existing rows' `source_versions`. The only change is therefore the code (the punt fix).
- A first Preview dry run failed with a usage error because zsh does not word-split an unquoted variable; the pins went in as one argument. Rerun with an array. The apply command was written with literal flags.
- The dry run's "changed" count is value-only (`|Δvalue| > 1e-9`); rank-only and play-count-only changes are separate. Reconciled against the table dumps: 2,291 value + 479 rank-only + 153 play-count-only = 2,923 rows, plus 1,046 new `ppa_per_play` rows.

## Work Completed
- Confirmed the five pinned Silver versions validated in the Production catalog; captured the Production before payload (10,460 rows, SHA-256 `505de257…`) and Preview's table (11,506 rows, `e82e6ab7…`).
- Dry runs, pinned, `--weeks 1-5 --diff`: Preview 0 changes; Production 2,291 value changes, 1,046 new rows, 0 removed.
- After the user's apply: full-table equality with Preview, CFBD comparison (as-of weeks 4 and 5: all four gated metrics at 0.956-0.997 against the 0.85 floor), fingerprint audit (only `team_season_stats` changed), live matchup page (PPA/play dashes 8 → 0).

## Files Modified
- New `docs/plans/2026-10-07/team-stats-republish/` (payloads, dry-run and verification logs, scripts, summary, checksums).
- `docs/status.md` (Release state paragraph, Production team-stats line), `docs/data/known_issues.md` (punt entry: republish done), this log.

## Validation
- [x] Row-level equality with Preview (0 differing rows apart from `updated_at`); one `updated_at` value across all rows.
- [x] Change set equals the dry run's prediction (2,923 changed, 1,046 new, 7,537 unchanged).
- [x] CFBD comparison gated metrics pass; explosiveness (ungated) correlates lower and was not compared with its pre-fix value.
- [x] Serving fingerprints unchanged except `team_season_stats`.
- [x] Ruff, `git diff --check`, docs build (see below); evidence checksums verified.
- [ ] Other matchup pages, browser rendering and phone width not checked.

## Amendments and Blockers
- None. Rollback not needed. If ever required: upsert `before-production.json.gz` (restores the 10 older metrics); the 1,046 `ppa_per_play` rows would remain (pipeline role cannot DELETE).

## Handoff Notes
- **Resume at:** user commits `docs/status.md`, `docs/data/known_issues.md`, `session_logs/2026-10-07/04-production-team-stats-republish.md` and `docs/plans/2026-10-07/team-stats-republish/`; keep `02-docker-python-ci-parity.md` out.
- **Watch out for:** Production matchup ranks changed materially (explosive-rate ranks up to 52 places); `docs/status.md` records it. The V5 per-play companion tables still count returned punts until the Window 2 Silver rebuild.
- **Proposed commit:** `docs(data): record Production team-stats republish for as-of weeks 1-5`

**tags:** ["team-stats", "production", "republish", "verification", "matchup"]
