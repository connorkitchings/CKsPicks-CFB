# Phase 1: Data and Evidence Audit

- **Status:** Implemented
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** `session_logs/2026-09-05/03-phase1-data-evidence-audit.md`
- **Sealed audit:** `artifacts/research/data-first-football-v1/phase1/2026-09-05T1510Z-phase1-evidence-audit-v2/` (complete_with_blockers; 57 issues; all 5 results unsupported pending Phase 2)
- **Commit policy:** Separate plan commit required

## Goal

Locate every selected data input, explain every population loss, and determine
which current research conclusions are reproducible, require correction, or
are unsupported.

## Dependencies and Scope

Phase 0 must pass. Audit R2/catalog lineage before underlying objects; cover
source captures, Silver/Gold, measurements, states, predictions, and reports.
No repair, model selection, production write, or subscription purchase occurs.

## Interfaces and Outputs

- Dataset inventory: identity/checksum, parents, schema, storage, seasons,
  population, timing, consumers, and eligibility.
- Issue register: evidence, severity, affected records/descendants, root-cause
  status, disposition, and verification need.
- Schedule-derived population denominator independent of successful joins.
- Coverage/exclusion report, hypothesis/error map, research-result disposition,
  and affordable-source comparison.

## Implementation Tasks

1. Verify only required R2/Preview configuration without revealing values;
   resolve manifests and catalog entries before data reads.
2. Inventory datasets and lineage across 2015-2019 and 2021-2025, with 2020
   rejection and separate FBS-FBS/FBS-FCS populations.
3. Audit keys, duplicates, joins, finite values, units, nulls, denominators,
   reconciliation, team classification, and authentic pregame availability.
4. Quantify first-game inclusion, unequal team experience, matchup routing,
   numerical warnings, silent drops, stacked rows, unique games, and bootstrap
   sampling units. Explicitly test the current evaluator's game-count semantics.
5. Map errors to football hypotheses: preseason strength, opponent quality,
   possession volume, scoring efficiency, roster change, and sparse opponents.
6. Compare automated QB/roster, transfers, weather, and special-teams sources,
   starting with CFBD. Record price, terms, timing, maintenance, and coverage;
   keep total subscriptions within $15/month and request purchase approval later.

## Acceptance and Validation

Every selected input is located or explicitly unresolved, every loss is counted
and explained, and every current result receives a disposition. An existing
certificate is evidence, not an audit substitute. Validate first games,
asymmetric experience, FCS opponents, overtime, cancellations, missing plays,
and classification changes with targeted record reconciliation plus complete
metadata/population checks.

## Failure Behavior and Done

Unresolved issues remain open in the register and block affected inputs from
certification; they do not block publication of the audit. Finish with immutable
reports, exact Phase 2 repair inputs, validation, session log, and status update.

## Amendments

Changing seasons, populations, timing rules, cost ceiling, or result-disposition
criteria requires a revised plan.

### Amendment 1 - Decision-complete implementation detail

**Approval source:** The user explicitly approved the detailed Phase 1
implementation plan on 2026-09-05.

The audit covers regular and postseason games involving at least one
season-classified FBS team. It uses separate `resolve` and `audit` stages,
recomputes evidence without refitting models, writes only beneath
`artifacts/research/data-first-football-v1/phase1/`, and may finish with
explicit blockers when existing evidence cannot establish the full population.
