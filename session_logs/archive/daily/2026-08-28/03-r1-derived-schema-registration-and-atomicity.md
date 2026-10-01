# Session: R1 Derived-Schema Registration and Atomicity

## TL;DR

- **Worked On:** Began the approved remediation for the missing executable R1
  derived-data schemas.
- **Outcome:** Added the missing derived v1 contracts and builder preflight;
  local validation passes and the fresh R1 recapture is next.
- **Plan Contract:**
  `docs/plans/2026-08-28/r1-derived-schema-registration-and-atomicity.md`
- **Approval / Status:** User approved the exact remediation in Codex on
  2026-08-28; contract is `In Progress`.
- **Blockers:** None beyond the identified implementation and subsequent R1
  data-quality gates.
- **Next:** Commit the implementation and start a fresh full-corpus Preview R1
  run.

## Context and Decisions

- The prior R1 run completed all source capture and failed only because the
  catalog could not resolve `byplay/byplay_v1`.
- `drives/drives_v1` and `source_reconciliation/reconciliation_v1` are also
  unregistered and would have failed next; `reconciled_team_game/team_game_v1`
  already has an executable contract.
- Preflight belongs in the team-game builder because changing global lake
  behavior would alter unrelated legacy/research workflows.

## Work Completed

- Created the approved durable implementation contract.
- Added executable schemas for `byplay`, `drives`, and
  `source_reconciliation`; retained the existing reconciled team-game schema.
- Added builder preflight for all derived outputs, moved reconciliation before
  immutable writes, and pre-registers every derived schema before materializing
  the set.
- Added the schema module to the R1 committed-code guard and schema regression
  coverage for valid frames, bad versions/keys, and unsupported classifications.

## Files Modified

- `src/cks_picks_cfb/data/schema_contracts.py` — executable derived schemas.
- `src/cks_picks_cfb/data/silver/contracts.py` — matching Silver contracts.
- `scripts/pipeline/build_team_game_dataset.py` — fail-before-write preflight.
- `src/cks_picks_cfb/ops/__main__.py` — R1 committed-code guard.
- `tests/test_schema_contracts.py` — derived-schema coverage.

## Validation

- [x] Focused schema/reconciliation/ops tests: `46 passed`.
- [x] Full Python suite: `578 passed, 2 skipped`.
- [x] Scoped Ruff.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.
- [ ] Fresh R1 run and deterministic recovery rerun.

## Amendments and Blockers

None.

## Handoff Notes

- **Resume at:** Start the new committed-code full-corpus Preview R1 run.
- **Watch out for:** Preserve v1 names, do not use prior failed source sets,
  and do not begin R2 before `tournaments_permitted: true`.

**tags:** ["r1", "schemas", "catalog", "ratings"]
