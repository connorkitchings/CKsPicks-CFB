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

## Deferred decisions

No document currently selects the estimator, rating scale, prior model,
uncertainty mechanism, special-teams component, residual model, concrete
artifact schema, or production activation date.
