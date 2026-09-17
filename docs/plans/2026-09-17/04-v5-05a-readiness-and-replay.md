# V5-05A: Readiness Validation and Frozen Replay

- **Status:** In Progress
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** User explicitly authorized implementation of this exact plan path on 2026-09-17 ("Use the repository-local implement-plan skill and implement the approved contract at: docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md ... This request explicitly authorizes implementation.").
- **Implementation log:** `session_logs/2026-09-17/10-v5-05a-readiness-and-replay.md`.
- **Commit policy:** Separate code checkpoint and certified-evidence documentation checkpoint; user executes Git.

## Goal

Implement Contract 05 Tasks 1–2 for the certified V5 forecast candidate: validate
authentic source availability with a verified ready/blocked readiness report, and
prove frozen-algorithm replay (identical forecasts from identical
candidate/state/input refs, no current-week outcome leakage, no refitting on
prospective outcomes). This phase establishes the ready/blocked verdict that
gates how Phases 05B/05C exercise live inputs.

**Expected outcome:** a verified `blocked` readiness report. The same-day
readiness assessment (`docs/research/2026-09-17-v5-live-readiness-assessment.md`)
found the certified artifacts cover 2015–2019 and 2021–2025 only, with no 2026
measurement/rating pipeline and Preview lagging production. Terra's verified
assessment decides the verdict; the expectation does not substitute for it.

## Current State and Entry Gate

The Contract 05 entry gate is met. Contract 04 is Implemented:
- Certified forecast `forecast-v1-20260917-4600ddd-04b` (commit `4600ddd`,
  cutoff `2026-09-17T16:40:02Z`, shared `expanding` horizon, alpha-10 reference
  heads, calibration 311–375 across 2022–2025)
- Certified rating parent `possession-v1-ratings-20260917-d029526-cert`
- Certified measurement parent
  `possession-v1-measurements-20260915-18fb0aa-r6`
- Certified repair parent `repair-v2-20260909T1417Z`

No V5 shadow code, config, schemas, or CLIs exist. The candidate-v1 system
(`src/cks_picks_cfb/ratings/shadow.py`, `prospective.py`,
`scripts/pipeline/build_rating_shadow_*.py`, `conf/ratings/shadow_operations_v1.yaml`)
is a pattern reference only; its counter and candidate identity must not be reused.

This contract remains **Draft** until a separate explicit user approval. Phase 05B
must not execute until 05A is Implemented with a committed SHA and reviewed
deterministic preflight evidence. V5-05 remains Approved and is not complete
until 05C certifies.

## Proposed Approach

Build the V5 shadow foundation in the `forecast` package namespace: all six
shadow schema contracts up front (so 05B/05C build on stable interfaces), the
source-availability checker and readiness reporter, and the frozen-replay proof.
Certify Phase 05A with its own Preview preflight/apply/verify cycle for the
readiness record pipeline — the same evidence-bound discipline as 03B/04B —
before Phase 05B consumes its interfaces.

## Scope

### Included

- All six shadow schema contracts and column tuples (stable interfaces for 05B/05C)
- `shadow_v1.yaml` config with timing constants, population gates, diagnostic class
- Source-availability validation: exact parent resolution, schedule/completed-game/
  score-possession/preseason-auxiliary checks, capture-vs-effective-time proof
- Readiness report (`ready` or `blocked` with named reasons), evidence-bound and verified
- Frozen-algorithm replay proof on historical refs
- Focused tests, quality gates, Phase 05A certification execution in Preview

### Excluded

- Shadow freezes, scoring, ledger/counter (Phase 05B)
- Diagnostic rehearsal, shadow verifier, runbook, Contract 06 handoff (Phase 05C)
- Measurement/rating pipeline extension for 2026 incremental updates (separate future contract)
- Any V4, Neon, catalog, web, subscription, provider, scheduler, or automation change
- Prospective slate collection or recommendation (Contract 06)

## Architecture decisions

**Module location:** `src/cks_picks_cfb/forecast/shadow.py` (producer), alongside
`offsets`/`heads`/`horizons`/`calibration`. Contracts in
`src/cks_picks_cfb/data/data_first_shadow_v1.py`. Config at
`conf/research/data_first_football_v1/shadow_v1.yaml`.

**Stage and output root:**
`artifacts/research/data-first-football-v1/possession-v1/shadow/runs/<run-id>/`.

**All six schema contracts** (names `data_first_possession_<record>_v1`,
defined in 05A, frozen for 05B/05C):

| Record | Columns | Type |
|---|---|---|
| `readiness` | `candidate, season, week, run_id, source, status, timing_class, fallback, blocked_reason, overall` | compact |
| `shadow_freeze` | `candidate, season, week, run_id, freeze_time, first_kickoff, lead_seconds, v4_ref_uri, slate_digest, paired_count, broader_count, excluded_count, identity_sha256` | compact |
| `shadow_prediction` | `candidate, season, week, run_id, game_id, target, mean, variance, interval_lower_95, interval_upper_95, offset, model_ref, state_ref` | partitioned `(season, week)` |
| `shadow_evaluation` | `candidate, season, week, run_id, outcome_version, game_id, target, actual, error, crps, coverage_95` | partitioned `(season, week)` |
| `evidence_counter` | `candidate, season, week, qualifying, reason, freeze_ref, evaluation_ref` | compact |
| `shadow_rehearsal` | `candidate, run_id, season_range, diagnostic_only, cases_passed, cases_failed, verifier_ref` | compact |

**Pinned parents** (exact URIs, verified at every consumption with signed
payloads, frozen state, raw-SHA reconciliation, `production_activation_authorized
is False`):
- Forecast: `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json`
- Rating: `…/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`
- Measurement: `…/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json`
- Repair: `…/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`

**Blocked-readiness semantics:** any unavailable mandatory input, unverifiable
timing, or post-cutoff evidence → `overall = blocked` with named
`blocked_reason` per source. A technically verified `blocked` report satisfies
05A tooling completion but does not satisfy Contract 06's entry gate.

## Affected Components and Interfaces

- New `src/cks_picks_cfb/data/data_first_shadow_v1.py`: six dataset registry,
  column tuples, `validate_shadow_config()`, `verify_candidate_parents()`,
  `shadow_identity()`, `shadow_manifest()` (signed, manifest-last).
- New `src/cks_picks_cfb/forecast/shadow.py`: `check_source_availability()`,
  `build_readiness_report()`, `replay_frozen_forecast()`.
- New `scripts/research/run_v5_shadow_readiness.py`: CLI (`--run-id`,
  `--expected-code-sha`, `--environment preview`, `--as-of`, `--config`,
  `--candidate-manifest-uri`, `--season`, `--week`, `--v4-prediction-ref-uri`,
  `--input-refs-uri`, `--slate-ref-uri`; `--apply` + `--preflight-evidence`
  for the evidence-bound path). Dry run default.
- New `conf/research/data_first_football_v1/shadow_v1.yaml`:
  `production_activation_authorized: false`, `freeze_target_lead_seconds: 7200`,
  `freeze_hard_lead_seconds: 3600`, `score_stabilization_seconds: 86400`,
  `minimum_paired_games: 40`, `diagnostic_only` class.
- New `tests/test_v5_shadow_readiness.py`.
- Uses `PartitionedDatasetWriter`, `build_dataset_version`, and immutable lake
  primitives; no second storage format.

## Implementation Tasks

### Task 1 — Shadow data contracts and config

**Files:** `src/cks_picks_cfb/data/data_first_shadow_v1.py`,
`src/cks_picks_cfb/data/schema_contracts.py`,
`conf/research/data_first_football_v1/shadow_v1.yaml`.

**Changes:** register all six schemas with the column tuples above;
`validate_shadow_config()` enforces schema version, timing constants,
population gate, diagnostic class, and `production_activation_authorized is
False`; `verify_candidate_parents()` enforces exact forecast/rating/
measurement/repair URIs, raw-SHA reconciliation, signed payloads, frozen
state; `shadow_identity()` and `shadow_manifest()` mirror the 04B manifest
pattern (identity, parents, output refs, `production_activation_authorized:
false`, signed last).

**Acceptance criteria:**
- All six schemas resolve; wrong-parent/missing-key/tampered-signature
  fixtures rejected with named errors.
- Drifted timing constants or gate values fail `validate_shadow_config`.

**Validation:** focused contract tests warnings-as-errors; `contracts/validation.py`.

### Task 2 — Source availability and readiness report

**Files:** `src/cks_picks_cfb/forecast/shadow.py`,
`scripts/research/run_v5_shadow_readiness.py`.

**Changes:** `check_source_availability()` resolves and independently verifies
every candidate parent, then checks live schedule, completed-game sources,
score/possession semantics, preseason/auxiliary inputs, and team-state
reconstructability at the cutoff; capture-vs-effective timestamps must prove
pre-cutoff availability. `build_readiness_report()` persists one row per
(candidate, season, week, source) with status/timing-class/fallback/blocked
reason and the derived overall. Only declared fallbacks permitted — never
reinterpret, backdate, or recapture. Evidence-bound apply path writes the
`readiness` compact dataset via `build_dataset_version` after plan
comparison; terminal readiness manifest written last.

**Acceptance criteria:**
- Unavailable-mandatory-input fixture → `overall = blocked` with named reason.
- Complete-input fixture → `overall = ready` with full forecast reproduction.
- Capture-after-cutoff and reconstructed-as-authentic fixtures rejected.

**Validation:** focused readiness tests (available/blocked/timing/fallback
matrices) warnings-as-errors; CLI `--help`/compile.

### Task 3 — Frozen algorithm replay proof

**Files:** same as Task 2 (`--replay` mode on the readiness CLI).

**Changes:** `replay_frozen_forecast()` freezes fitted prior/noise/head/
calibration parameters through the preceding completed season; updates ratings
and non-offense offsets only from permitted finalized games in earlier
canonical weeks with pre-freeze source availability. Proves one-use prior
observations, no current-week outcome leakage, byte-identical forecasts from
identical candidate/state/input refs.

**Acceptance criteria:**
- Current-week-outcome perturbation leaves earlier forecasts unchanged.
- Identical-refs rerun byte-identical.
- Refit-on-prospective fixture rejected.

**Validation:** replay invariance tests warnings-as-errors.

### Task 4 — Phase 05A certification execution

**Changes:** on a clean committed worktree, capture full SHA + shared UTC
cutoff; fresh run ID `shadow-v1-YYYYMMDD-<shortsha>-05a`; no-write preflight
→ evidence review (zero warnings, readiness plan complete, replay
byte-identical) → evidence-bound Preview apply → readiness-record verification
→ idempotent repeat (`already_applied`, no writes). Record elapsed phases, row
counts, digests, readiness verdict, immutable URIs.

**Acceptance criteria:**
- Preflight, apply, verification, repeat all pass under identical lineage.
- Any mismatch/warning/gate failure = failed identity → repair + new commit,
  never reuse.

**Validation:** full warning-as-error suite; scoped ruff; `ruff check .`;
`make contracts-check`; strict mkdocs; R2 prefix inventory (Preview shadow
paths only); `git diff --check`.

## Testing Strategy

- Unit: contract/schema validation, per-source availability matrices, fallback
  policy (mandatory vs optional), timing-class boundaries, replay invariance.
- Negative: unavailable mandatory input, capture-after-cutoff, reconstructed
  presented as authentic, current-week leakage, refit-on-prospective, evidence
  mismatch, partial prefix, immutable collision.
- Integration: small dry-run/apply/verify/reapply fixture for the readiness
  pipeline with all evidence replayed.
- Regression: adjacent forecast/rating suites; full warning-as-error suite.

## Risks and Edge Cases

- **Expected `blocked` verdict.** The same-day assessment found no 2026
  measurement/rating pipeline and Preview lagging production. Terra's verified
  assessment decides; the expectation must not become a self-fulfilling skip
  of live-source checks.
- **Long parent streaming.** R6 + rating replay is the costliest step; the
  bounded stderr `_Progress` pattern (30s cap, forced phase events,
  secret-safe) is required; stdout stays pure JSON.
- **Byte-equivalence.** Preflight repeats must run in one environment/session;
  no dependency upgrades between runs.
- **Week 3 is live.** The real-season assessment must account for frozen Week 3
  (close pending Tue Sep 22+); a supplied `--as-of` cannot backdate measured
  availability.

## Definition of Done

- [ ] All six shadow schemas/contracts registered with focused coverage.
- [ ] Readiness validation + verified ready/blocked report with named reasons.
- [ ] Frozen-replay proof with leakage/refit rejection.
- [ ] Phase 05A preflight/apply/verify/repeat certified in Preview.
- [ ] All quality gates pass; session log complete.
- [ ] User commits code checkpoint and evidence checkpoint separately.
- [ ] 05A Implemented; 05B entry gate (committed SHA + reviewed evidence) met.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be
logged if output order, bytes, plans, digests, identities, and acceptance
criteria are unchanged. Any change to sources, math, timing rules, population
gates, schemas, eligibility, or verification independence requires
user-approved replanning.
