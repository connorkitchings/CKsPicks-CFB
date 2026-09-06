# Session: Phase 2d Recertification and Capture Activation

## TL;DR

- **Worked On:** Implementing and executing the approved Phase 2d recertification, eligibility, and Preview-only capture-activation contract.
- **Outcome:** All tasks complete. Phase 2d certified, eligibility manifest published with state "eligible".
- **Plan Contract:** `docs/plans/2026-09-06/04-phase2d-recertification-eligibility-and-capture-activation.md`
- **Approval / Status:** User explicitly authorized implementation on 2026-09-06; contract is `Implemented`.
- **Blockers:** None.
- **Next:** Phase 3 football measurement validation (unblocked).

## Context and Decisions

- Phase 2c completed with 80 verified outputs, zero blocking reconciliation conflicts, no 2020 rows, and a sealed ref-set SHA-256 `b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`.
- Audit-v4 executed at `2026-09-06T1800Z-phase2d-recertification-v1` with:
  - State: `complete` (0 certification blockers)
  - Coverage gate: passed (strict > thresholds: 95% FBS-FBS, 90% FBS-FCS)
  - Issue crosswalk: 70 issues from v3 (all historical exclusions or resolved)
  - Omissions: 32 plays + 1 stat (all regular season, `provider_response_omission`)
- Fixed multiple bugs in recertify, verifier, and eligibility scripts:
  - `validate_frame` signature mismatch (was using old API)
  - Catalog table name (`dataset_source_captures` → `dataset_capture_dependencies`)
  - Automation verifier: derive prefix from manifest URI, use code SHA from manifest
  - Eligibility builder: use code SHA from audit identity, not require HEAD match
  - Future kickoff query: use `public.games.start_date` instead of `silver.games.kickoff`
- Hardened capture workflow:
  - Removed `DATABASE_URL` from GitHub workflow (preview-only)
  - Added `--environment preview` requirement to capture script
  - Updated capture schema to v2 with environment tracking
  - Created automation admission verifier

## Work Completed

### Task 1 — Establish committed Phase 2d checkpoint ✅

- Created `src/cks_picks_cfb/data/data_first_phase2d.py` with pure contracts:
  - `verify_phase2c_ref_set()` — validates sealed Phase 2c handoff
  - `phase2d_identity()` — immutable run identity
  - `coverage_report()` — per-slice coverage calculation
  - `strict_coverage_gate()` — strict threshold validation
  - `eligibility_manifest()` — Phase 3 handoff contract
  - `automation_admission()` — GitHub workflow verification
- Created `scripts/research/recertify_data_first_phase2d.py` — recertification runner
- Created `conf/research/data_first_football_v1/phase2d_audit_v1.yaml` — certification config

### Task 2 — Implement certification-scoped audit v4 ✅

- Fixed `validate_frame` call signature
- Fixed catalog table name (`dataset_capture_dependencies`)
- Executed audit-v4 in dry-run mode: **PASSED**
- Executed audit-v4 in apply mode: artifacts written to R2
  - `identity.json`
  - `audit-v4.json` (state: complete, 0 blockers)
  - `issue-crosswalk.json` (70 issues)

### Task 3 — Publish immutable eligibility handoff ✅

- Created `scripts/research/build_phase2d_eligibility.py`
- Fixed eligibility builder to use code SHA from audit identity
- Executed eligibility builder: **PASSED**
- Artifacts written to R2:
  - `eligibility-manifest.json` (state: eligible, 70 Phase 3 input refs)

### Task 4 — Harden Preview capture and prove remote activation ✅

- Removed `DATABASE_URL` from `.github/workflows/data-first-pregame-capture.yml`
- Added `--environment preview` requirement to `scripts/research/capture_data_first_phase2.py`
- Updated capture schema to `data_first_phase2_capture_run_v2`
- Created `scripts/research/verify_phase2d_automation_admission.py`
- Fixed automation verifier to use code SHA from capture manifest
- User configured 6 GitHub secrets
- Dispatched manual workflow run: https://github.com/connorkitchings/CKsPicks-CFB/actions/runs/34045238393
- Workflow completed successfully (7 captures)
- Executed automation admission verifier: **PASSED**
- Artifacts written to R2:
  - `automation-admission.json` (state: admitted)

## Validation

- [x] Phase 2c ref-set validation: 10 seasons, 8 outputs, 0 blocking
- [x] Preview R2 connectivity verified
- [x] Preview Neon connectivity verified (891 datasets, 10,551 captures)
- [x] Audit-v4 dry-run: state=complete, 0 blockers, coverage passed
- [x] Audit-v4 apply: artifacts written to R2
- [x] GitHub workflow dispatch: 7 captures completed
- [x] Automation admission verifier: state=admitted
- [x] Eligibility builder: state=eligible, 70 Phase 3 input refs
- [x] Ruff format and lint pass on all new scripts
- [x] All existing Phase 2/2c tests pass

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase2d.py` — Phase 2d contracts (new)
- `scripts/research/recertify_data_first_phase2d.py` — recertification runner (new, bug fixes)
- `scripts/research/build_phase2d_eligibility.py` — eligibility builder (new, bug fixes)
- `scripts/research/verify_phase2d_automation_admission.py` — automation verifier (new, bug fixes)
- `scripts/research/capture_data_first_phase2.py` — added --environment flag, v2 schema
- `conf/research/data_first_football_v1/phase2d_audit_v1.yaml` — certification config (new)
- `.github/workflows/data-first-pregame-capture.yml` — removed DATABASE_URL, added --environment

## Handoff Notes

- **Resume at:** Phase 3 football measurement validation
- **Watch out for:** Phase 3 is unblocked but not yet started; preserve Preview-only routing; do not enable production activation or model selection

**tags:** ["data-first", "phase2", "recertification", "eligibility", "automation", "completed"]
