# Session: Phase 3 v2 Preflight Count-Gate Investigation

## TL;DR

- **Worked On:** Ran the authorized no-write Preview preflight for the active
  Phase 3 v2 compact-state contract and isolated its only failed certification
  check.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** The user authorized Phase 3 execution. The contract
  remains `In Progress`; no Preview materialization occurred.
- **Outcome:** The compact and tournament headline invariants passed: 6,318
  validation games, 428,880 transient component rows, 142,960 compact feature
  rows, and 202,176 predictions. Certification rejected the run because the
  inherited adjusted-history expectation is 6,777,120 while the replay retained
  3,067,048 rows.
- **Blocker:** The count mismatch changes an explicit sealed acceptance gate.
  Do not change that gate or apply the run without a revised methodology/Phase
  3 contract that either substantiates the higher count or corrects it with
  independent evidence.

## Evidence

The no-write command used run ID `phase3-v2-compact-state-20260910`, Preview
storage, as-of `2026-09-10T00:00:00Z`, and committed code SHA
`d768c41e1a14ae43ad66a43bfbd329a2af58ab24`. It did not include `--apply`.

The direct preflight reached certification and failed only
`expected_replay_counts`. A read-only diagnostic reconstruction reported:

| Dataset | Expected | Actual |
| --- | ---: | ---: |
| Population | 8,936 | 8,936 |
| Observations | 303,790 | 303,790 |
| Pregame snapshots | 1,215,160 | 1,215,160 |
| Adjusted history | 6,777,120 | 3,067,048 |
| Predictions | 202,176 | 202,176 |

The replay intentionally writes adjusted-history records only for
`ADJUSTED_COMPONENTS`, the six measurements whose four-pass adjustment trace is
retained. The higher inherited count was set before a successful end-to-end
Preview preflight and has no supporting completed evidence in the repository.
The compact representation, candidate registry, folds, timing policy, and
tournament mathematics were not changed in this session.

## Validation

- [x] No-write Preview preflight reached its certification gate.
- [x] Read-only count diagnostic reproduced the complete row-count map.
- [x] `uv run pytest -q -W error tests/test_data_first_phase3_v2.py tests/test_data_first_documentation_authority.py` — 21 passed.
- [x] `uv run ruff check scripts/research/run_data_first_phase3_v2.py src/cks_picks_cfb/ratings/phase3_v2.py tests/test_data_first_phase3_v2.py tests/test_data_first_documentation_authority.py`.
- [x] `uv run mkdocs build --strict --quiet`.
- [ ] `git diff --check` — run before the user-controlled documentation checkpoint commit.

## Handoff Notes

- **Resume at:** Create a decision-complete amendment for the adjusted-history
  count gate. It must state the intended retained-history scope and test the
  corrected invariant before another no-write preflight.
- **Watch out for:** This is not authorization to loosen the Phase 3 benchmark.
  The replacement count needs a reproducible derivation and an independent
  verifier check before Preview apply can be considered.

**tags:** ["phase3", "preview", "certification", "counts", "research"]
