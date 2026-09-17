# V5-05B: Shadow Freeze, Scoring, and Evidence Ledger

- **Status:** Approved
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** User explicitly approved implementation on 2026-09-17 ("proceed").
- **Implementation log:** `session_logs/2026-09-17/12-v5-05b-freeze-score-ledger.md`.
- **Commit policy:** Separate code checkpoint and certified-evidence documentation checkpoint; user executes Git.

## Goal

Implement Contract 05 Tasks 3–4 on the Phase 05A foundation: measured immutable
shadow freezes (T−2h target, T−1h hard gate, ≥40 paired games, population
preservation) and outcome-versioned scoring with the evidence ledger/counter.
Proves fail-closed behavior on timing, identity, population, source, and
prediction failure, with idempotent reruns that never rewrite evidence.

## Current State and Entry Gate

Phase 05A must be **Implemented** with a committed SHA and reviewed
deterministic preflight evidence before 05B executes. Required 05A interfaces:
`data_first_shadow_v1` contracts (all six schemas frozen),
`shadow.check_source_availability()`, `shadow.build_readiness_report()`,
`shadow.replay_frozen_forecast()`, the readiness CLI, and `shadow_v1.yaml`.

The readiness verdict from 05A (expected `blocked` for live 2026) does not
block building freeze/score tooling — the tooling is proven in diagnostic
rehearsal terms here and exercised against live inputs only when readiness
permits. Phase 05B tooling must work identically in both cases.

This contract remains **Draft** until a separate explicit user approval after
05A certifies. Phase 05C must not execute until 05B is Implemented. V5-05
remains Approved and is not complete until 05C certifies.

## Proposed Approach

Extend `forecast/shadow.py` with `plan_freeze()`, evidence-bound freeze
apply, `score_freeze()`, and `update_evidence_counter()`, following the proven
03B/04B manifest-last, evidence-replay, idempotent-repeat discipline. Two CLIs
(freeze, score) share the common flag contract and the 05A parent-verification
path. Certify Phase 05B with its own Preview preflight/apply/verify cycle.

## Scope

### Included

- Measured freeze: T−2h target/T−1h hard gate, V4 pairing, slate digest,
  population preservation, cancellation/postponement dispositions
- Freeze apply path: evidence replay, manifest-last, collision/idempotency
- Outcome-versioned scoring: 24h stabilization, correction history, MAE/RMSE/
  bias/CRPS/coverage/width, stage slices, paired/broader coverage
- Evidence ledger/counter with qualifying reasons and no-double-count rule
- Focused tests, quality gates, Phase 05B certification execution

### Excluded

- Readiness/replay (Phase 05A, prerequisite)
- Diagnostic rehearsal, shadow verifier, runbook, Contract 06 handoff (Phase 05C)
- Measurement/rating pipeline extension, prospective collection (Contract 06)
- Any V4, Neon, catalog, web, subscription, provider, scheduler change

## Architecture decisions

Inherit all 05A interfaces unchanged: six schemas and column tuples, stage
root, pinned 04/R6/Repair parent URIs, `shadow_v1.yaml` constants
(`freeze_target_lead_seconds: 7200`, `freeze_hard_lead_seconds: 3600`,
`score_stabilization_seconds: 86400`, `minimum_paired_games: 40`),
R2-only writes, `production_activation_authorized: false`.

**Freeze record grain:** one `shadow_freeze` row per (candidate, season, week,
run); `shadow_prediction` partitioned by `(season, week)` with one row per
(game, target). Broader FBS-involving population, V4-paired subset, and every
exclusion persisted separately — no post-kickoff subset construction.

**Scoring record grain:** one `shadow_evaluation` row per (candidate, season,
week, outcome_version, game, target); `evidence_counter` one row per
(candidate, season, week) with `qualifying` boolean, `reason`, and
freeze/evaluation refs. The count is independently derivable from
freeze/evaluation pairs, never from stored counters alone.

**Timing authority:** measured freeze-completion/object-availability time
governs; a supplied `--as-of` cannot backdate it. Scoring requires trustworthy
completion timestamps — never kickoff-plus-duration substitution.

## Affected Components and Interfaces

- Extend `src/cks_picks_cfb/forecast/shadow.py`: `plan_freeze()`,
  `score_freeze()`, `update_evidence_counter()`.
- New `scripts/research/run_v5_shadow_freeze.py`: CLI adds
  `--readiness-manifest-uri`, `--slate-ref-uri`, `--v4-prediction-ref-uri`;
  `--apply` + `--preflight-evidence` for the evidence-bound path.
- New `scripts/research/run_v5_shadow_score.py`: CLI adds
  `--freeze-manifest-uri`, `--outcome-ref-uri`; `--apply` +
  `--preflight-evidence`.
- Reuse 05A contracts/config/schemas unchanged; `PartitionedDatasetWriter`
  for `shadow_prediction`/`shadow_evaluation`; compact writes for
  `shadow_freeze`/`evidence_counter`.
- New `tests/test_v5_shadow_freeze.py`, `tests/test_v5_shadow_score.py`.

## Implementation Tasks

### Task 1 — Measured immutable freezes

**Files:** `src/cks_picks_cfb/forecast/shadow.py`,
`scripts/research/run_v5_shadow_freeze.py`.

**Changes:** `plan_freeze()` validates readiness manifest (`ready` for live;
diagnostic rehearsal path bypasses with permanent `diagnostic_only` class),
first-kickoff derivation, T−2h targeting with T−1h hard gate on measured
completion, exact V4 ref binding, slate-membership digest, source-availability
proofs, complete finite both-target predictions, ≥40 paired games with normal
coverage; broader/paired/excluded populations persisted separately;
cancellation/postponement retained with disposition; Week-0/pre-candidate/
diagnostic/late/incomplete/unverifiable/altered freezes rejected with reasons.
Evidence-bound apply: publication plan first, `shadow_prediction` partitions
compared before enqueue, `shadow_freeze` compact validated, terminal freeze
manifest last; prefix inspection (exact manifest → `already_applied`;
incompatible/partial → permanently ineligible).

**Acceptance criteria:**
- T−1h-violation, <40-game, altered-identity, post-kickoff-subset, and
  partial-prefix fixtures all fail closed with named reasons.
- Byte-identical rerun returns `already_applied` with zero writes.
- V4 ref mismatch or missing V4 pairing rejected.

**Validation:** focused freeze tests (timing edges at exactly T−2h/T−1h,
39-vs-40 boundary, population preservation, collision, idempotency)
warnings-as-errors; CLI `--help`/compile.

### Task 2 — Outcome-versioned scoring and counting

**Files:** `src/cks_picks_cfb/forecast/shadow.py`,
`scripts/research/run_v5_shadow_score.py`.

**Changes:** `score_freeze()` requires exact freeze manifest + outcome ref
(no mutable current-week lookup); ≥24h after last included completion with
trustworthy timestamps; MAE/RMSE/bias, candidate CRPS/coverage/width, stage
slices, paired/broader coverage, unavailable-V4-uncertainty marked as such;
corrections create new evaluation versions linked to the original freeze
(never overwrite, never double-count). `update_evidence_counter()` derives the
qualifying count from verified freeze/evaluation pairs; each
candidate/season/week counted once; exclusions/corrections visible with
old↔new links.

**Acceptance criteria:**
- <24h, missing-timestamp, missing-outcome fixtures block scoring (freeze
  evidence untouched).
- Correction creates a linked new version; counter unchanged.
- Counter independently reproducible from immutable refs.

**Validation:** focused score/ledger tests (24h edges, corrections,
duplicates, population splits) warnings-as-errors.

### Task 3 — Phase 05B certification execution

**Changes:** on a clean committed worktree, capture full SHA + shared UTC
cutoff; fresh run IDs `shadow-v1-YYYYMMDD-<shortsha>-05b-freeze` and
`-05b-score`; no-write preflights → evidence review (zero warnings, plans
complete, gates hold) → evidence-bound Preview applies → idempotent repeats.
Record elapsed phases, row counts, digests, freeze verdicts, immutable URIs.

**Acceptance criteria:**
- Preflight, apply, repeat pass under identical lineage for both pipelines.
- Any mismatch/warning/gate failure = failed identity → repair + new commit.

**Validation:** full warning-as-error suite; scoped ruff; `ruff check .`;
`make contracts-check`; strict mkdocs; R2 inventory (Preview shadow paths
only); `git diff --check`.

## Testing Strategy

- Unit: timing edges (exactly 7200/3600/86400s), 39-vs-40 boundary,
  population preservation, slate-digest stability, correction linking.
- Negative: late/incomplete/unverifiable freezes, altered identity, partial
  prefix, missing timestamps/outcomes, double-count attempts, V4 mismatch,
  post-kickoff subset construction.
- Integration: small freeze→score→ledger fixture dry-run/apply/reapply with
  evidence replay and idempotency.
- Regression: 05A suite; full warning-as-error suite.

## Risks and Edge Cases

- **V4 freeze coupling.** Shadow freeze needs V4 predictions frozen on V4's
  schedule. Never change V4's cadence to qualify a slate; record unpaired
  slates as nonqualifying with reasons.
- **Week 3 live state.** Rehearsal fixtures must not assume current-week
  availability; use pinned historical refs for deterministic evidence.
- **Schedule changes.** Cancellations/postponements stay visible; scored
  paired count <40 renders the slate ineligible without rewriting history.
- **Long scoring recomputation.** Stream by partition with bounded progress;
  interrupted runs re-execute under the same identity.

## Definition of Done

- [ ] Measured freeze tooling with fail-closed timing/population/identity gates.
- [ ] Outcome-versioned scoring with correction history and ledger/counter.
- [ ] Phase 05B preflight/apply/repeat certified in Preview for both pipelines.
- [ ] All quality gates pass; session log complete.
- [ ] User commits code and evidence checkpoints separately.
- [ ] 05B Implemented; 05C entry gate met.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be
logged if output order, bytes, plans, digests, identities, and acceptance
criteria are unchanged. Any change to sources, math, timing rules, population
gates, schemas, eligibility, or verification independence requires
user-approved replanning.
