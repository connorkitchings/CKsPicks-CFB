# Modernization Verification Audit

- **Audited commits:** `9ac7490`, `2a2f9f9`
- **Baseline:** `ff8a71b`
- **Audit date:** 2026-08-23
- **Scope:** Repository-only; no R2, Neon, external-drive, training, bundle, or deployment I/O.
- **Verdict:** **Not verified**

## Executive assessment

The refactor has credible compatibility evidence: the isolated pre/post core
regression set is identical and passes, compatibility facades import, the new
weekly-helper and notifier tests pass, and web build/typecheck/publication tests
pass. It is not verified as complete because current quality gates fail and
several completion claims lack matching implementation or test evidence.

| Dimension | Assessment | Evidence |
|---|---|---|
| Accuracy | Partial | The `94`-test baseline/current structural set passes; 2020, point-in-time, storage-root, and fail-closed guards remain. The weekly CLI success path lacks integration evidence. |
| Completeness | Not verified | Phase 7 acceptance criteria fail; Phase 5 and Phase 6 claims are only partial or conflict with policy. |
| Modularity | Partial | Facades and packages improve seams, but several execution units remain large and the CLI retains orchestration. |
| Effectiveness | Not verified | Full tests pass, but lint, formatting, and warning-free requirements fail; Python contract parity is not actually checked. |
| General quality | Partial | Documentation and contract status overstate validation. This audit made no production-facing change. |

## Evidence and validation

| Check | Result |
|---|---|
| Baseline/core regression set | `94 passed` under `ff8a71b` |
| Current/core regression set | `94 passed` with the same test selection |
| Current focused modernization set | `112 passed` (storage, Silver, aggregation/byplay, preseason, weekly, ops, CLI tests) |
| Full Python suite + branch coverage | `381 passed, 2 skipped, 216 warnings`; total coverage `51%` |
| Python lint | **Fail**: two unused imports in `tests/test_generate_weekly_bets_cli.py` |
| Python format check | **Fail**: `contracts/validation.py` would be reformatted |
| Contract validation | Pass, but added Python checks are import/call smoke checks only |
| Docs build and whitespace check | Pass |
| Web lint/typecheck/build | Pass; build requires normal host permissions because Turbopack binds an internal port |
| Web publication boundary | `3 passed`; Node emits a module-type warning |
| Warnings-as-errors target | **Fail**: CatBoost/sklearn `DeprecationWarning` becomes an error |

Reproduce the principal checks:

```bash
PYTHONPATH=src:. .venv/bin/pytest tests/test_storage.py tests/test_silver_reconciliation.py \
  tests/test_aggregations_core.py tests/test_new_features.py tests/test_preseason.py -q
PYTHONPATH=src:. .venv/bin/pytest tests/test_game_ordinal_training.py -q \
  -W error::DeprecationWarning
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python contracts/validation.py
cd web && npm run lint && npm run typecheck && npm run build && npm run test:publication
```

## Phase traceability

| Phase | Grade | Evidence and disposition |
|---|---|---|
| 1 — Dependency & legacy hygiene | Verified | Dependencies moved to `research`; archived entrypoints have no maintained code callers. Remaining references are historical/planning documentation or explicit archive notes. |
| 2 — Storage & Silver | Partial | Facades and paired baseline/current tests pass. There is no full output differential for R2/Silver builders; R2 branch coverage is `25%`. |
| 3 — Features & recency | Partial | Focused packages retain facade imports and the paired set passes. Main units remain substantial, and no complete API/signature inventory proves all public symbols. |
| 4 — Preseason refinement | Partial | `preseason.py` is a facade and preseason regressions pass. No serialized-bundle or prediction-byte differential proves the documented equivalence claim. |
| 5 — Pipeline & ops | Partial | Weekly helper and notifier safety tests pass. The CLI still owns prepared-input/routing behavior, and no valid no-network CLI success path is tested. |
| 6 — Web UX | Partial | Market mode shows scores and `Final`; prediction mode shows grade chips. The contract requires grades in both modes but market mode deliberately excludes grade data. `WeekNav.tsx` is unchanged in the audited commits; no local mobile visual fixture exists. |
| 7 — Test coverage & quality gates | Incorrect | Claims of warning-free tests, passing lint/format, CLI integration coverage, and Python contract parity are unsupported. |
| 8 — Completion & hygiene | Incorrect | The modernization document declares all gates passing despite the current lint, format, and warning failures. |

## Findings

### P1 — Phase 7 quality-gate completion is false

`tests/test_generate_weekly_bets_cli.py:3` and `:5` contain unused imports, so
`ruff check .` fails. `contracts/validation.py` also fails
`ruff format --check`. This contradicts the Phase 7/8 completion claims in
`docs/planning/2026_codebase_modernization_and_refactoring_plan.md:183-201`
and makes the tree fail its Python CI gate.

**Remediation:** remove unused imports, format the validator, and record the
exact CI command results before declaring completion.

### P1 — CatBoost/sklearn forward compatibility is not fixed

The added filters in `src/cks_picks_cfb/models/regime_training.py:104-106` and
`:132-134` suppress `RuntimeWarning`, `UserWarning`, and `FutureWarning`; the
actual CatBoost/sklearn warning is a `DeprecationWarning` raised at prediction
through `src/cks_picks_cfb/models/game_ordinal_training.py:105-115`. The full
suite emits 216 warnings, and `-W error::DeprecationWarning` fails. sklearn
reports this fallback becomes an error in 1.8.

**Remediation:** use a compatible estimator integration or a narrow, tested
warning policy at the actual call boundary; do not broadly suppress unrelated
user/future warnings.

### P1 — The claimed CLI integration smoke test never executes inference

`tests/test_generate_weekly_bets_cli.py:12-38` tests only `--help` and a
missing config. It does not create synthetic Gold/schedule/market inputs, mock
storage/models, perform a successful prediction, validate CSV columns/order, or
exercise artifact collision behavior. This misses the contract requirement at
`docs/plans/2026-08-23/modernization-phases-5-8-completion.md:101-108`.

**Remediation:** add one no-network end-to-end CLI golden test with fake storage,
explicit dataset refs, routed predictions, and a temporary output path.

### P2 — Python “cross-stack contract validation” is only a smoke check

`contracts/validation.py:132-148` calls `schema_for("games", "v1")` and one
feature allowlist validation. It reads no Python field mapping and compares no
Python schema against canonical SQL/TypeScript definitions, so it cannot detect
the claimed drift. Existing SQL↔TypeScript checks remain useful; the new Python
alignment claim at `docs/planning/2026_codebase_modernization_and_refactoring_plan.md:190-194`
is overstated.

**Remediation:** define canonical field mappings and add positive plus deliberate
mismatch tests proving the validator fails on Python, SQL, or Drizzle drift.

### P2 — Weekly inference extraction is incomplete

`scripts/pipeline/generate_weekly_bets.py` remains 742 lines and directly
prepares Gold/market data and routes predictions. The new
`src/cks_picks_cfb/inference/weekly.py` is 332 lines, but the CLI does not use
its `prepare_inference_features` or `execute_regime_routing` helpers. This is a
useful partial seam, not the documented delegation at
`docs/planning/2026_codebase_modernization_and_refactoring_plan.md:144-152`.

**Remediation:** move prepared-input/routing branches behind testable adapters,
then prove parity with a successful CLI golden test.

### P2 — Phase 6 result badges conflict with fail-closed market mode

Prediction cards render `ResultChip` at `web/src/components/GameRow.tsx:151-160`.
Market cards at `:167-203` render final scores only, while
`web/src/lib/queries.ts:249-273` deliberately selects no prediction grades.
This contradicts the plan’s “identically across both modes” requirement at
`docs/plans/2026-08-23/modernization-phases-5-8-completion.md:83-86`, but is
consistent with the no-model-output market boundary.

**Remediation:** resolve policy before code changes. Under the current
fail-closed policy, revise completion documentation to state that market mode
shows scores only; otherwise explicitly authorize public prediction-grade
disclosure and add the data contract/tests.

### P2 — Modularity is improved but not demonstrated as cohesive

| Area | Baseline lines | Current lines | Largest current unit |
|---|---:|---:|---|
| Storage | 1,369 | 1,410 | `storage/r2.py` — 758 |
| Silver | 811 | 872 | `silver/builders.py` — 649 |
| Core aggregations | 1,120 | 1,171 | `aggregations/team_game.py` — 618 |
| Byplay | 888 | 924 | `byplay/enrichment.py` — 680 |
| Preseason | 814 | 878 | `preseason_features.py` — 415 |
| Weekly inference | 884 | 1,074 | CLI — 742 |

Focused packages and facades improve navigation, but these figures support
structural partitioning rather than a completed modularity objective. High-risk
coverage remains thin: R2 storage 25%, Silver builders 55%, state machine 56%,
and ops CLI 18%.

**Remediation:** prioritize behaviorally distinct seams—R2 transport/retry,
Silver normalizers, CLI input adapters, and ops command composition—rather than
line-count-driven splitting.

### P3 — Web visual verification remains unproven

Static review finds the new flex wrapping and controls acceptable, and the web
build/typecheck pass. The repository has no local fixture or rendering test for
the documented 375px–420px viewports, settled-result presentation, or loading
layout. The publication test verifies mode/data projection only.

**Remediation:** add local fixture rendering or component/browser tests for both
publication modes and narrow viewports; no live database is needed.

## Guardrails confirmed

- Local storage still requires `CFB_MODEL_DATA_ROOT` in
  `src/cks_picks_cfb/data/storage/factory.py`.
- Point-in-time and training policy paths still reject 2020 and protect lineage.
- Weekly helper tests cover missing lines, threshold boundaries, coverage mismatch,
  V3 regime normalization, and manifest counts/hashes.
- Ops tests cover notifier success/failure, command scoping, and detail truncation.
- No maintained code caller remains for archived entrypoints.

## Recommended follow-up contract

1. Restore lint/format cleanliness and correct completion documentation.
2. Resolve CatBoost/sklearn compatibility with a warnings-as-errors regression.
3. Add a successful no-network CLI golden test and finish promised delegation.
4. Replace Python import smoke checks with proven canonical parity checks.
5. Reconcile market-mode grades with fail-closed publication policy, then add
   fixture-based web verification.

## Remediation status — 2026-08-23

The approved completion contract is in progress at
`docs/plans/2026-08-23/modernization-verified-completion.md`. The historical
findings above remain intact.

Completed remediation evidence:

- Ruff lint and formatting now pass. CatBoost is locked at `1.2.10`; the
  broad warning suppression was removed, and CatBoost pipeline fit, prediction,
  and serialization pass with warnings treated as errors.
- The weekly CLI now has parser and orchestration boundaries, delegates explicit
  Gold preparation and both routing modes to `inference.weekly`, and has a
  successful in-memory fixture covering routed output, coverage, edges, and
  temporary CSV creation.
- Publication-contract validation now compares SQL DDL columns and Python
  INSERT placeholders/providers, with temporary drift tests for unknown columns
  and missing providers.
- Market mode intentionally exposes nullable settled grades only; its selected
  run query cannot project prediction, lean, edge, confidence, or model fields.
  Playwright fixtures verify both modes at 375px and 420px without a database.
- Ops contracts and notifier behavior were extracted behind compatibility
  imports; existing injected-failure and replay tests continue to pass.

Current verification blocker:

- The full suite passes (`386 passed, 2 skipped`) with `-W error`, but global
  branch coverage is `51.56%`, below the required `60%` floor. The completion
  verdict therefore remains **Not verified**, and the contract remains
  **In Progress**. The remaining deep modularization and targeted coverage work

### Remediation evidence — 2026-08-23

The original audit evidence above is preserved. A subsequent repository-only coverage tranche passed the required full branch-aware command with `414 passed, 2 skipped` and **60.02%** coverage under the unchanged `src/cks_picks_cfb` scope and `fail_under = 60`. It used only fake S3/psycopg clients, temporary files, and in-memory frames. Ruff format/lint, contract validation, MkDocs build, and `git diff --check` also passed. This remediates the global coverage-floor finding only; the modernization verdict remains unchanged until the outstanding modularization and traceability criteria are independently verified.
  must be completed before the traceability matrix can be upgraded.
