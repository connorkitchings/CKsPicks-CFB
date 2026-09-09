# Session: Data-First Repair and Recertification v2 Implementation

## TL;DR

- **Worked On:** Began implementation of the approved Repair v2 contract.
- **Outcome:** Repair v2 code, contracts, tests, and read-only Preview dry run
  are complete; immutable Preview materialization awaits the required clean
  committed checkpoint.
- **Plan Contract:** `docs/plans/2026-09-08/data-first-repair-and-recertification-v2.md`
- **Approval / Status:** User explicitly authorized implementation on 2026-09-09; contract is `In Progress`.
- **Blockers:** None at session start.
- **Next:** User creates the code checkpoint, then run the exact Preview apply
  and independent verifier commands recorded below.

## Context and Decisions

- Preserve the user-owned untracked `.opencode/` directory.
- Keep all work isolated to Preview research artifacts; do not alter V4, production state, web serving, or forecasting/tournament code.

## Work Completed

- Reconciled the approved contract against the current repository state.
- Added isolated Repair v2 normalizers and immutable-data contracts without
  altering Phase 2/3 v1 code or V4.
- Added Preview-only runner and independent verifier with exact pinned-parent
  hashes, dry-run default, output schema validation, and an immutable two-item
  CFBD capture inventory (2014 FBS roster and pre-2015 coach history).
- Added the sealed Repair v2 configuration and focused tests for population
  eligibility, incomplete games, missing measurements, 2020 exclusion,
  recruiting windows, returning-production conflicts, coaching censoring,
  roster transfers, constant-feature admission, and parent identity rejection.
- Ran the sealed-parent Preview dry run with no writes or provider calls. It
  reproduced 8,936 scheduled games, 8,935 forecast-eligible games, 8,903
  measurement-usable games, 33 population omissions, and 5,240 auxiliary rows.
- The dry run generated exactly the approved two planned provider requests,
  each capped at three attempts and under the 200-request repair budget.

## Files Modified

- `docs/plans/2026-09-08/data-first-repair-and-recertification-v2.md` - Marked implementation in progress and linked this log.
- `session_logs/2026-09-09/01-data-first-repair-v2-implementation.md` - Created implementation session log.
- `src/cks_picks_cfb/data/data_first_repair_v2.py` - Repair population,
  auxiliary normalizers, coverage/admission, immutable manifest contracts.
- `scripts/research/run_data_first_repair_v2.py` - Preview-only dry-run/apply
  runner with bounded capture implementation.
- `scripts/research/verify_data_first_repair_v2.py` - Independent artifact
  reconstruction verifier.
- `conf/research/data_first_football_v1/repair_v2.yaml` - Sealed identity,
  capture policy, and semantic fixture configuration.
- `src/cks_picks_cfb/data/schema_contracts.py` - Executable immutable dataset
  schemas for Repair v2 outputs.
- `tests/test_data_first_repair_v2.py` - Focused Repair v2 unit coverage.

## Validation

- [x] Focused Repair v2 + schema tests: `17 passed`.
- [x] Full Python warning-as-error suite: `788 passed, 2 skipped`.
- [x] Repository-wide Ruff format check and lint.
- [x] `make contracts-check`.
- [x] V4/boundary coverage through the full Python suite.
- [x] Strict MkDocs build.
- [x] `git diff --check`.

## Amendments and Blockers

- Preview materialization is intentionally blocked until the tracked Repair v2
  paths are committed at the SHA supplied to `--expected-code-sha`, as required
  by the approved contract. No cloud writes or provider calls were made.
- The first committed-Checkpoint Preview apply (`repair-v2-20260909T1340Z`)
  stopped before any CFBD call or dataset publication: the runner wrote the
  required user-readable capture inventory, then attempted to overwrite that
  immutable object with an internal request representation. The now-fixed
  runner keeps the immutable R2 inventory and uses the catalog header solely
  for resume validation. The partial run contains only identity/capture-plan
  evidence and is intentionally retained as immutable failed-run evidence;
  use a new run ID after the corrective commit.

## Handoff Notes

- **Resume at:** Commit the implementation, then run:

  `PYTHONPATH=src:. uv run python scripts/research/run_data_first_repair_v2.py --core-eligibility-uri artifacts/research/data-first-football-v1/phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/eligibility-manifest.json --auxiliary-eligibility-uri artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json --phase3-retained-uri artifacts/research/data-first-football-v1/phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json --run-id <committed-run-id> --expected-code-sha <committed-sha> --environment preview --as-of 2026-09-09T12:00:00Z --apply`
- **Then:** Run `verify_data_first_repair_v2.py` with the emitted manifest URI
  and the same committed SHA before changing the plan status.
- **Watch out for:** 2020 is forbidden in every outcome, feature, state, and fold; historical capture metadata remains reconstructed-only.

**tags:** ["data-first", "repair-v2", "research", "r2"]
