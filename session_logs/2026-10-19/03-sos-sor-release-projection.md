# 2026-10-19 — SOS/SOR release projection (Workstream C)

Branch `connorkitchings/sos-sor-release-projection`, cut from `dev` at `510bb5b0`. Contract: `docs/plans/2026-10-19/02-sos-sor-release-projection.md`. Nothing is committed, and no migration has been applied to any database.

## What was built

**Python**
- `src/cks_picks_cfb/season/projection_resume.py`: `build_team_resume` and wiring helpers (`build_resume`, `resume_rows`, `source_qualified_period_id`, `canonical_fbs_teams`). Bridge coefficients are read from the pinned artifact (`BRIDGE_SHA256`). Probabilities and SOR are clamped to [0, 1] and [0, 100].
- `contracts/migrations/0028_team_resume.sql`, mirrored in `contracts/schema.sql`, `contracts/schema.ts` and `web/src/lib/schema.ts`.
- New staging projection set `resume_v1` = `charts_v2` + `team_resume` (`projection_common.py`); `charts_v2` stays frozen so retained releases still match their table set. `release.py` registers `team_resume`; `build_projections` raises on any unregistered built key; `SeasonInputs.bridge_sha256` added.
- Verification: projection-level `resume_periods`, `resume_values`, `resume_reference`, `resume_no_tied_finals`; prepare-level `resume_bridge_pinned`, `resume_rated_teams`, `resume_completed_parity`, `resume_record_recount`.
- Tests: `tests/test_projection_resume.py` (hand-computed fixtures 1-12, plus clamp regressions), `tests/test_season_resume_projection.py` (real pipeline), and edits to the existing season release, verification, prepare and Postgres tests.

**Web**
- `web/src/lib/team-resume.ts`, `v5.ts`, `season-release-query.ts`: optional-table read (`to_regclass` plus `existsFrom`/`rowsOf`); missing table or no rows gives empty, never an error. `team_resume` is intentionally outside the core and chart release-table lists.
- `season-release-context.ts`: `chartSetOf` now recognizes `resume_v1` through `RECORDED_PROJECTION_SETS`, mirroring Python. See "Defects found" below.
- `WEEK_GENERATIONS` removed; period labels come from résumé rows (`post_week`, and game count = sum of `completed_games` / 2), with date labels as the fallback. Descriptions now read "(N FBS games, weeks 0–N)".
- `RatingsView`: W-L (vs FBS), SOR with rank, WAA, SOS Played/Remaining/Full, Elite|Average switch, SOR/WAA/SOS sort (accepted in `?sort=`), single "—" for nulls, visible group labels, inline "Elite" link to `/methodology#elite-reference`.
- Methodology doc and page copy, including the `elite-reference` anchor.
- Fixtures: ratings fixture with résumé data for four teams, and `?period=no-resume` for a release without the table.

## Defects found by review, not by the implementers' own checks

- **Float artifact:** a real-candidate smoke check found 3 rows with SOR of about −2e-14 and `sor_p` just above 1, which migration 0028's CHECK constraints would have rejected at staging. Fixed by clamping; regression tests added; re-run shows none.
- **Chart-set recognition:** the Postgres release tests (which earlier agents' environments skipped) failed 6 tests. Root cause was the web's exact-match `chartSetOf`, which resolved a `resume_v1` release to no chart set. Fixed and covered by new tests.
- **Brief error:** the review brief said elite SOS should exceed average SOS. It is the reverse by construction (an elite reference loses less often), so elite values are lower. The code is right; UI and methodology copy say so.
- **UI polish after screenshots:** "Elite" link broke the sentence on phones; null SOR rendered "– –"; the two control groups had no visible labels. Fixed.

## Contract amendments

Recorded in the contract (2026-10-19, stage 1): average reference includes the evaluated team; margin is ratings-only (`offset_margin` not applied; intercept and slopes, including home field, are applied); SOR rank ties by `overall_rank`; FBS-only game counts; coefficients derived from the pinned artifact. Owner review accepted 1 and 3 to 5; amendment 2 was confirmed in code (home advantage is in the bridge intercept, and a real-bridge test shows 0.6433 home vs 0.3567 away for equal teams). Owner confirmation of amendment 2 is still outstanding.

## Verification (final tree)

- `uv run pytest -q`: 3398 passed, 34 skipped. `ruff check`, `ruff format --check` clean. `make contracts-check` passes. Postgres release tests: 125 passed.
- Web: lint, typecheck clean; `test:publication` 252 passed, 1 skipped; Playwright Chromium 139 passed, 9 skipped; `test:charts-gate` 12 passed; builds with charts on and off compile.
- Real-candidate smoke check (local Preview candidate): 1,242 rows, 138 teams x 9 periods including preseason; independent FBS W-L recount has 0 mismatches over 138 teams; no out-of-range values; top SOR at Week 7: BYU 5-0 (90.99), Kentucky, Miami, UCLA, Texas Tech.

## Not done / owner-gated

- Apply migration 0028 to Preview (owner go), then verify the `to_regclass` read and the missing-table fallback against the real Preview database before it is applied (fixture mode bypasses the database).
- Production migration and every Production readback: separate approval.
- Run the weekly runbook prepare from a clean commit, Preview rehearsal and readback, then the manual `/ratings` check for a known team.
- SOR header tooltips are `title` attributes (hover only, not on touch). The definitions are on the methodology page and in the note under the controls.
- The rating-trajectory chart still has no e2e coverage (skipped suite).
