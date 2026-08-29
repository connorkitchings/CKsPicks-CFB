# R1 Cross-Lineage Audit Scope Remediation

- **Status:** Approved (user directed continuous execution on 2026-08-28:
  "keep rolling")
- **Created:** 2026-08-28
- **Planner:** Sol (inline, mid-execution of
  `docs/plans/2026-08-28/r1-derived-schema-registration-and-atomicity.md`)
- **Implementation log:**
  `session_logs/2026-08-28/04-r1-cross-lineage-audit-scope-remediation.md`
- **Commit policy:** Separate plan and implementation commits; user executes
  Git operations.

## Goal

Correct the `compare_season` cross-lineage gate so it compares successor-v2 R1
evidence against legacy evidence over each dataset's own scope, then complete
the fresh full-corpus Preview R1 run through certification.

## Current State

Run `r1-full-corpus-20260828-962f85d` (as_of `2026-08-28T17:00:15Z`) completed
every capture, Silver season, reconciled team-game step, and derived ref-set
closure, then failed at `audit_successor_cross_lineage` with two findings:

1. `season_membership_ok` was `False` for every comparison season because the
   check required `games` and `game_outcomes` to have identical game-ID sets.
   They never do, by Silver design: `games` keeps both-teams-FBS rows only
   (`silver/builders.py` FBS classification filter) while `game_outcomes`
   retains all captured games (~114–126 additional non-FBS-scope rows per
   season). The immutable legacy comparison evidence has the identical shape
   (e.g. 2019: 734 games vs 848 outcomes on both lineages).
2. `_scores()` raised on 2024 because game `401640992` (App State vs Liberty,
   2024-09-28, canceled) carries null scores with `completed=False` in the
   successor data and — byte-for-byte the same row — in the legacy evidence.

Successor and legacy already agree exactly on games membership, game
identities, teams, and every scored game. No successor data defect exists.
The audit had never previously executed against real evidence (all earlier
runs stopped before derived refs) and its unit fixtures were degenerate
(single game, `games ≡ outcomes`), so the mis-specification was unreachable
until now.

## Proposed Approach

Keep the audit fail-closed and keep its report contract
(`successor-cross-lineage-audit-v2`, same four check names) unchanged, but
make each comparison scope-correct:

- `season_membership_ok`: successor `games` IDs equal legacy `games` IDs AND
  successor `game_outcomes` IDs equal legacy `game_outcomes` IDs. No
  cross-dataset equality demand between `games` and `game_outcomes`.
- `scores_ok`: scored games (non-null home/away points) equal between
  lineages AND the uncompleted (null-score) game-ID sets equal between
  lineages.
- A null score on a `completed=True` row remains a hard error; duplicate
  game IDs remain a hard error; `game_identity_ok` and `team_identity_ok`
  are unchanged.

This tightens successor-vs-legacy equivalence coverage (incomplete-game sets
are now compared) while removing only the two impossible demands.

## Scope

### Included

- `src/cks_picks_cfb/ratings/cross_lineage.py` semantics fix.
- `tests/ratings/test_cross_lineage.py` coverage for canceled-game symmetry,
  outcomes-superset membership, asymmetric incomplete sets, and
  completed-with-null-score rejection.
- This plan, session log, plan-index update, and governing-contract
  amendment.
- A fresh code-bound full-corpus Preview R1 run through certification and its
  identical-invocation recovery rerun.

### Excluded

- Any change to Silver builders, capture data, coverage thresholds,
  certification logic, production/V4/candidate-v1 behavior, 2020, and 2026
  outcomes. Failed prior runs remain immutable diagnostics and are never
  parents.

## Evidence

- Read-only probes (2026-08-28) against
  `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260828-962f85d/`:
  corrected semantics pass all six comparison seasons
  (`2019/2021/2022/2023/2025`: no incomplete games; `2024`: exactly
  `{401640992}` incomplete on both lineages).

## Implementation Tasks

### Task 1 — Scope-correct `compare_season`

**Files:** `src/cks_picks_cfb/ratings/cross_lineage.py`

- Split `_scores()` into scored mapping plus incomplete-ID set; hard-fail on
  duplicates and on null scores for completed games.
- Redefine `season_membership_ok` and `scores_ok` per above; keep other
  checks and all error messages fail-closed.

### Task 2 — Regression coverage

**Files:** `tests/ratings/test_cross_lineage.py`

- Equal evidence with an outcomes superset and one shared canceled game
  passes; divergent canceled-game sets fail `scores_ok`; membership diff in
  either dataset fails `season_membership_ok`; completed-with-null-score
  raises.

### Task 3 — Validate, commit, fresh run

- Focused + full Python suite, scoped Ruff, `make contracts-check`, strict
  MkDocs, `git diff --check`.
- Commit, then launch `r1-full-corpus-20260828-<short SHA>` with a fresh
  as_of (~5 minutes ahead), full recapture (no `--skip-capture`, no parent
  reuse), through certification; rerun the identical invocation for
  deterministic recovery.

## Risks and Edge Cases

- The prior run's completed steps cannot be reused (code-bound identity);
  recapture is ~40 minutes and re-fetches from CFBD within existing rate
  policy.
- Any post-fix failure at PPSO, terminal-team, or coverage gates is an
  intentional stop condition requiring a new contract.

## Definition of Done

- [ ] Remediation implemented and tested; all validation gates pass.
- [ ] Fresh R1 run reaches certification; identical rerun verifies
  deterministic recovery, or a terminal diagnostic publishes immutably.
- [ ] Session log, plan index, and governing-contract amendments recorded.
- [ ] R2 is handed off only after `tournaments_permitted: true`.

## Amendments

1. **2026-08-28 (fresh run execution).** Run `r1-full-corpus-20260828-2cb4d5a`
   completed captures (with two sanctioned same-ID resumes after a transient
   Neon connection timeout and a CFBD 502 outage), all Silver seasons, derived
   ref-set closure, and — for the first time — a passing
   `audit_successor_cross_lineage` (`all_checks_passed: true`). It then
   exposed a second never-executed path: `build_successor_r1_foundation` and
   `certify_successor_history` both parsed derived-ref-set entries with
   `DatasetRef(**entry)`, which crashes on the entries' required `season`
   scope field (`TypeError: unexpected keyword argument 'season'`). Fixed by
   a shared scope-aware parser `derived_history_dataset_refs()` in
   `src/cks_picks_cfb/ratings/successor_history.py` used by both scripts,
   with round-trip regression coverage; verified read-only against the real
   100-entry ref set. A fresh code-bound run is required for the same
   one-run-one-identity reason as before.
