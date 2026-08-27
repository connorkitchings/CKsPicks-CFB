# Rating-System Requirements

> **Status:** Approved initial requirements for 2026 research and shadow work.
> This is not a rating-engine implementation or a promotion authorization.

## Goal

Make a point-in-time, uncertainty-bearing team state the canonical expression
of team quality. Use it to create structured football predictions before any
market decision.

```text
source data → canonical Bronze/Silver/Gold → football measurements
→ measurement-level opponent adjustment → team ratings/state
→ structured game prediction → optional ML residual → probabilistic output
→ market decision
```

## Required behavior

### Point-in-time state

Before every scheduled game, the system must be able to reproduce a state for
each team using only evidence effective before that game’s kickoff. A conceptual
state includes:

- offense, defense, and overall quality;
- uncertainty associated with each relevant quality estimate;
- preseason-prior and observed-evidence contribution;
- completed-game and relevant exposure counts;
- source/version provenance and as-of timestamp; and
- coverage, missingness, and quality flags.

This is a conceptual contract, not a schema. The final rating scale, estimator,
prior, uncertainty method, and artifact format remain open.

### Layer boundaries

- **Measurement** records observed football performance.
- **Opponent adjustment** applies schedule and context interpretation once,
  upstream of the baseline rating engine.
- **Rating/state** accumulates adjusted evidence continuously through the
  season; credibility moves smoothly from preseason evidence to observed play.
- **Prediction** maps two frozen states plus venue and legitimate context to
  expected margin, total, or team scores.
- **Residual ML** is optional and may only model documented incremental matchup
  effects; it must not reconstruct team strength from scratch.
- **Market decision** receives timestamped prices only after football
  prediction, uncertainty, and provenance exist.

### Phase 1 remediation and Phase 2 baseline (implemented)

The original Phase 1 implementation is retained as research history but is not
an authorized Phase 2 input. Its corrective contract is
`docs/plans/2026-08-24/phase1-rating-measurement-remediation.md`; it replaces
the prior refs with v2 observations, season-to-date snapshots, and terminal
snapshots, materialized with bounded season-scoped reads under
`docs/plans/2026-08-24/phase1-phase2-completion.md`. Phase 2 is implemented
from that passing handoff under
`docs/plans/2026-08-24/phase2-minimum-viable-team-state-baseline.md`.

The Phase 2 baseline (state design ID
`ddd6033824909620aa381527dba202a06c65155de53403849b59ffcaaae7092d`) blends
the four adjustment-eligible measurements — EPA/play, success rate, 20-yard
explosive rate, and points per scoring opportunity, each weighted 25% — into
pregame and season-terminal offense/defense/overall states with non-null
posterior uncertainty: prior-season terminal carryover at `rho = 0.60`,
preceding-season team-equal standardization with frozen floors, precision
weighting by equivalent prior exposure, and reversed defensive direction.
Artifacts live under
`artifacts/research/rating-successor/states/ddd60338…/runs/2026-08-25T1153Z/`
(measurement states `69965b6a3eb6856f86ed554d`, team states
`1fdcb1ca6d235bf2ecf87414`) with all audit checks passing and a
byte-identical rerun; only `pregame` rows are eligible Phase 3 inputs. No
catalog registration occurred.

The measurement baseline contains EPA/play, success rate,
20-yard explosive rate, points per scoring opportunity, average starting
field position, plays per drive, and turnover rate. Only the first four are
adjustment-eligible; field position, pace, and turnovers remain contextual
until a later contract says otherwise.

The adjustment is four fixed, league-centered additive iterations over
strictly prior evidence, with iteration zero and four retained for audit.
Zero exposure stays null with a quality reason; play eligibility is
`is_drive_play == 1` and `garbage == 0`. Reconstructed 2021–2025 timing is
valid for historical development only; protected 2026 evidence requires
authentic source timing. The implementation lives in the isolated
`cks_picks_cfb.ratings` namespace with the Preview-only CLIs
`scripts/pipeline/build_rating_measurements.py` and
`scripts/pipeline/build_rating_team_states.py`; V4 paths are untouched.
Phase 2 consumed exactly the bounded refs and checksums recorded in the
corrected [measurement catalog](measurement_catalog.md) and produces only
Preview research component and team-state artifacts; no catalog registration
occurs unless explicitly requested.

That v2/v1 handoff is now superseded for new research by certified true-PPSO
Phase 1 v3 (report SHA
`79f4370febcc95672380f703958e8dcc357c40161be58d9d110869b22c153e25`). Phase
2 v2 retains the same estimator but pins the v3 inputs and gates location only
on representative pregame populations (at least 90% of terminal-season teams)
plus every terminal population. It must pass a refreshed foundation review
before Phase 3 v3 can inspect historical outcomes. Phase 4 remains blocked.

Phase 3 v1 is immutable failed research: its two-equation margin/total OLS
diagnostic had complete paired V4 coverage but failed the frozen calibration
and total-bias gates. The successor is the separate
[sealed v2 team-score tournament](../plans/2026-08-25/phase3-score-model-tournament-v2.md),
which compares linear and NB2 team-score families on 2022–2024 expanding
folds and confirms its selected, unchanged family once on 2025. It cannot tune
v1, relax a gate, freeze a candidate, or begin Phase 4 unless all gates pass.
Its sealed 2026-08-26 selection also failed: linear scores passed margin but
failed total calibration, while NB2 failed required uncertainty/calibration
gates. The immutable diagnostic is evidence only; no candidate or operational
shadow artifact exists.

The passing successor is the sealed
[Phase 3 v3 tournament](../plans/2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md)
on the true-PPSO Phase 1 v3 and Phase 2 v2 foundation. Linear scores failed
complete-family selection (non-positive score means); `negative_binomial_scores`
passed the 2022–2024 sealed selection and the unchanged locked-2025
confirmation on 1,522 fully V4-paired games — margin MAE `13.30` vs V4 `15.52`
with paired-lift 95% CI `[1.59, 2.82]`, total MAE `13.41` vs V4 `13.39` at
parity, and every bias/standardization/interval gate true — then refit
unchanged on 2021–2025. Candidate v1 identity: design
`503d422c22bc357bfb25b7fe27f8f9c5e14098a1d2748e71d58b043d5a74e6fe`, code
`c4c5cfb`, models ref `071f4de17b4b351e74e0a670`, predictions ref
`75e9a9cc7e942823bde56a2a`, tournament SHA-256
`f71a0f437bf9156670fadd44e5dba6b42f56f8f63f666b682c389da37dfa54bd`. The
candidate is frozen: it must not be tuned on any outcome it later claims as
protected. Phase 4 shadow operations are implemented: the immutable
Preview-only all-2025 rehearsal passed all 15 weeks and a byte-identical rerun
(summary SHA-256 `b755b585…`). Phase 5 tooling is In Progress; live protected
evidence remains blocked until its committed-code and Preview-environment gates
pass. Shadow
operations may read a frozen V4 run only for paired evaluation; they cannot
alter V4, production data, publication, or candidate v1.

### Data and lineage

- Use immutable Bronze/Silver/Gold lineage, stable team/game keys, and strict
  effective-time provenance.
- Exclude 2020 entirely. Treat 2019 as prior-quality lineage only for early
  2021 where already permitted by current policy.
- Never use bookmaker-derived values in measurements, ratings, football-model
  selection, or prediction inputs.
- Carry enough lineage to reproduce each state and game prediction from exact
  dataset versions and configuration.

### Uncertainty and output

The baseline must produce uncertainty-bearing state and game outputs, not null
standard-deviation placeholders. The mechanism may be simple initially, but it
must be point-in-time, interpretable, and evaluable for calibration and
contraction as credible evidence grows.

### Research and production isolation

Initial rating artifacts are immutable research/shadow outputs. They cannot be
inserted into V4 bundles, Neon activation, public publication, or rollback
selection. V4 remains the production comparison baseline.

## Evaluation and promotion requirements

Historical 2021–2025 data supports temporal development. Because its outcomes
are already known, it does not provide untouched successor evidence. Each
candidate uses the protected 2026 policy in [evaluation](evaluation.md): freeze
the design, data cutoff, configuration, and predictions before outcomes.

The first promotion review requires six completed full slates with normal
coverage; Week 0 does not count. The review must establish rating stability and
responsiveness, uncertainty calibration, structured prediction quality relative
to V4, reproducibility, operational rehearsal, and rollback. Timestamped
market value is evaluated only afterward. A separate approved promotion contract
is mandatory.

## Follow-on implementation contracts

1. Measurement and adjustment interfaces, coverage audit, and redundancy study.
2. Deliberately simple point-in-time rating baseline.
3. Structured rating-to-game prediction and shadow artifact contract.
4. Candidate-estimator, special-teams, uncertainty, and residual-ML research.
5. Evidence-gated promotion, rehearsal, and rollback contract.

Each follow-on contract requires a fresh Terra task before its estimator
code, artifacts, Preview catalog registration, or audit execution occurs.

## Deferred decisions

No document currently selects the estimator, rating scale, prior model,
uncertainty mechanism, special-teams component, residual model, concrete
artifact schema, or production activation date.
