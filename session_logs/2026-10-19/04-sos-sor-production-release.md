# 2026-10-19 — SOS/SOR release projection: Preview and Production release

Code shipped on `dev` and `main` at commit `5060aa60` (`feat(web): simplify ratings résumé columns`). CI passed on `dev`. Contract: `docs/plans/2026-10-19/02-sos-sor-release-projection.md`. Earlier build work is in `03-sos-sor-release-projection.md`.

## Outcome

- Migration 0028 (`season_release_team_resume`) was applied by the owner to Preview, then Production.
- Candidate `season-2026-2cdf8916d915e21b3f25fa71` was prepared from clean commit `5060aa60`. All 32 checks passed, including eight `resume_*` checks. `team_resume` has 1,242 rows (138 teams x 9 periods, including preseason). Serving payload SHA-256: `b04544766245f8c40b48323ca9bab2f9a5a44a73c920df77127c47d428838e20`.
- Preview was activated first, then Production. Both activation readbacks have SHA-256 `6b52cdf0a1c464c9873968fc58088eb431afcc82e65f3c47b1ed8eacdbe10429`.
- Active releases are now `production-season-2026-2cdf8916d915e21b3f25fa71` and `preview-season-2026-2cdf8916d915e21b3f25fa71`. Week 8 has 56/56 games predicted and lined, as of 2026-10-19T14:10:00Z.

## Preparation command

The Makefile `season-prepare` target selects `revision_manifest_w<WEEK>_v1.json`, so Week 8 needed the direct command:

`run_season.py prepare --revision-manifest conf/season/2026/revision_manifest_w8_v2.json --through-week 7 --next-week 8 --as-of 2026-10-19T14:10:00Z`

## Verification

- Preview independent read-only check against the prior Week 8 release `production-season-2026-b7bc98eb26fa667f6c0941d6`'s Preview twin (`preview-season-2026-b7bc98eb26fa667f6c0941d6`): `game_results`, `system_stats`, `games` and `market_quotes` identical. In `predictions`, `prediction_grades` and `v5_rating_snapshots`, every value column is identical. Only release-ID identity columns differ (`run_id`, `spread/total_model_version`, `snapshot_id`, `source_run_id`).
- Live Production after deploy: `/`, `/results`, `/ratings`, `/performance` and `/api/health` return 200. `/charts` returns 404. Health reports the new active release, Week 8, 56/56 predicted and lined, data as of 2026-10-19T14:10:00Z.
- `/ratings` shows "Post-Week 0..7" labels, FBS W-L, SOR rank, and SOS Played/Remaining/Full. It shows no WAA and no uncertainty.

## Display decisions

- SOR is shown as rank only.
- WAA and overall uncertainty are not displayed.
- SOS uses one measure: the average FBS team.
- Elite SOS is stored but not shown.

## Rollback

- Production rollback target: `production-season-2026-b7bc98eb26fa667f6c0941d6`. Use only with owner authorization.
- Preview rollback is not supported by the tooling.

## Process lessons

- **Makefile target mismatch:** `season-prepare` hardcodes the `_v1` manifest name. Future weeks that use a `_v2` manifest need the direct `run_season.py prepare` command, or the target should accept the manifest as a parameter.
- **Skipped Postgres tests:** Postgres release tests were skipped in earlier agent sandboxes. Once run, they exposed a real defect: the web's exact-match `chartSetOf` did not recognize `resume_v1`, so a `resume_v1` release resolved to no chart set. Run these tests in every environment that can reach Postgres.
- **Float artifact:** a float artifact put SOR and `sor_p` slightly outside [0, 1] and [0, 100]. Migration 0028's CHECK constraints would have rejected those rows. Fixed with a clamp and regression tests.
- **UI changes after prepare:** release requires HEAD to equal the prepared `code_sha` and a clean tree. Any UI change after prepare requires a re-prepare.

## Not done

- No Week 8 market refresh was performed. The next market refresh remains due before 2026-10-20T18:00:00Z (see `docs/status.md`).
- The weekly ingestion process review is still open (`docs/planning/weekly-operations-process-review.md`).

**tags:** ["production", "week8", "sos-sor", "release", "migration-0028"]
