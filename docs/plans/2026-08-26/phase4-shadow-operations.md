# Phase 4 — Isolated Shadow Operations

- **Status:** In Progress
- **Created:** 2026-08-26
- **Planner:** Sol
- **Approval source:** User approved this exact contract on 2026-08-26 and
  selected: exact-match rehearsal oracle, all-2025-weeks rehearsal, R2
  production-run V4 pairing, opt-in preview catalog registration.
- **Implementation log:** `session_logs/2026-08-26/04-phase4-shadow-operations.md`
- **Commit policy:** Separate plan commit recommended before implementation
  commits (governs protected prospective evidence and Phase 5–7 execution).

## Goal

Deliver the research-only weekly shadow lifecycle for frozen candidate v1 —
pregame state/prediction freeze before kickoff, paired postgame scoring
against V4 — fully isolated from V4 bundles, Neon production, publication, and
rollback authority. Observable success:

- A rehearsal across **all 2025 weeks** reproduces the frozen locked-2025
  predictions exactly (numeric oracle) and exercises the complete scorer
  against the certified V4 benchmark.
- The freeze and score CLIs are operational for 2026 game weeks with
  fail-closed coverage, timing, duplication, and integrity gates.
- No production interface, public API, or V4 artifact changes; Week 1 becomes
  plan-eligible for Phase 5 only if every rehearsal gate passes unweakened.

## Current State

- Frozen candidate: `negative_binomial_scores`, design `503d422c…`, code
  `c4c5cfb`; models ref `rating_score_models_v3` version
  `071f4de17b4b351e74e0a670` (contains `selection`, `locked_confirmation`
  (trained 2021–2024), and `final_refit` stage records with JSON-serialized
  coefficients/covariance/dispersion); predictions ref
  `rating_score_predictions_v3` version `75e9a9cc7e942823bde56a2a`
  (locked-2025 rows = exact rehearsal oracle); V4 benchmark replay
  `f4ec062c7f931f125ce6be99`.
- Phase 1 v3 measurement and Phase 2 v2 state builders are cutoff-native
  (kickoff-ordered pregame snapshots) and rerun-proven; `predict_score_model`
  derives margin/total with PSD covariance from a reconstructable
  `ScoreModel`.
- 2026 weekly Silver rebuilds flow through the existing `prepare-week` preview
  path; V4's authoritative weekly predictions are the frozen production run
  artifacts in R2 (`artifacts/production/predictions/…`).
- No shadow tooling, freeze manifest schema, or evidence ledger exists. Week 1
  kickoffs begin ~Sept 5.

## Proposed Approach

One new isolated subsystem, `shadow-v1`, with three pieces: (1) exact
`ScoreModel` reconstruction from the frozen models ref, verified against the
frozen predictions; (2) a pregame freeze CLI that rebuilds point-in-time 2026
states from pinned Silver parents and predicts with the **unchanged** frozen
`final_refit` model, writing an immutable freeze manifest before earliest
kickoff; (3) a postgame scoring CLI that joins authoritative outcomes and
paired V4 predictions, appending an immutable evidence ledger. Correctness is
proven by a full-season 2025 rehearsal whose predictions must equal the frozen
locked-2025 rows — the strongest available determinism oracle — using the
`locked_confirmation` model stage, which is exactly point-in-time correct for
2025.

## Scope

### Included

- `src/cks_picks_cfb/ratings/shadow.py` (+ tests): model reload, freeze/score
  core, manifest and ledger schemas.
- `scripts/pipeline/build_rating_shadow_freeze.py`,
  `scripts/pipeline/build_rating_shadow_score.py`,
  `scripts/pipeline/run_rating_shadow_rehearsal.py` (Preview-only).
- New immutable schemas: `rating_shadow_freeze_manifest_v1`,
  `rating_shadow_predictions_v1`, `rating_shadow_evidence_v1`,
  `rating_shadow_score_report_v1`; research prefix
  `artifacts/research/rating-successor/shadow-v1/<design>/…`.
- Preview Neon **catalog** registration of shadow datasets behind an explicit
  `--register-catalog` flag (preview branch, `catalog` schema only).
- Rehearsal over every 2025 week with per-week point-in-time cutoffs;
  rehearsal outputs live under a `rehearsal/` subprefix and never enter the
  evidence ledger.

### Excluded

- Any change to V4, production R2, Neon production branch, web schemas,
  publication, market data, or the frozen candidate's design/config/parents.
- Phase 5 execution (actual 2026 freezes/scoring) — separate authorization
  after this contract implements.
- Challenger research, recalibration, or any candidate modification (Phase 6).

## Affected Components and Contracts

- `src/cks_picks_cfb/ratings/score_models.py` — add
  `load_score_model(record) -> ScoreModel` (pure addition; frozen-run behavior
  unchanged).
- `conf/ratings/shadow_operations_v1.yaml` — new pinned contract
  (model/prediction/benchmark refs, V4 pairing source, gates).
- Neon preview `catalog` schema — optional dataset-version rows (append-only).
- `docs/planning/roadmap.md`, `docs/modeling/rating_system_requirements.md`,
  `docs/plans/index.md` — authority updates on completion.

## Implementation Tasks

### Task 1 — Frozen-model reconstruction with exact oracle

**Files:** `src/cks_picks_cfb/ratings/score_models.py`,
`tests/ratings/test_shadow.py`

**Changes:** Add `load_score_model` rebuilding `ScoreModel` from a
`model_record` row (feature-name-ordered coefficients, covariance,
dispersion). Round-trip property test on synthetic records.

**Acceptance criteria:** Reconstructed `final_refit` and
`locked_confirmation` models re-predict the frozen predictions-ref rows with
`|Δ| ≤ 1e-9` on means/SDs/intervals for every (game, target) row of the
corresponding fold; feature-name order verified against `FEATURE_NAMES`.

**Validation:** Focused unit tests + one Preview integration check reading
refs `071f4de1…`/`75e9a9cc…`.

### Task 2 — Pregame freeze CLI

**Files:** `scripts/pipeline/build_rating_shadow_freeze.py`,
`conf/ratings/shadow_operations_v1.yaml`,
`src/cks_picks_cfb/ratings/shadow.py`

**Changes:** Given `--season --week --as-of`, explicit Silver parent ref URIs
(byplay/drives/games/game_outcomes/reconciled_team_game from the current
preview prepare-week build), and the pinned config: rebuild observations →
adjusted snapshots → team states with the unchanged Phase 1 v3 / Phase 2 v2
equations, assemble the slate's prediction frame, predict with the frozen
`final_refit` model, and write `freeze-manifest.json` + `predictions-ref.json`
under the run prefix.

**Acceptance criteria (all fail-closed):**

- `as_of` strictly before the slate's earliest kickoff; manifest records
  kickoff bounds and per-game cutoff proof.
- Every scheduled slate game has two non-null pregame states; predictions
  carry positive SDs and finite intervals; `actual_*` columns are null.
- One active freeze per (season, week): a second differing freeze attempt
  collides immutably; identical rerun no-ops byte-for-byte.
- Manifest records: parent refs + checksums, model ref + stage + sha, coverage
  stats (scheduled/predicted/missing), and `normal_coverage_slate`
  classification (full FBS slate, no abnormal openers byes-only weeks).
- Code/config commit-identity checks like the sibling research CLIs.

**Validation:** Unit tests with the hand-built league fixtures; timing,
dedupe, missing-state, and outcome-leakage edge cases.

### Task 3 — Postgame scoring CLI + evidence ledger

**Files:** `scripts/pipeline/build_rating_shadow_score.py`,
`src/cks_picks_cfb/ratings/shadow.py`

**Changes:** Given `--season --week` and the frozen week's manifest: join
authoritative completed outcomes (Silver `game_outcomes`), pair V4 —
rehearsal mode reads the benchmark replay ref; prospective mode reads the V4
production run's frozen predictions artifact in R2 (uri pinned in the manifest
at freeze time) — compute paired metrics via the existing evaluation module
(no quality gate in Phase 4; gates are operational only), and append
`rating_shadow_evidence_v1` rows plus a score report.

**Acceptance criteria:** Only games with both a pre-kickoff freeze record and
authoritative outcomes are scored; unpaired-V4 rows are recorded, never
silently dropped; re-scoring the same week collides or no-ops (no ledger
mutation); every ledger row carries freeze-manifest sha, outcome ref, and V4
source uri/sha.

**Validation:** Unit tests on fixtures + integration against rehearsal
outputs.

### Task 4 — Full-season 2025 rehearsal (exact-match oracle)

**Files:** `scripts/pipeline/run_rating_shadow_rehearsal.py`,
`tests/ratings/test_shadow.py`

**Changes:** Load the certified historical parents once; for **every** 2025
week, compute the week's cutoff (earliest kickoff − 1h), assemble the
point-in-time pregame frame in-memory, predict with the reconstructed
`locked_confirmation` model, freeze, then score. Per-week efficiency: derive
pregame snapshots from the shared kickoff-ordered observation set rather than
19 full rebuilds.

**Acceptance criteria:**

- Every week's predictions match the frozen `locked_2025` rows on identical
  (season, game_id, target) coverage with `|Δ| ≤ 1e-9` on means/SDs/intervals.
- Scorer executes per week against benchmark V4 `f4ec062c…` with complete
  pairing coverage; all rehearsal outputs land under `shadow-v1/…/rehearsal/`
  and are marked `rehearsal_only: true`.
- A single rehearsal summary report records per-week timing, coverage, and
  oracle results; `all_checks_passed` true is the Phase 4 exit gate.

**Validation:** Full run in Preview; deterministic rerun byte-identity of the
summary.

### Task 5 — Preview catalog registration (opt-in)

**Files:** `scripts/pipeline/build_rating_shadow_freeze.py` (flag),
`src/cks_picks_cfb/data/catalog.py` (reuse)

**Changes:** `--register-catalog` appends dataset-version rows for
freeze/predictions/evidence datasets to the **preview** Neon `catalog` schema
only.

**Acceptance criteria:** Absent flag → zero Neon interaction; production
branch and web roles are structurally unreachable; registration failure fails
the run before any ledger append.

### Task 6 — Authority closure

**Files:** `docs/planning/roadmap.md`,
`docs/modeling/rating_system_requirements.md`, `docs/plans/index.md`, session
log.

**Acceptance criteria:** Roadmap marks Phase 4 Implemented with rehearsal
evidence (run id, SHAs); Week 1 declared plan-eligible for Phase 5 iff
`all_checks_passed`; plan index updated.

## Testing Strategy

- Unit: model round-trip; manifest collision/dedupe; cutoff-boundary timing;
  missing-state and unpaired-V4 recording; outcome-leakage rejection.
- Integration (Preview storage): freeze→score cycle on fixtures; rehearsal on
  the real historical parents; byte-identical reruns.
- Full gates: `uv run pytest -q`, scoped Ruff, `make contracts-check`,
  `uv run mkdocs build --strict`, `git diff --check`.

## Risks and Edge Cases

- **Rehearsal runtime (all 2025 weeks):** mitigated by the shared-observation
  per-week design; if still heavy, an amendment may parallelize weeks without
  changing semantics.
- **2026 Silver readiness:** freeze depends on the weekly preview
  `prepare-week` build existing and being pinned by explicit refs; the freeze
  CLI must fail closed when parents are stale (missing scheduled games).
- **V4 production-run availability:** production publishes in approval-gated
  mode; the prospective pairing uri is pinned at freeze time and verified by
  checksum at score time, with unpaired rows recorded rather than fabricated.
- **Float serialization:** oracle tolerance 1e-9 absorbs parquet/JSON
  round-trips; exact byte equality is required only for rerun determinism, not
  across serializations.
- **Catalog writes:** preview-only, opt-in, append-only; any ambiguity fails
  closed.

## Definition of Done

- [ ] Tasks 1–5 implemented with all acceptance criteria and focused tests
      passing.
- [ ] Full-season 2025 rehearsal passes the exact-match oracle with
      `all_checks_passed: true` and a deterministic rerun.
- [ ] Validation battery green (full suite, Ruff, contracts, MkDocs,
      `git diff --check`).
- [ ] Authority docs, plan index, and session log record refs, checksums, and
      Phase 5 eligibility.
- [ ] No production, V4, publication, or market surface touched; candidate v1
      unchanged.

## Amendments

### 2026-08-26 — Correctness remediation before materialization

Implementation review found mechanical contract gaps in the initial draft:
Parquet serializes frozen sequence fields as strings; the proposed 2026 state
seed recomputed a prior terminal with fallback scaling; the V4 reader assumed
a lake ref rather than the authoritative production prediction-run
manifest/CSV; and run-stamped operational prefixes did not establish one
canonical weekly freeze.

The implementation therefore retains the candidate and all Phase 3 equations,
but tightens the Phase 4 mechanics as follows:

- Canonical operational artifacts are one freeze and one final score report at
  `ops/season=<season>/week=<week>/`; immutable per-week evidence replaces the
  ambiguous append-only ledger wording.
- Candidate model loading verifies the candidate-manifest SHA, design and code
  identities, exact refs, model chronology, finite parameters, PSD covariance,
  and positive NB2 dispersion. It accepts native or safely decoded Parquet
  sequence fields only.
- Current-season states rebuild from the complete certified 2021–2025
  snapshots and terminals plus new current-season observations. No arbitrary
  historical seed row is used.
- Prospective V4 pairing requires a production run ID. A read-only production
  Neon query verifies frozen/scored state and timestamp; a read-only production
  R2 read verifies the immutable manifest/CSV checksums and normalizes V4
  margin/total predictions. No production write, schema, activation, or
  publication action is introduced.
- Canonical final scoring requires complete outcomes and complete V4 pairing.
  Incomplete attempts produce an immutable diagnostic only. Evidence rows carry
  freeze, outcome, V4, source-kind, and scoring lineage.
- The 2025 rehearsal rebuilds its 2025 observations/snapshots from the Phase 1
  audit's pinned historical parents, combines them with certified earlier
  seasons, and runs the common state assembly before oracle comparison.

These are mechanical safety corrections within the approved isolation,
candidate, and acceptance boundaries. Preview materialization remains
prohibited until the corrected code is committed and local validation passes.
