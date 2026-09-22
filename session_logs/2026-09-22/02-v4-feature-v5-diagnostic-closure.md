# Session: V5-01 V4 Feature-v5 Diagnostic Closure (Terra)

## TL;DR
- **Worked On:** Terra execution of `docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md` — closed Task 5 of the 2026-09-10 shadow rebuild diagnostic by scoring `shadow-2026-v5-w2` against the Week 2 close outcomes and rendering the pooled verdict.
- **Outcome:** Contract 01 **Implemented**. Verdict: pooled W1+W2 shadow spread **35-56-1 on 91 graded (38.46%) < 45% → cause not confirmed**; shadow predictions are **value-identical to official on all 100/100 W0–W2 games** (drift 0.0), refuting the v4/v5 feature mismatch as the cause of the 2026 V4 spread underperformance. W2 scored artifact uploaded (idempotent rerun verified); zero DB/serving writes (guards identical before/after in both databases).
- **Plan Contract:** `docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md` (Status: Implemented)
- **Approval / Status:** User authorized execution 2026-09-22 ("Use the repository-local implement-plan skill and implement the approved contract…"). All DoD items pass.
- **Blockers:** None.
- **Next:** Terra for `docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md` (Contract 12 acceptance + 07–09 re-review).

## Context and Decisions
- Resumed the original contract with Amendments 1–3 and pinned cutoffs preserved; no artifact regenerated — all inputs reused from immutable R2.
- Week 2 finals ref recovered from close pipeline run `cb75ca881f3a49d5bd115c4fdeaa7dcb` (`game_outcomes@e35fc53701a235148f0bd306`); 49/49 coverage verified pre-scoring (also enforced fail-closed by the scorer). W0/W1 outcome refs resolved to full run IDs `8d2e78ab92634bd0abfa76f9f169cb6f` / `edb91b1594534ff987793f0e2657dc03` from the 6-hex prefixes in log 11.
- W2 shadow manifest verified before scoring: as-of `2026-09-08T17:50:00Z` (pre-kickoff, Fri 2026-09-11 23:30 UTC), artifact SHA `c66240a3…`, parents = games `5dabf61a`, market snapshot `459c80d0`, quotes `ede4a9a7`, v5 matchups `4d89b391`, bundle `week0-2026-v4-strict-20260818-r2` (`72429375…`), state `preview`.
- Grading-convention note (per contract): the artifact scorer grades all spreads directionally; totals carry explicit `No Bet` below the edge threshold (W1: 2, W2: 8). Win rate = W/(W+L); pushes/No-Bets excluded. No discrepancy against the original threshold convention was discovered, so no amendment was required. The official W1 close graded the 2 sub-threshold totals directionally (14-29 vs 13-28+2 NB) — a convention difference recorded in log 11 and reported, not silently reconciled.
- Observed in passing: production `current_week` now (2026, 4, `2026w4-da5d98761831`) — Week 3 was closed and Week 4 published after 2026-09-13. Relevant to the 2026-09-22 launch plan's ops phase; no action taken here.

## Work Completed
- Task 1 — refs reconciled (read-only): W2 shadow artifact + manifest cutoff verified; W0/W1 scored artifacts present (8/43); outcomes refs resolved and coverage verified (8/8, 43/43, 49/49; no duplicates).
- Regression guards captured before/after in both databases — identical: prod 52/2492/4657 with current_week (2026, 4, `2026w4-da5d98761831`); preview 19/821/1524 with (2025, 16, `v4replay-2025-w16`).
- Task 2 — scored `shadow-2026-v5-w2` via the artifact-only scorer path with `--upload-artifact`; rerun idempotent (no collision); scored artifact at `artifacts/preview/scored/year=2026/week=2/run_id=shadow-2026-v5-w2/scored.csv` (+ signed manifest).
- Independent paired analysis from raw artifacts (no scorer import): prediction identity (drift 0.0 on 100/100 games, bets/lines equal), per-week + pooled counts/metrics reproducing all three scorer artifacts exactly, official production grades pulled read-only for comparison.
- Task 3 — closure: research report `docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md`; original diagnostic contract marked Implemented (blocker note resolved, DoD checked); Contract 01 marked Implemented with closure record; `docs/plans/index.md` + roadmap updated.

## Results (key tables)
| Week | n | Spread W-L-P (graded) | Win rate | Total W-L-P (graded/NB) | Win rate |
| --- | --- | --- | --- | --- | --- |
| 0 | 8 | 2-6-0 (8) | 25.0% | 5-3-0 (8/0) | 62.5% |
| 1 | 43 | 16-26-1 (42) | 38.1% | 13-28-0 (41/2) | 31.7% |
| 2 | 49 | 19-30-0 (49) | 38.8% | 21-20-0 (41/8) | 51.2% |
| Pooled W1+2 | 92 | 35-56-1 (91) | **38.46%** | 34-48-0 (82/10) | 41.5% |

MAE/bias (pooled W1+2): spread 19.09/−2.38, total 15.70/−0.56. Threshold: 38.46% < 45% → **cause not confirmed**; causal interpretation — value-identical predictions refute the mismatch hypothesis; open hypotheses (season effect/mean reversion, early-season regime weakness [W1 spread bias −5.42], market environment, sample variance) reported evidence-bounded.

## Files Modified
- `docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md` — created (closure record)
- `docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md` — Implemented + closure record
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` — Implemented; blocker resolved; DoD checked
- `docs/plans/index.md` — contract 01 row + 2026-09-10 diagnostic entry
- `docs/planning/data-first-football-forecasting-roadmap.md` — contract 01 row + dated record
- `session_logs/2026-09-22/02-v4-feature-v5-diagnostic-closure.md` — this log
- New R2 artifact (Preview): `artifacts/preview/scored/year=2026/week=2/run_id=shadow-2026-v5-w2/scored.csv` + manifest (idempotent)

## Validation
- [x] Refs/SHAs/cutoff audit; 49/49 W2 outcome coverage pre-verified
- [x] Scoring idempotent (rerun byte-identical, immutable-collision path exercised)
- [x] Independent recomputation reproduces all three scorer artifacts exactly
- [x] Serving-state guards identical before/after (both databases)
- [x] `uv run pytest tests/test_data_first_documentation_authority.py` (38 passed)
- [x] `uv run python contracts/validation.py`
- [x] `uv run mkdocs build --strict --quiet`
- [x] `git diff --check`

## Amendments and Blockers
- None. No denominator or convention discrepancy discovered; production untouched.

## Handoff Notes
- **Resume at:** Terra for `docs/plans/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md`.
- **Watch out for:** prod is already at Week 4 (`2026w4-da5d98761831`) — verify Week 3 close + Week 4 prepare/publish state before assuming the 07 entry gate is still pending. This diagnostic is closed; do not reopen shadow predictions or treat its results as V5 prospective evidence.

**tags:** ["v5-01", "v4-feature-v5", "diagnostic-closure", "scoring", "verified"]
