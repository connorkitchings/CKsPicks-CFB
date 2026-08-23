# Verified Modernization Completion

- **Status:** In Progress
- **Created:** 2026-08-23
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation in this task on 2026-08-23.
- **Implementation log:** `session_logs/2026-08-23/04-modernization-verified-completion.md`
- **Commit policy:** User-controlled; keep documentation, quality gates, modularization, and web verification as logical commit boundaries.

## Goal

Remediate the repository-only findings in the [Modernization Verification Audit](modernization-verification-audit.md), then rerun the audit against baseline `ff8a71b` and modernization commits `9ac7490` and `2a2f9f9`.  The work is verified only when every required gate passes, no P0/P1 finding remains, and the audit traceability matrix has direct evidence for every non-deferred criterion.

## Constraints

- Do not access R2, Neon, the external data drive, production configuration, model bundles, or deployment systems.
- Preserve Python public imports, signatures, CLI flags, error contracts, output CSV column order, publication manifest semantics, storage immutability, model chronology, and fail-closed behavior.
- The only authorized public behavior change is nullable settled `spreadResult` and `totalResult` fields in market-mode web data. They may disclose only win/loss/push outcomes, never model predictions, leans, edges, confidence, thresholds, IDs, or run metadata.
- Preserve the existing audit artifacts as historical evidence. Correct escaped Markdown and append remediation evidence rather than erasing findings.

## Implementation Tasks

### 1. Truthful quality gates

- Upgrade CatBoost to `>=1.2.9,<2`, refresh the lockfile, and replace broad sklearn/CatBoost warning suppression with only narrow, tested numerical handling.
- Correct Ruff lint and formatting failures.
- Set the global Python coverage floor to 60% and make the explicit full Python CI/Nx target collect coverage. Focused test commands stay usable without collection.
- Add CatBoost pipeline fit/predict/serialization regressions and run the full suite with warnings treated as errors.

### 2. Deep, compatible modularization

- Split storage into shared S3 transport, indexed object/checksum behavior, and thin R2/S3/read-only adapters with facade-preserved imports and semantics.
- Split Silver normalization into schedule, market, and entity builders plus validation/orchestration.
- Split aggregation, byplay, and preseason code into pure transformation stages and small coordinators while preserving compatibility entrypoints.
- Split ops state, stores, notifications, step factories, and CLI wiring into cohesive modules while preserving current public entrypoints.
- Add import-cycle, export/signature, facade delegation, exception ownership, and baseline/current golden-parity coverage.

### 3. Testable weekly inference and operations

- Make the weekly script a thin parser/dependency-wiring layer with `main(argv=None)` and an injectable orchestration boundary.
- Route it through the existing feature-preparation and regime-routing APIs, preserving flags, outputs, artifact collision behavior, chronological and market-separation safeguards, and fail-closed errors.
- Add valid zero-network fixtures for prediction, coverage failure, manifest generation, immutable collision, and all regime routes.
- Failure-inject publish/freeze/close and test notification redaction, truncation, timeout, command scope, replay behavior, and original-error preservation.

### 4. Real contract validation

- Retain SQL and TypeScript schemas as canonical database contracts; do not add a duplicate Python schema.
- Validate SQL table columns against Python publication INSERT/UPSERT column lists and named placeholder providers, while retaining SQL/Drizzle and team-map validation.
- Keep lake-schema checks distinct from cross-language database validation.
- Add negative temporary-copy tests proving SQL, TypeScript, and Python drift is detected with actionable diagnostics.

### 5. Web disclosure and browser verification

- Add nullable market-mode settled result grades from the selected versioned run, falling back to legacy game results only when no versioned run exists.
- Render score and result chips in both publication modes, and update publication-boundary tests to permit grades only.
- Add a production-disabled `CFB_UI_TEST_MODE=1` fixture path and Playwright browser coverage at 375px and 420px for modes, week navigation/URL state, grades, loading state, focus/reduced motion, and overflow.
- Apply React performance and Web Interface Guidelines recommendations to modified components.

## Required Verification

```bash
uv run ruff format --check .
uv run ruff check .
PYTHONPATH=src:. uv run pytest tests -q -W error --cov=cks_picks_cfb --cov-report=term-missing:skip-covered
uv run python contracts/validation.py
uv run mkdocs build --quiet
git diff --check
cd web && npm run lint && npm run typecheck && npm run build && npm run test:publication && npm run test:ui
```

Also require isolated baseline/current golden parity for every behavior-preserving extraction, a successful zero-network weekly path and injected failure paths, contract negative tests, browser evidence for both modes at mobile widths, and documentation/audit updates.

## Definition of Done

- [ ] All required gates pass with no warnings treated as errors. Python test,
  lint, format, contract, and web gates pass; the 60% coverage requirement does
  not yet pass (current: 51.56%).
- [x] Python coverage is at least 60%, including critical happy and failure paths in storage, Silver, inference, state-machine, and ops CLI modules. Evidence: 2026-08-23 full branch-aware run, `414 passed, 2 skipped`, 60.02%; storage 71%, state machine 88%, Silver 73%, and ops CLI 45%. The completion work remains In Progress because its deeper modularization and audit criteria are separate.
- [ ] No P0/P1 audit findings remain.
- [ ] The audit report has a current evidence-backed verdict and Phase 1–8 traceability matrix.
- [ ] This plan is marked `Implemented` only after the preceding items pass; otherwise it remains `In Progress` with precise blockers.

## Amendments

- **2026-08-23 — coverage evidence:** The pre-existing suite reaches 51.56%
  branch coverage under the required source scope. The 60% requirement remains

- **2026-08-23 — coverage closure evidence:** Offline fake-client and temporary-fixture tests raised the same required source scope to 60.02% branch-aware coverage (`414 passed, 2 skipped`, warnings as errors). This closes only the coverage floor; it does not rewrite the prior audit finding or change the overall modernization verdict.
  unchanged; no modules will be excluded merely to satisfy the gate. Additional
  targeted tests and the planned deep extractions remain necessary.
