# Possession-Based Rating Methodology Specification

- **Status:** Approved
- **Created:** 2026-09-11
- **Planner:** Sol
- **Approval source:** User selected the four contested decisions on 2026-09-11
  (compete both rating definitions; carry the full Phase 4A v2 prior/updater
  grid; volume proxy now; accepted the overtime and non-offense-scoring
  defaults) and approved the complete contract in the same planning session.
- **Planning log:** `session_logs/2026-09-11/05-possession-rating-methodology-planning.md`
- **Implementation log:** Pending
- **Commit policy:** Commit with implementation (contained documentation work).

## Goal

Settle every open methodology decision for the possession-based rating system
(step 3 of the approved handoff queue in
`docs/plans/2026-09-10/documentation-alignment-and-next-research-steps.md`) and
persist it as decision-complete semantic authority, so the four replacement
execution contracts — possession measurement certification, rating estimation,
score forecasting, and prospective evaluation — can be authored without new
modeling decisions.

Success is observable when: every decision area below is specified; the
specification is persisted under `docs/modeling/`; the authority documents and
tests are consistent; and no estimator, measurement, or data code has changed.

## Current State

- Phase 3 v2 is certified Preview evidence (2026-09-11, run
  `phase3-v2-compact-state-20260910-r2`, selection `quality_core_epa_split`).
  Its selected core is benchmark evidence for this design, not a definition of
  it.
- Certified reusable machinery: true-drive-points score-stream reconstruction
  with validity gates (`src/cks_picks_cfb/ratings/observations.py:70-218`);
  four-pass league-centered additive opponent adjustment; preceding-season
  team-equal z-standardization with frozen floors (`src/cks_picks_cfb/ratings/states.py:31-61`);
  fixed-ρ 0.60 carryover with two-step 2019→2021 decay (`states.py:257-261`);
  precision-weighted credibility `n/(n+k)` (`states.py:64-89`); recency
  half-life weighting (`ratings/phase3.py:402-416`); FCS partial-pool fallback
  (`ratings/phase4a.py:317-337`).
- Known data gaps this spec must respect: no possession-count measurement
  exists; clock/tempo fields survive only in raw/Silver plays (byplay dropped
  them); overtime appears only as `quarter >= 5` and is currently included in
  every measurement; defensive and special-teams scores are identifiable
  play-by-play but attributed to no unit; the drives dataset
  `points`/`points_on_opps` columns are Boolean-sum-defective and unusable.
- The execution-held Phase 4A v2 contract
  (`docs/plans/2026-09-08/phase4a-prior-and-dynamic-rating-selection-v2.md`)
  specifies a 6-prior × 5-updater grid (including one local-level Kalman
  challenger) that has never been executed; no Kalman code exists anywhere.
- Prior-feature defects found by the 2026-09-08 review (constant coaching
  features, cross-team roster continuity, ~30% recruiting missingness) are
  repaired by design inside that held contract. The fresh Preview admission
  (`early-week-context-20260904-786580ec-r2`) admits returning production,
  recruiting, and coaching as reconstructed evidence only; transfers and
  talent remain rejected.

## Methodology Decisions

Each decision below is final for the first generation. Amendments require the
contract amendment process.

### D1 — Rating quantity: two competing definitions

The offense and defense ratings estimate **expected scoring efficiency per
possession against an average opponent under standard conditions**. Two
definitions compete; the rating-estimation tournament's gates decide.

- **Definition A — true points per possession (PPP).** Offense: true drive
  points (certified score-stream reconstruction) summed over eligible offensive
  possessions, divided by that possession count. Defense: the same points
  attributed to the defending team, divided by eligible possessions defended.
- **Definition B — EPA per possession.** Offense: sum of eligible-play PPA
  over eligible offensive possessions, divided by that possession count.
  Defense: same for possessions defended.

Both are per team-game measurements with possession exposure. Passing,
rushing, explosiveness, finishing (PPSO), field position, pace, and turnover
measurements remain supporting diagnostics that explain ratings; they are not
rating states in the first generation.

### D2 — Possession eligibility

A possession is a drive with at least one eligible scrimmage play. Eligible
play = `st == 0`, `penalty == 0`, `twopoint == 0`, play type not a dead-ball
marker, and `garbage == 0` (the existing eligibility in
`ratings/observations.py`). Kickoff-only and special-teams-only drives are
excluded from both numerator and denominator (zero eligible plays). One-play
drives are included. Because clock is not modeled, no clock-ending special
case exists in v1. The same possession set denominates both definitions and
the volume layer.

### D3 — Scoring attribution

Offensive possessions carry their true drive points to the possessing offense
and the defending defense. Defensive touchdowns, kick/punt/field-goal return
touchdowns, and defensive two-point conversions are excluded from unit
ratings (they occur outside eligible offensive possessions; the score-stream
reconstruction already excludes them). They feed a separate **non-offense
scoring translation state**: per-team points scored and allowed off
non-offensive plays, per game, accumulated with game-exposure shrinkage toward
league mean (provisional equivalent prior exposure: 4 games). This state is
part of the translation layer only — it is explicitly not a third rating.

### D4 — Overtime

Overtime drives are excluded from rating evidence and efficiency exposure
(non-standard conditions: fixed starting field position, alternating
possession rules). Overtime points remain in game targets (full-game margin
and total) exactly as played.

### D5 — Field-position normalization

None in v1. `average_start_field_position` remains a certified context-only,
unadjusted measurement that translation-layer challengers may consume; the
primary closed-form translation may not. "Standard conditions" is interpreted
as: opponent-adjusted through D6, with no starting-field-position
conditioning. Field-position-normalized efficiency is a documented future
challenger.

### D6 — Opponent adjustment

The certified iterative additive league-centered four-pass adjustment
(iterations 0 and 4 retained) is applied to per-game possession measurements
(both definitions, both roles) exactly as it is to the six existing adjusted
components. No schedule-strength adjustment occurs at the rating layer; this
prevents double-counting per the approved architecture.

### D7 — Rating scale and standardization

Per definition × role: preceding-season team-equal standardization (prior
season terminal snapshot pooled mean and standard deviation with frozen floors
and fallbacks, existing mechanism) produces z-space states; defense z is
reversed so higher is better. Native adjusted values (points per possession or
expected points per possession) are carried alongside for interpretability and
for the closed-form translation. Provisional floors/fallbacks are listed in
the constants table and must be frozen by the measurement-certification
contract from 2015–2019 representative pooled standard deviations.

### D8 — Preseason priors: full Phase 4A v2 grid carried forward

The held Phase 4A v2 prior grid is reaffirmed and carried onto both possession
rating definitions: (1) neutral; (2) fixed ρ = 0.60 carryover with `d = 2` for
the 2019→2021 gap; (3–6) carryover plus Ridge residual prior on the recruiting
block, the returning-production block, the repaired continuity block, and all
three combined. The learned label is
`terminal_possession_rating(S) − carryover_mean(S)` built strictly before
season S. Ridge alpha selection `{0.1, 1, 10, 100}` by inner validation with
the 0.5% simplicity preference, fallback rules, and held-out-residual prior
variance all follow the held contract unchanged. Only repaired feature blocks
are eligible (constant columns removed and logged; same-team continuity;
censored tenure lower bound with censor flag; new-coach flag), restricted to
Preview-admitted reconstructed evidence (returning production, recruiting,
coaching). Transfers and talent data remain rejected.

### D9 — State updates: five updaters

1. Exposure analytic posterior (the reference): credibility `n/(n+k)` with
   possession-denominated equivalent prior exposure (provisional k in the
   constants table).
2–4. Recency half-life {2, 4, 8} games: half-life weights applied to numerator
   and denominator; weighted denominator becomes effective exposure in the
   same posterior.
5. Local-level Kalman challenger (net-new code): one scalar observation per
   team/role/game equal to that game's adjusted z; observation information is
   that game's eligible possession count (`R = r / n`); process variance grows
   with elapsed days (`P⁻ = P + q·Δ/7`); `K = P⁻/(P⁻+R)`;
   `m⁺ = m + K(z−m)`; `P⁺ = (1−K)P⁻`; preseason mean/variance initialization
   at first kickoff; byes grow variance; q and r fitted per role × prior
   family on preceding-season innovation Gaussian NLL via deterministic
   L-BFGS-B with the held contract's bounds and rejection rules. No
   adaptive-volatility mechanism.

### D10 — Uncertainty

Every state carries posterior variance from its updater (analytic or Kalman).
Game forecasts use Gaussian moment-based target distributions evaluated by
CRPS and 50/80/95% interval coverage with rolling-origin calibration per
`docs/modeling/evaluation.md`. Rating variance is not outcome variance; the
translation layer separates them.

### D11 — Possession volume (v1 proxy)

Expected eligible possessions per team per game come from a small Ridge on
`[log own plays_per_drive, log opponent plays_per_drive]` predicting log
possessions, fit on preceding seasons and frozen for the validation season.
The certified `plays_per_drive` pace proxy is therefore the only v1 volume
input. Clock-based tempo reconstruction (Silver plays retains clock fields;
byplay would need extension) is a documented later challenger, out of scope
for v1.

### D12 — Score translation

- **Primary closed form.** Expected team points = expected possessions ×
  [league base efficiency + λ·(off_dev + def_dev)] + expected non-offense
  points + frozen league home-field-advantage constant, where deviations are
  the two states' native adjusted values relative to league mean (defense
  signed so lower-allowed is favorable) and λ is a single shrink coefficient
  calibrated once on preceding seasons (reported; expected near 1). Margin and
  total follow by summation.
- **Challenger bridge.** Fold-local Ridge (α = 10) on the four role ratings
  plus a non-neutral home-host indicator and an unknown-venue indicator —
  identical bridge across candidates, per the held Phase 4A design. The
  non-offense expectation enters both paths as an additive offset.

Both paths emit margin and total forecasts; the forecasting contract's gates
decide.

### D13 — FCS coverage and missing evidence

FBS-FCS games remain in the population with existing coverage gates. FCS teams
without their own state use the `fcs_partial_pool` fallback (preceding named
FCS cohort shrunk toward neutral with maximum cohort SD); a missing non-FCS
state is a hard error. Missing measurements stay null with quality reasons.
True-points validity gates are inherited (integral values, [0, 8] drive
points, ≥94% season reconciliation, paired offense-and-defense quarantine on
score-stream violations).

### D14 — Evaluation contract

Development corpus 2015–2019 and 2021–2025; 2020 excluded from every input,
label, prior, and fold. Outer validation seasons 2018, 2019, 2021–2025; inner
fitting strictly preceding from 2017 with at least two prior training seasons;
no transform fitted on validation. Evaluation is layered and ordered: (1)
rating quality — point-in-time correctness, stable season-long meaning,
responsiveness, uncertainty behavior, attribution, lineage; (2) prediction
quality — per the rating-phase gates (≥0.5% early-game improvement with
positive paired 90% lower bound and full-season MAE within 1% of reference;
≤5% regression guards per validation season and per completed-game stage);
(3) market comparison only afterward, per the roadmap. The reference for
definition-level comparison is fixed-ρ/exposure on the same definition;
definitions A and B compete under identical grids. Bootstrap: 2,000
replicates, paired season/week blocks, seed 20260908, 90% intervals. The
six-slate prospective policy and promotion rules are unchanged.

## Provisional constants (to freeze, never tune post hoc)

| Constant | Provisional | Frozen by |
| --- | --- | --- |
| PPP standardization floor / fallback | 0.30 / 1.00 pts per possession | Measurement certification |
| EPA/possession standardization floor / fallback | 0.50 / 1.50 expected pts per possession | Measurement certification |
| PPP equivalent prior exposure k | 8 possessions | Rating estimation |
| EPA/possession equivalent prior exposure k | 20 possessions | Rating estimation |
| Non-offense state equivalent prior exposure | 4 games | Score forecasting |
| Translation shrink λ, league HFA, volume Ridge | calibrated on preceding seasons, frozen per validation season | Score forecasting |

## Scope

### Included

- New specification document `docs/modeling/possession_rating_methodology.md`
  containing D1–D14, the constants table, and the follow-on contract
  interfaces (annex below).
- Updates to `docs/modeling/rating_system_requirements.md` (decided items
  leave the unresolved list), `docs/modeling/measurement_catalog.md`
  (possession measurements: proposed → specified-pending-certification),
  `docs/planning/data-first-football-forecasting-roadmap.md` and
  `docs/plans/index.md` (queue: methodology done → replacement contracts),
  `docs/decisions/decision_log.md` (the four user choices, dated 2026-09-11),
  and `mkdocs.yml` navigation for the new document.
- Alignment of `tests/test_data_first_documentation_authority.py` where it
  encodes methodology-pending language.

### Excluded

- Estimator or measurement code, configuration, R2 writes, data changes,
  catalog registration, V4/production/Neon/web changes, betting work, clock
  reconstruction, market ingestion, and any Phase 4B/5/6 content beyond their
  held statuses.

## Implementation Tasks

### Task 1 — Author the specification document

**Files:** `docs/modeling/possession_rating_methodology.md`, `mkdocs.yml`

**Changes:** Persist D1–D14 verbatim in substance with the constants table,
data-gap inventory, and reusable-machinery references (file:line) from this
contract. Add the document to the Modeling navigation.

**Acceptance criteria:** A reader can author the four follow-on contracts
without making a modeling decision; specified-vs-certified labels are
unambiguous.

### Task 2 — Update rating requirements authority

**Files:** `docs/modeling/rating_system_requirements.md`

**Changes:** Move decided items out of "unresolved and uncertified"; link the
new specification; shrink the deferred-decision list to what genuinely
remains (special-teams rating component, residual ML, artifact schema,
production activation).

### Task 3 — Update the measurement catalog

**Files:** `docs/modeling/measurement_catalog.md`

**Changes:** Record possession measurements (PPP, EPA/possession, possession
counts, non-offense points) as specified-pending-certification with exact
definitions; keep certified-vs-proposed distinctions intact.

### Task 4 — Update queue and decision records

**Files:** `docs/planning/data-first-football-forecasting-roadmap.md`,
`docs/plans/index.md`, `docs/decisions/decision_log.md`

**Changes:** Roadmap queue advances to replacement execution contracts;
decision log records the four 2026-09-11 user choices with this contract
link.

### Task 5 — Align authority tests

**Files:** `tests/test_data_first_documentation_authority.py` (only if
needed)

**Changes:** Update assertions that encode methodology-pending status; do not
weaken execution-hold or lineage checks.

## Follow-on Contract Interfaces (annex)

- **A. Possession measurement certification.** Produce per-team-game eligible
  possession counts, true offensive drive points, PPP and EPA/possession for
  both roles, and non-offense points for/against; freeze floors, fallbacks,
  and exposure equivalents from 2015–2019 representative data; inherit
  validity gates; publish immutable Preview research artifacts. No catalog
  registration.
- **B. Rating estimation tournament.** Both definitions × the 6-prior ×
  5-updater grid; layer-1 rating gates then bridge-evaluated prediction gates
  per D14; reference fixed-ρ/exposure per definition; implement the Kalman
  challenger (net-new code) to the held contract's specification.
- **C. Score forecasting.** Closed form and bridge challengers with the
  volume proxy and non-offense state; freeze λ, HFA, and volume coefficients
  per validation season.
- **D. Prospective evaluation.** Unchanged six-slate policy; frozen
  pre-kickoff predictions only.

## Testing Strategy

Documentation-only: authority tests remain green (or are updated per Task 5);
`uv run mkdocs build --strict --quiet` passes with the new document in
navigation; `git diff --check` is clean; scoped Ruff if any test file changes.

## Risks and Edge Cases

- Conflating *specified* with *certified*: every possession measurement stays
  uncertified until contract A passes; labels must stay explicit.
- Provisional constants must be frozen from representative data by the
  contracts named in the table — never tuned after seeing validation outcomes.
- The spec-vs-code weight discrepancy noted in Phase 3 (`quality_core_epa_split`
  equal weights vs the design document's weighted description) is recorded so
  the new spec always states the executable truth.
- Scope creep into estimator code is prohibited in this contract.

## Definition of Done

- [ ] Tasks 1–5 complete; specification persisted and navigable.
- [ ] `uv run mkdocs build --strict --quiet`, focused authority tests, and
      `git diff --check` pass.
- [ ] Implementation log written; contract status updated to `Implemented`.
- [ ] Follow-on planning tasks can proceed from the annex without new
      modeling decisions.

## Amendments

None yet.
