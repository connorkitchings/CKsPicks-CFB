# Unified 1.0 No-Bet Rule (Lean, Display, Grades)

- **Status:** Implemented (2026-09-26)
- **Created:** 2026-09-26
- **Planner:** Sol (plan-session)
- **Approval source:** User approved scope and execution on 2026-09-26 ("go"): unified 1.0 rule, rebuild history (W0–3 + W4 in one batch), totals 1.0–1.5 lean-only.
- **Parent contracts:** `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md` (Implemented); `docs/plans/2026-09-26/01-v5-bestquote-production-release.md` (Implemented).
- **Implementation log:** `session_logs/2026-09-26/03-unified-no-bet-threshold.md`
- **Commit policy:** Production mutations (new packets, authorizations, publish/score/select) require a fresh release decision gate per the established replay-lane policy. The user executes all git operations. Implementation stops before any production mutation.

## Goal

A sub-1.0-point edge must never display a model side. When the edge is
below 1.0 for either target, the published lean is null (the site shows
"No lean"), the target receives no grade, and the market line keeps its
frozen-quote selection lineage. Totals in [1.0, 1.5) keep their displayed
side but stay ungraded (lean-only zone, unchanged). The already-released
W0–3 best-quote record is rebuilt under the new rule; W4 is rebuilt in the
same batch (unscored).

Observable success criteria:

1. No served row with edge < 1.0 carries a lean, a side label, or a grade —
   on Preview and, after the release gate, in production.
2. Every served line (including sub-1.0 targets) remains a real market tick
   bound to its frozen quote via `prediction_market_selections`.
3. Forecasts are unchanged versus the `-r2` batch; only leans, bet labels,
   and the grade population move.
4. The released W0–3 record loses exactly the 11 sub-1.0 spread grades and
   nothing else; total grades stay at 124.

## Current State

- The site shows a model side whenever the DB lean is non-null; leans are
  derived arithmetically in `prepare_predictions`, ignoring the artifact's
  "No Bet" labels. Result on production: 32 sub-1.5 totals show a side with
  no result, and 11 graded spreads have edge < 1.0 (0/4/5/2 across W0–3).
- The standard scorer reads bet labels first but falls back to the lean, so
  labels alone never suppress grades; only the rehearsed threshold-aware
  scorer enforces the basis. Making the lean label-honest fixes display,
  the standard scorer, and the rehearsal scorer at once.
- Configs carry `spread_edge_threshold: 0.0` / `total_edge_threshold: 1.5`,
  both feeding bet labels. V4 lineage (`v4_2026.yaml` and all V4 runs) is
  frozen and untouched by this plan.

## Design

| Concept | Spread | Total |
|---|---|---|
| Lean/label threshold | 1.0 (`spread_edge_threshold` 0.0→1.0) | 1.0 (new `total_lean_threshold`) |
| Grade threshold | 1.0 (lean presence) | 1.5 (`total_edge_threshold`, unchanged) |
| Below lean threshold | lean null, no grade, selection kept | same |
| [1.0, 1.5) totals | n/a | lean shown, no grade (unchanged) |

- Generation: `total_lean_threshold` (defaulting to `total_edge_threshold`
  when absent) feeds the label threshold in the V5 producers; V4 producers
  behave identically to today.
- Publish: `prepare_predictions` maps `Spread Bet`/`Total Bet` labels to
  leans (`No Bet`→null); arithmetic derivation remains as fallback when
  label columns are absent.
- Scoring: no logic change — label-honest leans make the standard scorer,
  the rehearsal scorer, and the production driver agree.
- Verification: selections counted versus lined rows (line non-null), not
  lean-non-null, since sub-1.0 targets keep quote lineage.

## Implementation Tasks

### Task 1 — Configs and label-threshold plumbing

**Files:** `conf/weekly_bets/v5_replay_2026.yaml`,
`conf/weekly_bets/v5_replay_w4_2026.yaml`,
`scripts/pipeline/generate_v5_weekly_bets.py`,
`scripts/pipeline/generate_v5_replay_weekly_bets.py`,
`scripts/pipeline/generate_weekly_bets.py`,
`src/cks_picks_cfb/inference/v5_serving.py`, focused tests.

**Changes:** set `spread_edge_threshold: 1.0` and add
`total_lean_threshold: 1.0` in the two V5 replay configs; read
`total_lean_threshold` with fallback to `total_edge_threshold` in the
producers and pass it as the label threshold; `weekly.py` unchanged.

**Validation:** unit tests for fallback + label thresholds at 1.0/1.5
boundaries.

### Task 2 — Publish leans honor bet labels

**Files:** `scripts/pipeline/publish_to_db.py`, `tests/test_publish_to_db.py`.

**Changes:** in `prepare_predictions`, derive each lean from its bet-label
column when present (`Home/Away/Over/Under` → side, `No Bet`/other →
null); keep arithmetic derivation as fallback. Edges still derived
arithmetically.

**Validation:** new tests (No-Bet→null both targets, label-present mapping,
label-absent fallback); existing CSV-fixture tests keep passing.

### Task 3 — Rehearsal verification updates

**Files:** `scripts/pipeline/rehearse_v5_bestquote_replay_preview.py`.

**Changes:** `verify_selections` counts selections versus lined rows;
grade expectations follow the configs (spreads ≥ 1.0 via lean, totals ≥
1.5). Dry-run all five weeks to confirm label populations.

### Task 4 — Preview rebuild, verify, serve, roll back

New run IDs; publish/score/select W0–3 + publish/select W4 on Preview;
full verification (forecasts identical to `-r2`; spread grades −11;
totals graded unchanged; all served lines real ticks; stats guard;
idempotency); serving selection with rendered-line check; restore current
Preview selections.

### Task 5 — Production packets and release gate (stops at the gate)

Regenerate `prepare`/`packet` outputs for the new batch with the
production driver, run all five replay-packet validations, present the
precondition readback. **No authorization, publish, score, or selection
before a fresh explicit release decision.**

### Task 6 — Docs

`docs/modeling/betting_policy.md` (unified 1.0 + lean-only zone),
`docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`,
`docs/modeling/v5_status.md`, parent-plan amendment, this contract's DoD,
session logs. Coordination note: the future Week 5 live weekly config must
carry `spread_edge_threshold: 1.0` + `total_lean_threshold: 1.0`.

## Testing Strategy

Focused pytest for label mapping/fallback, threshold plumbing, packet
builder (existing), plus the full suite, ruff, `make contracts-check`,
web lint/typecheck/build/tests, strict MkDocs, `git diff --check`. No
schema migration (lean columns already nullable).

## Risks and Edge Cases

- The 11 dropped spread grades are a deliberate, authorized record change;
  the rebuild batch gets new run IDs, packets, and authorizations — never
  an edit of the `-r2` rows.
- Legacy artifacts without label columns publish exactly as today
  (fallback); no legacy run is re-published (immutability).
- V4 configs and runs are untouched; a future V4 publish would follow V4
  labels, which is out of scope and unplanned.
- Totals in [1.0, 1.5) keep showing a side with no result — the explicitly
  approved lean-only zone, not a defect.
- Week 5 live lane coordination: thresholds must be carried into its weekly
  config when created.

## Definition of Done

- [x] Configs + plumbing + publish label-honoring implemented and tested.
- [x] Preview rebuild batch verified (forecasts identical; −11 spread grades;
      totals graded unchanged; all lines real ticks).
- [x] Production packets built and validated; release decision pending.
- [x] Docs updated; no production mutation performed in this contract.

## Release record (user-authorized 2026-09-26, same decision ref)

- Five `-r3` authorizations inserted (IDs
  `v5-bestquote-2026w{0..4}-{00632b2e,469d2df8,3cd45db9,e9481c48,4f1e8436}`);
  W0–3 published/scored/selected with 270 grades (15/76/82/97; 146 spread +
  124 total); W4 published/selected 58/58, unscored (0 certified finals).
- Production readback: all five weeks on the `-r3` runs; health `ok` with
  the W4 replacement active; V4, original, and `-r2` runs untouched with
  original grade counts. Rollback = single recorded selection per week.
