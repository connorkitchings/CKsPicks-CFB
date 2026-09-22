# 2026 v5 Shadow Rebuild Diagnostic (Preview-only)

- **Status:** Implemented 2026-09-22 — Task 5 closed under [Contract 01](../2026-09-13/01-v4-feature-v5-diagnostic-closure.md): W2 shadow scored against the Week 2 close outcomes (`cb75ca88…`); pooled W1+W2 verdict rendered — shadow spread 35-56-1 on 91 graded (38.46%) < 45% → **cause not confirmed**; predictions value-identical to official on all 100/100 games, refuting the feature mismatch as the underperformance cause. Full record: [`docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md`](../../../research/2026-09-22-v4-feature-v5-diagnostic-closure.md).
- **Created:** 2026-09-10
- **Planner:** Sol
- **Approval source:** Original: user go-ahead 2026-09-10 (→ STOPPED, Amendment 1). Amendment 1: user re-approval 2026-09-10 (→ STOPPED on Task 2 byte-parity: code drift, zero writes). Amendment 2: user re-approval 2026-09-10, Amendment 2 (explicit authorization of this exact plan path for a fresh Terra run).
- **Implementation log:** `session_logs/2026-09-10/11-v5-shadow-rebuild-implementation-two-tier.md` (Tasks 1–4 + partial Task 5; `session_logs/2026-09-10/09-v5-shadow-rebuild-implementation-fresh.md` and `session_logs/2026-09-10/07-v5-shadow-rebuild-implementation.md` are stopped-run evidence, read-only; `session_logs/2026-09-10/06-v5-shadow-rebuild-planning.md` is the planning log); Task 5 closure under Contract 01: `session_logs/2026-09-22/02-v4-feature-v5-diagnostic-closure.md`
- **Commit policy:** Separate plan commit (production-adjacent diagnostic; difficult-to-reverse conclusions must stay reviewable)
- **Supersedes (as executable plan):** `docs/plans/2026-09-09/rebuild-2026-predictions.md` (retained as the root-cause record; its Step 5 is not executable — see Current State §4)

## Goal

Determine whether the 2026 V4 underperformance (~36% spread vs ~51% in 2025) is caused by the v4/v5 feature mismatch, by rebuilding **artifact-level** `point_in_time_matchups_v5` Gold and shadow predictions for 2026 Weeks 0–2 in **Preview only** and scoring them against final outcomes.

Observable success criteria:

- For each week, a v5 shadow Gold artifact whose manifest reads `dataset=point_in_time_matchups_v5`, `feature_track=strict`, with the pinned preseason ref below.
- Shadow prediction + scored artifacts per week in Preview R2, produced with pre-kickoff inputs only.
- A verdict table (shadow spread/total win rate vs official record) with the pre-registered kill criterion applied (§Definition of Done).
- **Zero** writes to production Neon, Preview serving tables, or frozen/scored runs.

## Current State

### 1. Official 2026 record (immutable, untouched by this plan)

| Week | Prod run | State | Games |
| --- | --- | --- | --- |
| 0 | `2026w0-55de0317120d` (plus `2026w0-79ec2aebcb00` published, latest-wins resolves to scored) | scored | 8 |
| 1 | `2026w1-b2c739321e5d` | scored | 43 |
| 2 | `2026w2-43b25511a100` | **frozen** (2026-09-10, grading authority for Tuesday close) | 49 |

Verified 2026-09-10 via `prediction_runs` + `/api/health` (see planning log). The frozen Week 2 run and scored Weeks 0–1 remain the official pre-kickoff betting record regardless of this diagnostic's outcome.

### 2. Feature-mismatch evidence (verified, not assumed — corrected by Amendment 1)

All four 2026 prod runs bind `dataset=point_in_time_matchups` (no preseason), but via **two different build paths**:

| Week | Matchups version | Content SHA | Manifest `as_of` (pin for shadow) | Build path + parents (all present in R2) |
| --- | --- | --- | --- | --- |
| 0 | `74ffdbbff759459734a73e30` | `1f32fc0f…` | `2026-08-15T14:42:00Z` | assembler: wide core `d1c5efd8` + baselines `ec13aef8` (schema v4) |
| 1 | `30ac8b5d37719160ff9d751c` | `2f7566f8…` | `2026-09-03T04:00:00Z` | `build_regime_features.py` + baselines: team_features `6d6f4da2` + baselines `0e6403e2` (schema v3); team_features parents: temporal `ef3380e0` + schedule `70aef191` |
| 2 | `9b7bc4789f39f584055d01c6` | `64393952…` | `2026-09-08T15:35:00Z` | `build_regime_features.py` + baselines: team_features `bda6032a` + baselines `0e6403e2` (schema v3); team_features parents: temporal `ace30e9c` + schedule `9432081e` |

Original publish cutoffs (for Task 4 shadows, recovered from prod `prediction_runs`/`data_as_of`): W0 `2026-08-20T13:19:14Z` (scored run; market `e3f984c4`), W1 `2026-09-03T05:00:00Z`, W2 `2026-09-08T17:50:00Z`.

V4 bundle `week0-2026-v4-strict-20260818-r2` was trained on `point_in_time_matchups_v5` (2025 benchmark `fe55e75884c7665527e740d3`, parents include `v4_preseason_team_features@8c47f6d5`).

### 3. Pinned preseason reference (verified in R2)

- URI: `lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/manifest.json`
- Coverage: `feature_track=strict`, `activation_eligible=True`, `as_of=2026-08-17T16:00:00Z` — precedes every week cutoff above, so joining it is point-in-time safe.
- The assembler (`scripts/pipeline/assemble_model_ready_features.py:102-155`) enforces dataset name, required columns, no duplicate season/team, track match, full home-team coverage, and activation eligibility; any violation fails closed.

### 4. Why the 2026-09-09 Draft is not executable as written

- Step 5 issues `SET state='superseded'` — **no `superseded` state exists** in the schema (replay evidence: runs remain `scored`, web resolution is latest-wins).
- Step 5 hand-edits `prediction_runs`/`current_week`, bypassing `python -m cks_picks_cfb.ops`, leases, and `ops.activation_history`.
- It does not account for Week 2 now being **frozen** (immutable grading authority) or the two-path build lineage (§2, corrected by Amendment 1).

### 5. Tooling (flags verified 2026-09-10)

- `assemble_model_ready_features.py`: `--core-ref-uri`, `--baselines-ref-uri`, `--preseason-features-ref-uri`, `--feature-track strict`, `--as-of`, `--output-ref-uri`, `--environment` (+ `--markets-ref-uri`, `--skip-catalog-registration`).
- `generate_weekly_bets.py`: `--config conf/weekly_bets/v4_2026.yaml`, `--year/--week`, `--as-of`, `--dataset-refs-uri`, `--run-id`, `--run-state preview`, `--upload-artifact`.
- Market lines are reused verbatim from prod `input_dataset_refs` (W0 `07336aaa`/`e3f984c4`, W1 `b273e83d`, W2 `459c80d0` + quotes `ede4a9a7`) — never re-captured.

## Proposed Approach

**Option A (selected): Preview-only artifact-level shadow diagnostic.** Rebuild v5 Gold and shadow predictions as new immutable Preview R2 artifacts, score at artifact level, compare. No new `prediction_runs`/`predictions`/`prediction_grades` rows in any database, no `current_week` moves, no freeze/score state transitions. Rationale: answers the causal question with zero risk to the official record; production-swap implications (re-freeze, relabeling) are a separate decision that requires its own contract.

**Option B (explicitly deferred):** any production activation of rebuilt predictions. Excluded from this contract; needs a separate approved contract and user approval after the diagnostic verdict.

## Scope

### Included

- Per-week (0, 1, 2) v5 Gold reassembly in Preview with pinned cutoffs and preseason ref.
- v4 parity-gate reassembly before any v5 work (Task 2).
- Shadow `generate_weekly_bets` runs (`--run-state preview`, distinct `shadow-2026-v5-w<N>` run IDs) reusing exact prod market refs.
- Artifact-level scoring via `score_weekly_bets.py` (`--from-artifact`, final-outcomes ref) + verdict table.
- Planning/implementation session logs; `docs/plans/index.md` entry.

### Excluded

- Any write to production Neon or production R2 prefixes.
- Any write to Preview serving tables: no `publish_to_db.py`, no `freeze_week.py`, no `score_to_db.py`, no `current_week` changes. (Preview catalog registration of new Gold versions is permitted; it is research metadata, not serving state.)
- No changes to the V4 bundle, inference code, Phase 3+ research, web app, or contracts.
- No re-capture of market lines or Bronze; no new provider calls (all inputs already immutable in R2).
- No Week 3+ work; no production swap (Option B).

## Affected Components and Contracts

- `scripts/pipeline/assemble_model_ready_features.py` (invoked, not modified)
- `scripts/pipeline/generate_weekly_bets.py` (invoked with `--dataset-refs-uri`, not modified)
- `scripts/pipeline/score_weekly_bets.py` (artifact-level scoring only, not modified)
- R2 (reads): Gold parents, preseason ref, market refs, games `5dabf61a`; R2 (writes): `artifacts/preview/...` shadow outputs only
- Neon: read-only SELECTs for verification; Preview catalog inserts via assembler (no serving-table writes)
- Ops contract: this diagnostic deliberately stays **outside** `python -m cks_picks_cfb.ops` because it creates no runs in the state machine; any future state-machine work needs its own contract

## Implementation Tasks

### Task 1 — Recover per-week refs (all verified present; no rebuild needed)

**Changes:**

- W0: wide core `lake/gold/dataset=point_in_time_matchups_core/version=d1c5efd877a8720a9250f013/manifest.json` + baselines `lake/gold/dataset=baseline_predictions_oof/version=ec13aef8a0f842867bffb9dc/manifest.json`.
- W1: team_features `lake/gold/dataset=point_in_time_team_features/version=6d6f4da2d6d4b329cc322fbd/manifest.json` + baselines `lake/gold/dataset=baseline_predictions_oof/version=0e6403e2f7250c0385f9aefa/manifest.json` (+ temporal `ef3380e0` / schedule `70aef191` recorded as team_features parents for provenance).
- W2: team_features `lake/gold/dataset=point_in_time_team_features/version=bda6032a9dc8041d500c0924/manifest.json` + baselines `0e6403e2…` (same baselines ref as W1) (+ temporal `ace30e9c` / schedule `9432081e`).
- Reuse exact prod market snapshot/quote refs per week (§Current State §5) and games ref `5dabf61a15b3745ff3a595a4`. Original builder argv recovered from Preview `ops.pipeline_steps` (W1 prepare `c9b80bf1…`, W2 prepare `3eb4c566…`): `build_regime_features.py --matchups-ref-uri …/temporal_matchups_ref.json --schedule-ref-uri …/schedule_2021_2026_ref.json --baselines-ref-uri artifacts/preview/refs/history/baselines-selection.json --as-of <pinned cutoff> --environment preview`.

**Acceptance criteria:**

- Every input ref resolves in R2 with matching content SHA before assembly.
- Cutoff audit: each input manifest `as_of` ≤ that week's first kickoff (W0 Thu 2026-08-29, W1 Thu 2026-09-03 evening, W2 Fri 2026-09-11).

**Validation:**

- `storage.exists` + SHA match per ref; `git diff --check` (no worktree changes expected).

**Stop rule:** if any week cutoff audit fails or a required ref is unrecoverable, stop that week (continue others) and record the gap. Do not substitute newer inputs.

### Task 2 — Two-tier parity gate (replaces byte-parity; Amendment 2)

Byte-parity is stale relative to HEAD: the W0 rerun from immutable parents produced `cc6b1a03…` vs prod `1f32fc0f…` due to post-08-15 code drift (5 extra all-NaN baseline columns retained by `attach_baseline_predictions`; 16 all-missing `*_prior_*` columns coerced None(object)→NaN(float64) by the assembler missingness step). Lineage is intact (same rows/keys/parents). The gate below proves drift is inference-inert instead of demanding byte identity.

**Tier 1 — lineage confinement (per rebuilt Gold vs its prod counterpart):**

- Same row count, same `(season, game_id)` keys, same SHA-verified parents.
- Column-diff confinement, exactly two permitted classes (any other diff → stop whole diagnostic):
  - (a) Columns in rerun but absent in prod must be **disjoint from the bundle feature union** (329 features across all 10 routes of `week0-2026-v4-strict-20260818-r2`, enumerated 2026-09-10; the inference loader `_predict_ref` reads only listed features and ignores extras) **and** all-null in that week's slice.
  - (b) Columns in both with differing values must be all-missing in **both** frames with only a None↔NaN representation change (semantic-null equivalence asserted per column).
- W0 subject already exists: `c89b4567…` (`artifacts/preview/shadow-2026-v5/w0-parity-point_in_time_matchups_ref.json`) — reuse it; its enumerated diffs (5 extra non-bundle all-NaN cols; 16 None↔NaN all-missing cols) are the reference confinement pattern. It is quarantined: never a Task-3+ input except via the Tier-2-cleared path below.

**Tier 2 — prediction-level control (per week):**

- Run `generate_weekly_bets.py` on the Tier-1-cleared rebuilt v4 with the **exact prod market refs**, the **original publish AS_OF** (W0 `2026-08-20T13:19:14Z`, W1 `2026-09-03T05:00:00Z`, W2 `2026-09-08T17:50:00Z`), same bundle + `conf/weekly_bets/v4_2026.yaml`, `--run-state preview`, run ID suffix `-v4control`, `--upload-artifact`.
- Require **identical parsed float values** (spread + total, every game) vs the official prod predictions artifact. Formatting-only differences must be proven value-identical and recorded; any value mismatch stops the whole diagnostic.
- Rationale: a match proves current-code outputs equal original-code outputs on identical inputs, so the Task-4/5 shadow-vs-official comparison isolates the feature effect with zero code-effect confounding.

**Per-week sequencing:**

- W0: Tier 1 on existing `c89b4567` → Tier-2 control → Task 3.
- W1/W2: exact `build_regime_features.py` rerun (Amendment 1) → Tier 1 → Tier-2 control; then no-baselines rerun → equivalence wide core → assembler without preseason → Tier 1 + Tier 2 on that assembly (this is what proves the Task-3 v5 inputs clean) → Task 3.

**Acceptance criteria:**

- All three weeks clear Tier 1 confinement and Tier 2 exact-prediction control.

**Validation:**

- Confinement report per week (diff enumeration vs the two permitted classes); control prediction diff (must be empty); recorded in the log.

**Stop rule:** any week failing either tier stops the whole diagnostic (do not proceed to v5 for any week). Report which tier failed and the implicated columns/games.

### Task 3 — v5 shadow Gold assembly

**Changes (only after Task 2 clears both tiers for all three weeks):**

- W0: assembler with core `d1c5efd8` + baselines `ec13aef8` + `--preseason-features-ref-uri lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/manifest.json --feature-track strict`, with `--as-of 2026-08-20T13:19:14Z` (Amendment 2: must dominate the 08-17 preseason parent recency while staying pre-kickoff; the assembler does not enforce parent recency, so this is pinned explicitly).
- W1/W2: assembler with `--core-ref-uri` = the Tier-2-cleared path-equivalence wide core, `--baselines-ref-uri` = `0e6403e2…` manifest, same preseason ref and `--feature-track strict`, pinned `--as-of` (W1 `2026-09-03T04:00:00Z`, W2 `2026-09-08T15:35:00Z`, both already dominate 08-17), `--environment preview`.

**Acceptance criteria:**

- Each output manifest reads `dataset=point_in_time_matchups_v5`, `schema_version=point_in_time_matchups_v5`, `model_ready_gold=v5`, parents = (core, baselines, preseason `8c47f6d5`).

**Validation:**

- Manifest assertions per week; assembler fail-closed gates (coverage/eligibility/track) must pass unmodified.

### Task 4 — Shadow predictions with frozen market refs

**Changes:**

- Per week, run `generate_weekly_bets.py --config conf/weekly_bets/v4_2026.yaml --year 2026 --week N --as-of <original publish AS_OF> --dataset-refs-uri <new v5 refs + exact prod games/market refs> --run-id shadow-2026-v5-w<N> --run-state preview --upload-artifact`.
- Pinned original publish cutoffs (recovered from prod): W0 `2026-08-20T13:19:14Z`, W1 `2026-09-03T05:00:00Z`, W2 `2026-09-08T17:50:00Z`. The shadow `--as-of` must equal the original per week (never now).

**Acceptance criteria:**

- Three uploaded Preview prediction artifacts, 8/43/49 games, `--run-state preview`, no DB activation (confirm `prediction_runs` unchanged in both databases).

**Validation:**

- Row-count + game-ID coverage match the official runs; `prediction_runs` SELECT before/after shows no new rows.

**Stop rule:** cutoffs are now pinned, so this rule is retired unless a pinned value proves wrong (e.g. mismatched market capture) — then stop that week rather than inventing a cutoff.

### Task 5 — Artifact-level scoring and verdict

**Changes:**

- Score each shadow artifact with `score_weekly_bets.py --year 2026 --week N --run-id shadow-2026-v5-w<N> --from-artifact --outcomes-ref-uri <final outcomes ref> --upload-artifact`. Finals are complete and stable, so current final-outcomes refs (production pipeline-run `game_outcomes_ref.json` files) are grading-safe. **Do not run `score_to_db.py`.**
- Build the verdict table: shadow vs official spread/total win rate per week + pooled W1+W2 (n=92; report W0 n=8 with small-sample caveat, excluded from the verdict).

**Acceptance criteria:**

- Kill criterion (pre-registered): pooled W1+W2 shadow spread win rate ≥50% → mismatch confirmed as the cause. <45% → cause not confirmed; report overfit/season-effect/inference-bug as open hypotheses with the evidence. 45–50% → inconclusive; recommend next probe, no production discussion.

**Validation:**

- Independent recomputation of the table from the scored artifacts; `git diff --check`.

**Terra execution note (2026-09-10, resolved 2026-09-22):** W2 finals blocked
the pooled verdict at planning time. Resolved under
[Contract 01](../2026-09-13/01-v4-feature-v5-diagnostic-closure.md): the W2
shadow was scored against the Week 2 close `game_outcomes_ref.json`
(pipeline run `cb75ca881f3a49d5bd115c4fdeaa7dcb`, 49/49 coverage verified), the
pooled table rendered, and the kill criterion applied (38.46% < 45% → cause
not confirmed). Interim evidence (W0/W1 value-identity) was confirmed final:
v5 predictions are value-identical to v4 for all 100 W0–W2 games. See
implementation log `11-…` and the closure research report.

## Testing Strategy

- No product-code changes, so no new unit tests. Verification is gate-based: SHA parity (Task 2), manifest assertions (Task 3), coverage + no-DB-write checks (Task 4), recomputed verdict table (Task 5).
- Regression guard: `prediction_runs` row counts in both databases before/after (must be identical); `current_week` pointers unchanged; `git status` shows only plan/log/index changes.

## Risks and Edge Cases

- **Two build paths, not one:** W0 prod Gold came from the assembler (wide core + baselines, schema v4); W1/W2 came from `build_regime_features.py` (team_features + baselines, schema v3). The parity gate uses the exact builder per week; cross-path equivalence for W1/W2 is proven empirically in Task 2, not assumed.
- **Code drift is contained by design, not by luck:** post-build changes add only never-read columns (loader reads listed bundle features; extras ignored) or all-missing representation changes. Tier 1 confines the diff classes; Tier 2 proves output equality. Anything outside both stops the diagnostic.
- **Parent-recency labeling:** the assembler does not enforce that `--as-of` dominates parent recency; Task 3 pins W0 v5 `--as-of` to the publish cutoff so no parent is backdated.
- **W0 n=8** cannot carry a verdict; pooled W1+W2 (n=92) is the decision sample.
- **Shadow runs must never enter serving state**: enforced by never invoking publish/freeze/score-to-db and by distinct `shadow-` run IDs; verify with row-count checks.
- **2020 exclusion** is enforced by the assembler validation (`excludes_2020`); assert it on every v5 manifest.
- **Cost**: R2 reads of Gold parents + small writes; no provider calls, no Odds API spend.

## Definition of Done

- [x] Tasks 1–5 complete or stopped early per the stated stop rules with gaps recorded.
- [x] Verdict table published in the implementation log with kill criterion applied. (Pooled W1+W2 shadow spread 38.46% < 45% → cause not confirmed; closure log 2026-09-22/02 + research report.)
- [x] No new rows in `prediction_runs`/`predictions`/`prediction_grades` in either database; `current_week` untouched (SELECT evidence, both sessions).
- [x] Official record unchanged: W0/W1 scored, W2 frozen runs intact.
- [x] `git diff --check` clean; plan status updated to `Implemented` (2026-09-22).
- [x] `docs/plans/index.md` entry accurate for the final status.

## Amendments

### Amendment 3 — Ref-minting for unregistered-core parents (Terra, 2026-09-10, minor/technical)

**Reason:** At HEAD (`d79276d`), `build_regime_features.py --no-baselines` and the
assembler's trailing `register_dataset_version` fail in Preview catalog writes:
no executable schema is registered for `point_in_time_matchups_core_v1`
(`schema_contracts.py:1594`), and the catalog FK then rejects children of the
unregistered core. The immutable bytes + manifests ARE written by the builders
before registration, content-addressed and parent-linked.

**Approach (mechanics only, no architecture/scope/acceptance change):** output
ref-files minted byte-faithfully from the builder-written manifests (same 5-key
`DatasetRef` JSON the builders would have written) at the prescribed shadow
`--output-ref-uri` paths: W1 core `fa0f7c34`, W1 assembly `7210bd9a`, W2 core
`1906c44b`, W2 assembly `90398ae9`, W1 v5 `882f691f`, W2 v5 `4d89b391`
(W0 paths needed no recovery). Preview catalog rows for versions with
unregistered parents remain absent — permitted-but-optional research metadata;
all Tier/manifest assertions run against R2 bytes. No source, script, bundle,
or contract file was modified.

### Amendment 2 — Two-tier parity gate for code drift + W0 v5 as_of fix (Sol, 2026-09-10)

**Reason:** Fresh Terra run executed Amendment 1 faithfully and tripped the byte-parity gate honestly: the W0 assembler rerun from immutable parents produced `cc6b1a03…` vs prod `1f32fc0f…` (log `09-…`). Diagnosis: deterministic post-08-15 code drift, not lineage corruption — 5 extra all-NaN baseline columns retained by `attach_baseline_predictions`, 16 all-missing `*_prior_*` columns coerced None(object)→NaN(float64) by the assembler missingness step, plus manifest-only coverage additions. Sol verified against the bundle manifest that all 5 extra columns are disjoint from the 329-feature bundle union and that the inference loader (`model_bundle_v3.py:179-202`) reads only listed features and ignores extras; the 16 prior columns ARE bundle inputs, so inspection alone cannot clear them. Terra also caught that Task 3's W0 v5 `--as-of 08-15` would backdate the 08-17 preseason parent.

**Original approach:** Task 2 demanded byte-identical content SHAs for all weeks; any mismatch stopped the diagnostic as untrustworthy lineage.

**Revised approach:** Task 2 becomes two tiers — Tier 1 confines Gold diffs to the two enumerated drift classes (extra never-read all-null columns; all-missing None↔NaN columns), Tier 2 proves inference-inertness empirically via a prediction-level control (rebuilt-v4 predictions must exactly equal official predictions, same bundle/config/markets/cutoffs). W0 reuses existing `c89b4567` (quarantined except via the cleared path). Task 3 pins W0 v5 `--as-of` to the publish cutoff `2026-08-20T13:19:14Z`. Tasks 4–5, kill criterion, scope, and no-serving-write constraints unchanged.

**Impact:** The gate now distinguishes corrupt lineage (stop) from inert code drift (proceed with proof). Requires user re-approval (fresh Terra run) since acceptance criteria changed.

### Amendment 1 — Correct build-path lineage for W1/W2 (Sol, 2026-09-10)

**Reason:** Terra reconciliation (log `07-…`) proved the contract's §2 assumption false: W1/W2 parents `6d6f4da2`/`bda6032a` exist in R2 as `point_in_time_team_features` (LONG), and W1/W2 prod matchups were built by `build_regime_features.py` + baselines (schema v3), not the assembler. Sol spot-verified: 8 team_features versions in R2, as_of values match pinned cutoffs, and `build_regime_features.py:147-158` confirms the no-baselines branch emits wide `matchups_core`. Feeding LONG input to the assembler would fail closed on `unique_game_keys`, tripping the stop rule for the wrong reason.

**Original approach:** Task 1 declared W1/W2 core parents absent and prescribed a builder rerun to recreate them; Task 2 prescribed assembler reassembly for all three weeks.

**Revised approach:** Task 1 recovers all refs as-is (nothing missing; original builder argv + temporal/schedule parents baked in). Task 2 uses the exact builder per week (W0 assembler; W1/W2 `build_regime_features.py` rerun) plus a path-equivalence check that manufactures the wide W1/W2 cores Task 3 needs. Task 3's W1/W2 v5 assemblies consume those cores. Tasks 4–5, stop rules, kill criterion, scope, and no-serving-write constraints unchanged; original publish cutoffs for Task 4 baked in.

**Impact:** No architecture/scope/acceptance change; the diagnostic is executable as amended. Requires user re-approval (fresh Terra run) since the authorized mechanics changed.
