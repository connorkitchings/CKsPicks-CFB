# Historical Expansion and Ratings Methodology Reset

- **Status:** In Progress
- **Created:** 2026-08-26
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact
  plan in Codex on 2026-08-26.
- **Implementation log:**
  `session_logs/2026-08-26/10-historical-expansion-ratings-methodology-reset.md`
- **Commit policy:** Separate plan commit required before implementation.

## Goal

Expand historical football evidence to 2015–2019 and 2021–2025, then select a
replacement rating/prediction methodology without using 2026 outcomes. Keep V4
unchanged in production and retain candidate v1 only as a diagnostic baseline.

Observable success means a fully immutable Preview-only historical corpus and
an attributable, leakage-safe tournament that either freezes candidate v2 or
publishes a failed-selection report while leaving candidate v1 and V4 intact.

## Current State

Candidate v1 uses a deliberately simple `rho=0.60` season carryover and
2021–2025 historical development. Its preseason rankings exposed a legitimate
need to investigate year-to-year transition quality. Candidate v1 is frozen at
`ac1fba1` for diagnostic-only prospective operation; it cannot be tuned.

Existing durable history contains 2019 and 2021–2025. A read-only CFBD probe
confirmed compatible 2015 play data. The shared R2 bucket is intentional:
immutable artifact namespaces and distinct Neon branches provide environment
separation. Week 0 2026 outcomes remain unavailable and may not affect this
work. 2020 remains globally forbidden.

## Proposed Approach

Use two explicit tracks:

- **Research:** R1 historical expansion and lineage certification; R2
  between-season priors; R3 within-season state updates; R4 structured
  prediction and candidate-v2 freeze.
- **Operations:** O1 unchanged V4 production; O2 candidate-v1 diagnostic
  evidence from the isolated `ac1fba1` worktree; O3 candidate-v2 protected
  evidence and, later, promotion review.

Every research artifact uses a successor-v2 prefix. Completed Phase 1–4 plans
remain immutable history. Phase 5 is amended into the O2 diagnostic lane and
cannot block R1–R4.

## Scope

### Included

- Historical football data and lineage for 2015–2019, 2021–2025.
- Football-only, point-in-time-admissible offseason context.
- Sealed temporal tournaments for priors, updates, and structured predictions.
- Documentation, contracts, audits, tests, and candidate-v2 evidence setup.

### Excluded

- 2020 inputs, labels, priors, folds, or artifacts.
- V4 bundle, production prediction, Neon activation, publication, and rollback
  changes.
- Market data as a rating or football-prediction feature.
- Any retrospective or backdated 2026 candidate-v2 freeze.

## Affected Interfaces and Contracts

- A versioned season-lineage policy with historical seasons
  `[2015..2019, 2021..2025]`, protected season `[2026]`, and forbidden season
  `[2020]`.
- A resumable Preview-only `prepare-rating-history` operation emitting an
  immutable expanded-history ref set and season coverage report.
- Versioned preseason-context eligibility, prior-tournament, update-tournament,
  predictor-tournament, and candidate-v2-manifest contracts.
- New successor-v2 configurations and artifact prefixes. Existing candidate-v1
  and V4 interfaces remain byte-for-byte compatible.

## Implementation Tasks

### Task 1 — Reset governance and active documentation

**Changes:**

- Add this roadmap and a planning log in a separate commit before code work.
- Amend the active roadmap, plans index, rating requirements, evaluation,
  measurement catalog, early-season documentation, AGENTS, context, README,
  and runbooks to distinguish research R1–R4 from operations O1–O3.
- Amend Phase 5 as the candidate-v1 diagnostic lane; correct the Week 1 session
  log to state that shared R2 is intended and Week 0 source availability was
  the actual stop condition.

**Acceptance criteria:** V4 remains the production champion; the active
authority consistently names expanded history, universal 2020 exclusion,
football-only inputs, candidate-v1 diagnostic status, and candidate-v2's fresh
prospective lane.

### Task 2 — Build the expanded-history foundation

**Changes:**

- Add one centralized season policy. 2015 is an within-season and terminal
  seed; normal offseason transitions are 2015→2016, 2016→2017, 2017→2018,
  2018→2019, and 2021→2022 through 2024→2025. Apply the selected annual decay
  operator twice for 2019→2021, but never fit normal transition parameters on
  that gap.
- Implement resumable Preview-only capture of 2015–2018 games, plays,
  game statistics, teams, and venues; import the existing 2019 archive; reuse
  immutable 2021–2025 refs.
- Materialize a checksummed ref set, per-season coverage report, and rebuilt
  true-PPSO measurement, reconciliation, terminal-state, and pregame-state
  artifacts under successor-v2 identities.
- Collect returning production, transfers, recruiting, coaching, and talent in
  an isolated research context layer. Admit a family only when it is
  semantically preseason, leakage-safe, at least 90% FBS-covered in every
  required fold, and authentically captured for 2026; otherwise mark it
  diagnostic-only.

**Acceptance criteria:** All eligible seasons meet at least 90% completed-game
play coverage, 94% score-stream reconciliation, representative terminal-team
coverage, stable schemas, and zero 2020 lineage. Stop before tournaments if
fewer than three of 2015–2019 are eligible.

### Task 3 — Run the sealed between-season prior tournament (R2)

**Changes:**

- Compare neutral, fixed `rho=0.60`, learned offense/defense carryover,
  partially pooled component carryover, multiyear EWMA half-lives `{1,2,3}`,
  and continuity Ridge residuals with alpha `{0.1,1,10,100}` only when the
  context family is admitted.
- Use expanding target-season folds `2018, 2019, 2022, 2023, 2024`; reserve
  2025 for a single locked confirmation. Report 2021 as a two-year-gap stress
  test only.
- Select on Games 1–3 state forecast/downstream margin-total quality, require
  each full-season MAE within 1% of fixed-rho, and choose the simpler candidate
  within a 0.5% performance tie.

### Task 4 — Run sealed within-season update and predictor tournaments (R3/R4)

**Changes:**

- Lock R2 before comparing fixed updates, exposure multipliers `{0.5,1,2,4}`,
  recency half-lives `{2,4,8}`, Gaussian process SD
  `{0.025,0.05,0.10,0.20}`, and robust innovation caps `{2,3}` on folds
  `2017, 2018, 2019, 2021, 2022, 2023, 2024`, with 2025 locked.
- Lock R3 before comparing current NB2, Gaussian linear team scores, direct
  bivariate margin/total, Ridge residual, and shallow CatBoost residual using
  the existing V4 grid. Residuals are cross-fitted and use only states,
  uncertainty, pace, venue/weather, completed games, and admitted football
  context; teams may not be categorical memorization.
- Use full football outcomes across all folds and paired V4 evaluation where
  available (2022–2024). Require existing finite/bias/calibration/interval and
  lineage gates; candidate v2 additionally needs a 2,000-sample seed-42 paired
  bootstrap upper bound below zero for combined Games 1–3 MAE versus v1, no
  individual full-season regression above 1%, and a passing locked 2025 result.

**Acceptance criteria:** freeze a complete candidate-v2 identity only after all
gates pass; otherwise publish a failed-tournament report without weakened
criteria. Every tournament emits uncertainty, component states, top/bottom
rankings, movement, and attribution diagnostics; rankings are descriptive, not
manual tuning gates.

### Task 5 — Establish prospective lanes and preserve production

**Changes:**

- Preserve candidate-v1 reproducibility in an isolated `ac1fba1` worktree and
  treat any v1 evidence as diagnostic only.
- Create a new policy and six-slate counter for candidate v2. Its first
  eligible slate is the first one frozen after committed implementation; never
  transfer candidate-v1 evidence or backdate a v2 freeze.
- Retain V4 as the unchanged production comparison and rollback authority.

## Testing Strategy

- Unit-test season policy, 2015 seed, compounded 2019→2021 decay, 2020
  rejection, folds, context admission, market exclusion, uncertainty, ties,
  fallback, and locked-season enforcement.
- Integration-test resumable capture/import through Bronze, Silver, byplay,
  drives, reconciliation, successor-v2 states, all three tournaments, immutable
  collisions, and byte-identical retries.
- Re-run ratings, lake, ops, V4, production-write-boundary, contracts, and web
  regressions. Require full pytest/coverage, scoped Ruff, contract sync, strict
  MkDocs, CLI smoke tests, and `git diff --check`.

## Risks and Stop Conditions

- Historical backfills are reconstructed research evidence and must never claim
  authentic historical capture time.
- Any context source that can contain end-of-season knowledge is
  diagnostic-only until semantic/effective-time admission passes.
- If the data gate or a locked gate fails, retain immutable diagnostics and
  stop rather than narrow seasons or relax thresholds silently.
- Missing Week 1 candidate-v2 is acceptable; calendar pressure never permits a
  weaker or retrospective freeze.

## Definition of Done

- [ ] Governance and active documentation are aligned and the prior R2 claim is corrected.
- [ ] Expanded history passes lineage and coverage certification.
- [ ] R2, R3, and R4 publish immutable selected or failed reports.
- [ ] Candidate v2 either freezes under all gates or an explicit failed report exists.
- [ ] Candidate v1/V4 compatibility and production isolation regressions pass.
- [ ] Required validation passes; the implementation log is complete.
- [ ] Plan status is updated to `Implemented`.

## Amendments

### Amendment 1 — R1 play-capture reliability hardening (2026-08-27)

**Reason:** The first Preview 2015 CFBD play captures proved that the original
all-or-nothing seasonal process cannot make durable progress after a stalled
weekly response and can leave catalog runs in `running` after child termination.

**Revised approach:**
`docs/plans/2026-08-27/r1-play-capture-reliability-hardening.md` supersedes
only Task 2's 2015–2018 play-capture mechanics. It uses a same-set resumable,
weekly request ledger and complete-manifest-only downstream contract.

**Impact:** R1 certification, R2–R4, V4, candidate-v1, production, season
policy, selection gates, and prospective evidence policy are unchanged. R1
remains blocked until the amendment is implemented and validates a complete
capture set.
