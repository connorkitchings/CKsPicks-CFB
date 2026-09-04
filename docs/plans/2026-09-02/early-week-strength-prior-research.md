# Early-Week Strength-Prior Research

- **Status:** In Progress
- **Created:** 2026-09-02
- **Planner:** Sol
- **Approval source:** User approved the plan and said “Proceed” in Codex on 2026-09-02.
- **Implementation log:** `session_logs/2026-09-04/01-early-week-strength-prior-research-continuation.md`
- **Commit policy:** Separate plan commit required; implementation commits remain user-controlled.

## Goal

Develop two isolated, football-only research tracks that correct the early-week strength-gap blind spot exposed by Alabama–East Carolina, while retaining the published V4 Week 1 artifact and all production behavior unchanged.

Success means each track is reproducible, point-in-time classified, market-free, and produces immutable diagnostics for Games 1–3. The rating track may advance only when the existing R2 gates pass; the direct track remains research-only until independently supported by a later promotion contract.

## Current State

- Production V4 run `2026w1-b2c739321e5d` correctly stored Alabama `+0.1656` (home margin) against East Carolina and a `-28.25` home line. This is not a UI or sign-convention error.
- Its `game_1` direct-CatBoost route has zero completed-game evidence, so all empirical-Bayes current weights are zero. The route uses prior-season performance rates and only neutral-site/conference context; it has no admitted roster, recruiting, coaching, talent, or conference-strength input.
- The strict V4 reference has only `prior_core`. Existing historic preseason inputs have 2026 capture timestamps/end-of-season fields and are explicitly reconstructed evidence; they cannot support activation, locked validation, refit, readiness, or publication.
- The existing R2 roster already defines four context Ridge candidates but skips them until an immutable context-admission report passes. R1 is certified at `r1-full-corpus-20260831-5f2a384`: its immutable coverage report sets `tournaments_permitted: true`, so fresh context admission is the remaining R2 gate.

## Proposed Approach

Use a shared, source-family admission boundary before either model experiment. The normalized source contract is one row per `season`, `team`, and family, with every family feature, `effective_at`, `retrieved_at`, source identity, and an explicit `feature_track` of `strict` or `reconstructed`.

Admit only complete football-only family data: returning production, transfers, recruiting, coaching, and optional talent. Require at least 90% FBS team-season coverage per season, canonical team mapping, no duplicate keys, finite numeric values, no market-named fields, and an authentic pre-kickoff 2026 capture. A family that fails is omitted wholesale; no row-level fill or fallback is allowed.

Run two independent experiments from the admitted context. Do not claim a shared winner: R2 evaluates preseason team-state priors, while the direct track evaluates Game 1–3 margin/total predictions. Reconstructed data can produce research reports only. Strict data is required before a later selection, locked test, refit, or promotion proposal.

## Scope

### Included

- Provenance-preserving offseason-context normalization and admission reports.
- A context-enabled R2 prior tournament after R1 certifies the foundation.
- A parallel direct early-game research tournament with additive context variants.
- Non-market strength-gap and 2026 Alabama–East Carolina input/output diagnostics.

### Excluded

- V4 changes, production artifacts, Neon publication state, web display behavior, markets as features or gates, and any current-season outcome use.
- External SP+/FPI/FEI sources, team-ID features, manual prediction overrides, and activation/promotion of either research result.

## Affected Components and Contracts

- `src/cks_picks_cfb/preseason_features.py` and `scripts/pipeline/build_v4_preseason_feature_reference.py` become the shared family schema and strict/reconstructed feature-reference boundary.
- A new offseason-context admission module/CLI and focused tests publish checksummed family coverage, effective-time, source, and track decisions.
- `src/cks_picks_cfb/ratings/priors.py`, `scripts/pipeline/build_r2_prior_tournament.py`, and `conf/ratings/successor_v2_tournaments.yaml` consume a passing admission reference to enable only the existing `continuity_ridge_alpha_*` candidates.
- `scripts/pipeline/generate_game_ordinal_candidates.py` and `scripts/pipeline/evaluate_game_ordinal_predictions.py` add the direct reconstructed-research path and its immutable report contract.

## Implementation Tasks

### Task 1 — Build and seal offseason-context admission

**Changes:**

- Define the normalized family schema and a source manifest binding each source DatasetRef, required fields, source semantics, and provenance.
- Add a CLI that validates family-by-family coverage for the permitted seasons (`2015–2019`, `2021–2025`) and an authentic 2026 pre-kickoff capture. It emits one immutable admission report plus normalized context ref with per-family `strict`/`reconstructed` status and failure reasons.
- Reuse the strict V4 family rules. Preserve `prior_core`; expose only complete admitted additive families. Talent is optional and omitted when unavailable.

**Acceptance criteria:**

- The report rejects 2020, missing/late evidence, duplicate team-season rows, incomplete families, market fields, and unverifiable team mappings.
- The current known historic inputs resolve as `reconstructed`, never strict; the authenticated 2026 capture is separately identified.

### Task 2 — Run the direct early-game research track

**Changes:**

- Generate Game 1–3 spread and total candidates using deterministic additive variants in this order: `prior_core`, returning production, transfers, recruiting, coaching, then optional talent.
- Evaluate direct Ridge, direct CatBoost, points-derived Ridge, and points-derived CatBoost against the frozen V4 baseline on the existing 2022–2024 temporal folds. Record MAE, RMSE, bias, paired bootstrap, seasonal stability, per-family coverage, and the selected feature set for every route.
- For reconstructed input, use only the existing research-report mode; block locked-2025 evaluation, refit, bundle creation, readiness, and publication.

**Acceptance criteria:**

- Candidate generation is strictly pre-season/fold-point-in-time, excludes 2020 and every market-derived field, and cannot silently omit a required feature from a selected variant.
- The report includes non-market large-strength-gap diagnostics based on pregame internal-state deciles and an Alabama–East Carolina provenance/output diagnostic. Neither is a market-derived selection or override rule.

### Task 3 — Enable the R2 context-prior research track

**Changes:**

- Require an admission-report/ref pair in the R2 runner. Enable the existing `continuity_ridge_alpha_0_1`, `1`, `10`, and `100` candidates only for admitted context; retain the present non-context roster as baseline.
- Fit context models within each expanding fold only, join target-season context by canonical team, carry coverage/provenance into metrics, and retain neutral fallback for teams without an admitted row.
- Run only after the R1 certificate says `tournaments_permitted: true`; write all output beneath the Preview research prefix. A failed admission or R2 gate produces a failed immutable report and does not authorize R3.

**Acceptance criteria:**

- R2 still observes its existing selection seasons, 2020 exclusion, 1% full season non-regression gate, and 0.5% simplicity tie rule.
- No context candidate can run from caller flags, incomplete data, a reconstructed report presented as strict, or target/future-season rows.

### Task 4 — Verify isolation and document the result

**Changes:**

- Add shared diagnostics that make feature track, source refs, family coverage, and strength-gap segment metrics visible in both research reports.
- Update the rating/modeling authority docs with the admitted-family contract, reconstructed restrictions, and the fact that V4 remains the champion.

**Acceptance criteria:**

- Tests prove neither CLI can write V4, production, prediction-run, or web publication artifacts; output is deterministic under an immutable URI.
- The final session log records report URIs, validation results, R1 dependency state, and whether each family/track passed admission.

## Testing Strategy

- Unit-test normalization, canonical mapping, forbidden-field rejection, source/effective-time/coverage gates, family omission, and strict versus reconstructed classification.
- Test R2 context candidates require a passing admission ref and remain fold-isolated. Test direct variants are additive, complete, reproducible, and blocked from locked/refit/publish on reconstructed evidence.
- Run focused preseason, V4, game-ordinal, ratings, and production-boundary tests; then `uv run pytest -q`, scoped Ruff, contract validation, MkDocs, and `git diff --check`.

## Risks and Edge Cases

- A shared 2026 snapshot does not make historic data strict. Historical source semantics/effective time must be documented or the family remains research only.
- The R1 certificate is an external dependency for R2. Direct research may proceed independently but may not bypass its reconstructed restrictions.
- Large-strength-gap diagnostics may expose errors but cannot become manual overrides or use a bookmaker line as truth.

## Definition of Done

- [ ] Immutable source/admission refs classify every requested family and track.
- [ ] Direct and R2 research reports are written or explicitly fail closed with immutable diagnostics.
- [x] V4, the published Week 1 run, and production/publication state are unchanged.
- [x] Required validation and documentation/session log updates pass.
- [ ] Plan status is updated to `Implemented` or `Superseded` with evidence.

## Amendments

### 2026-09-03 — Reconstructed 2026 diagnostic authorization

The user authorized one immutable, Preview-only Alabama–East Carolina scorer
after historical selection. It may train the selection-fixed recipe only to
emit a research diagnostic; it cannot create a bundle, affect locked testing,
read 2026 outcomes or market fields, enter readiness, or alter publication.

### 2026-09-03 — Context-materialization diagnosis and repair

The first corrected immutable admission report is
`artifacts/research/rating-successor-v2/early-week-context-20260903-0455595-r2/admission-v2-report.json`.
It admits reconstructed `recruiting` and `coaching`, rejects transfers and
talent for their declared evidence gaps, and rejects returning production at
0% coverage in every required season. This was diagnosed as a local adapter
defect, not a provider coverage gap: CFBD's generated client serializes the
returning fields in camelCase (`totalPPA`, `percentPPA`, and `*Usage`) while
the adapter accepted only snake_case. The repaired adapter has read-only
coverage of 91.9%–93.8% in every required season. The failed immutable report
is preserved; after the repair is committed, rematerialize under a new prefix
and require the planned three-family admission before direct or R2 execution.

### 2026-09-04 — Certified-R1 handoff and code-bound admission

The R1 coverage report at
`artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json`
now permits tournaments. Commit the returning-production adapter and R2
lineage repair before materializing a new Preview-only context prefix bound to
that code SHA. The new admission must preserve reconstructed provenance and
admit only returning production, recruiting, and coaching at the existing 90%
season-coverage threshold; transfers and talent remain excluded with explicit
diagnostic reasons. This unblocks only reconstructed direct/R2 research reports,
never locked validation, refit, bundle creation, readiness, publication, or V4.
