# Data-First Football Forecasting Roadmap

> **Status:** Approved 2026-09-05
> **Production authority:** V4 remains unchanged
> **Research namespace:** `artifacts/research/data-first-football-v1/`

## Purpose

Improve spread and total forecasts by establishing trustworthy data, validating
football measurements, selecting simple team ratings, and evaluating frozen
forecasts prospectively. Authentic timestamped lines are comparison evidence
after football-model evaluation. Bet selection, staking, bankroll management,
and betting-policy optimization are deferred.

Preserving the working system is mandatory. The program does not modify V4
production predictions, weekly operations, publication, bundle loading, or
rollback behavior. Corrected research behavior receives new versioned
identities when a shared change could affect production.

## Governing boundaries

- Target all games involving at least one FBS team, including FBS-FCS games.
- Develop historically on 2015-2019 and 2021-2025; exclude 2020 everywhere.
- Treat 2025 as development evidence only in this new program. Existing
  experiments retain their original evaluation contracts.
- Use future predictions frozen before kickoff as independent evidence.
- Prefer automated sources and simple, interpretable benchmarks.
- Keep recurring data subscriptions at or below $15/month total, including the
  existing reported $4 CFBD subscription. Purchases require separate approval.
- Permit recent-era feature families on declared shorter windows when coverage
  and chronological evaluation requirements pass.
- Let evidence determine timing; there is no deadline for replacing V4.

## Architecture

```text
Current production (preserved)
R2 data/artifacts -> V4 inference -> Neon serving state -> Vercel

New research (isolated)
audited data -> football measurements -> opponent adjustment
-> offense/defense team state + uncertainty -> spread/total forecast
-> prospective evaluation -> timestamped line comparison
```

Top-level responsibilities remain stable: reusable Python under
`src/cks_picks_cfb/`, production entry points under `scripts/pipeline/`, active
research entry points under `scripts/research/`, exploratory work under
`research/`, configurations under `conf/`, and current authority under `docs/`.

## Ordered phases

| Phase | Contract | Exit decision |
| --- | --- | --- |
| 0 | [Repository alignment](../plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md) | Current operations are regression-protected and the active architecture is unambiguous. |
| 1 | [Data and evidence audit](../plans/2026-09-05/01-data-and-evidence-audit.md) | Every selected input and population loss is located or explicitly unresolved. |
| 2 | [Repair and recertification](../plans/2026-09-05/02-data-repair-and-recertification.md) | Admitted research inputs contain no unresolved correctness or leakage defect. |
| 3 | [Measurement validation](../plans/2026-09-05/03-football-measurement-validation.md) | Useful, redundant, inconclusive, and unavailable information is distinguished. |
| 4 | [Simple ratings](../plans/2026-09-05/04-simple-team-rating-benchmarks.md) | One reproducible simple rating benchmark is frozen. |
| 5 | [Spread/total forecasting](../plans/2026-09-05/05-spread-total-forecasting.md) | One eligible candidate or valid simple reference is frozen. |
| 6 | [Prospective evidence](../plans/2026-09-05/06-prospective-evidence-and-line-comparison.md) | Evidence supports retention, continued shadowing, or a separate promotion plan. |

Automated pregame capture begins after its Phase 2 validation and continues
alongside later research. Each phase consumes explicit passing predecessor
artifacts, runs in a separate implementation task, and publishes evidence plus
a session log. A failed phase produces a diagnostic and blocks dependent work;
criteria are not weakened after results.

## Authority transition

This roadmap replaces the pending R3/R4 sequence and the unfinished research
portion of the historical-expansion roadmap. Completed R1/R2 work, candidate
v1, and direct early-game research remain immutable historical evidence subject
to Phase 1 audit disposition. V4 remains the production benchmark and rollback
authority throughout.

