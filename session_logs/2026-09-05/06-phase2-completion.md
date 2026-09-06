# Session: Phase 2 Completion

## TL;DR

- **Worked On:** Reconciled the Phase 2 handoff, repaired postseason request
  discovery and explicit Preview routing, and validated the code checkpoint.
- **Outcome:** The corrected dry-run discovers exactly 20 missing postseason
  requests. Code and documentation gates pass; operational execution awaits
  the required user-executed commit so apply mode can bind artifacts to HEAD.
- **Plan Contract:** `docs/plans/2026-09-05/02-data-repair-and-recertification.md`
- **Approval / Status:** User explicitly authorized the Phase 2 completion
  plan on 2026-09-05; contract remains In Progress.
- **Blockers:** Required committed-code checkpoint before provider calls and
  immutable materialization.
- **Next:** User commits the checkpoint; execute the 20-request bounded capture,
  then Phase 2c Silver rebuild and Phase 2d recertification.

## Context and Decisions

- The sealed v3 schedule denominator contains 8,521 regular-season rows and no
  postseason rows. The first Phase 2b execution captured postseason games but
  could not derive weekly postseason plays/stat requests from that unchanged
  denominator.
- Ten explicit registered `data_first_games` captures are the only supplemental
  schedule observations. The capture CLI validates provider, entity, endpoint,
  season type, permitted season, registration state, and schedule identities.
- `build-silver` and `build-team-game` now carry the explicit environment into
  child commands. `build_silver.py` resolves Preview storage and Neon directly
  instead of using an ambient `DATABASE_URL`.
- V4, production, 2020, purchases, model selection, and `.opencode/` remain out
  of scope.

## Work Completed

- Added deterministic supplemental schedule merging with duplicate collapse,
  conflict rejection, season/type validation, and the 2020 guard.
- Added repeatable `--schedule-capture-id` to historical capture planning.
- Added registered CFBD postseason capture-provenance validation.
- Added explicit environment resolution/propagation to Silver and team-game
  execution paths.
- Corrected the Phase 2b execution record and capture runbook.
- Confirmed the Preview dry-run yields 20 requests: postseason plays and
  team-game stats for each of 2015–2019 and 2021–2025.

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase2.py` - schedule merge and capture
  provenance contracts.
- `scripts/research/capture_data_first_phase2.py` - supplemental capture CLI.
- `scripts/pipeline/build_silver.py` - explicit runtime target selection.
- `src/cks_picks_cfb/ops/__main__.py` - environment propagation.
- `tests/test_data_first_phase2.py`, `tests/test_ops_state_machine.py` -
  regression coverage.
- `docs/ops/data_first_capture.md` and the Phase 2 contract - corrected
  operational authority.

## Validation

- [x] Focused suite: 52 passed.
- [x] Full suite: 707 passed, 2 skipped.
- [x] Scoped Ruff format-check and lint.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --quiet`.
- [x] `git diff --check`.
- [x] Read-only Preview dry-run: 20 requests.

## Amendments and Blockers

- Amendment 3 records the incomplete postseason endpoint capture and the
  explicit Preview-routing repair.
- Apply mode intentionally requires `--expected-code-sha` to equal committed
  HEAD. Repository policy leaves the checkpoint commit to the user.

## Handoff Notes

- **Resume at:** After the user commit, rerun the exact 20-request dry-run and
  execute it with a fresh run ID, `--max-requests 20`, bounded retries, and the
  committed full HEAD SHA.
- **Watch out for:** Do not build Silver until all 20 captures are registered;
  use the v3 manifest's exact regular-season captures plus the Phase 2 captures,
  never arbitrary duplicate catalog observations.

**tags:** ["data-first", "phase2", "capture", "silver", "recertification"]
