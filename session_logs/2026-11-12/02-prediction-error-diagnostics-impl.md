# Session: Prediction-error diagnostics implementation

## TL;DR

- **Worked On:** Contract 3, read-only prediction-error diagnostics for 2021 to 2025, then the three owner-approved additions (site class, conference, totals over-prediction diagnostic).
- **Outcome:** Slice modules, regeneration script, tests and the report `docs/modeling/prediction_error_diagnostics_2021_2025.md`. The reproduction check passed (2025 frozen V5 MAE 14.1596 margin, 13.3558 total). Only a true partial-quarantine re-estimation could not be computed.
- **Plan Contract:** [`docs/plans/2026-11-12/03-prediction-error-diagnostics.md`](../../docs/plans/2026-11-12/03-prediction-error-diagnostics.md) (amendment dated 2026-11-12)
- **Approval / Status:** Owner approved implementation and the three additions 2026-11-12.
- **Blockers:** None for the report. The partial-quarantine re-estimation needs the V5 control replay.
- **Next:** Owner review, commit and pull request into `dev`.

**tags:** ["ratings-lab", "diagnostics", "offseason-2027"]

## Context and Decisions

- Corpus: the persisted ratings-lab corpus in local lab storage, read through `LocalLabStore` directly (no bucket credentials needed for it).
- Frozen V5 equals the v5-common bridge row for row in 2022 to 2025 (max prediction difference 0), so slices use v5-common rows, which also carry the 90% intervals and 2021 (bridge fit on 2015 to 2019). The script asserts the equality.
- Slices use model outputs, timing, stage, evidence-coverage flags, site and conference only. No market line or betting result defines a slice. 2026 and 2020 rows are rejected by `require_development_view`.
- Venue and conference data: not in the corpus (`home_host` 1, `venue_unknown` true everywhere). Found in the `fbs_involved_games` dataset, reachable through the corpus's own pinned core-eligibility references. One read-only read of the Preview data lake with the checkout's existing Preview read credentials (found by `find_dotenv`; values never printed), then cached at `ratings-lab/v1/diagnostics/<corpus run id>/game_site_context.parquet` in the local lab output. Later runs and `--check` use the cache and make no network call. No writes to any bucket, no provider calls.
- Site classes: neutral flag; a team's home venues are venue ids with at least 3 non-neutral hosted games in 2021 to 2025 plus its most frequent venue; other non-neutral venues are their own class. Conference is each home team's conference in that season.
- Totals diagnostic: team-points errors are exact combinations of the margin and total errors; the rolling-origin recentering uses only earlier seasons' mean total error and is labelled a diagnostic.
- Not computable: the partial-quarantine sensitivity (needs ratings re-estimated without the quarantined games); a descriptive exposure proxy is reported instead.

## Files Modified

- `src/cks_picks_cfb/ratings_lab/error_slices.py`, `site_context.py`, `total_bias.py` (new, pure)
- `scripts/research/run_prediction_error_diagnostics.py` (new; `--check` verifies byte-for-byte reproduction)
- `tests/ratings_lab/test_error_slices.py`, `tests/ratings_lab/test_site_and_total_bias.py` (new, synthetic frames)
- `docs/modeling/prediction_error_diagnostics_2021_2025.md` (generated)
- `mkdocs.yml`, `docs/modeling/evaluation.md`, `docs/planning/offseason-2027-backlog.md`, `docs/plans/index.md`, `docs/plans/2026-11-12/03-prediction-error-diagnostics.md`

## Validation

- `uv run pytest tests/ratings_lab`: 74 passed.
- Script `--check`: report reproduces byte for byte.
- `ruff check`, `ruff format --check`, `git diff --check`, `mkdocs build --strict --quiet`: clean (see the final report).
- Web steps of `make check` skipped (web dependencies not installed in this worktree).

## Amendments and Blockers

See the dated amendment in the contract. No blockers.
