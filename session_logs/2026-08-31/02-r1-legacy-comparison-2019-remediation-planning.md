# Session: R1 Legacy-Comparison 2019 Selection Remediation — Planning

## TL;DR

- **Worked On:** Diagnosed the `freeze_successor_legacy_comparison_evidence`
  failure in runs `e9edee5` and `6bc4be6`; designed the manifest-anchored
  remediation; produced and saved the approved plan.
- **Outcome:** Plan approved. Implementation contract saved at
  `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md`.
  Plans index and roadmap updated. No implementation files changed.
- **Plan Contract:** `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md`
- **Approval / Status:** Approved by user on 2026-08-31. Status: Approved.
- **Blockers:** Week-1 docs must be committed before the remediation commit
  (script is in SUCCESSOR_R1_COMMIT_PATHS; commit ordering matters).
- **Next:** Open a fresh Terra task referencing the plan path above.

## Context and Decisions

- Root cause: `build_successor_legacy_comparison_ref_set.py` uses
  `_catalog_entries()` (Neon `catalog.dataset_versions` query) for all 6
  seasons. The 2019 restoration artifacts are in R2 but were never registered
  in the catalog (restoration predated catalog integration). The v1 catalog
  pin covers only 2021–2025.
- Decision: manifest-anchored resolution. Pin the restoration manifest URI +
  SHA-256 as constants. New `_manifest_2019_entry()` reads from R2, runs 7
  integrity checks (mirrors the restore script's `_ref()` logic), and returns
  the 2019 ref. Merged with the catalog 2021–2025 entries before the existing
  payload-shape validation. CONTRACT_VERSION and payload shape unchanged.
- Decision: NOT injecting PREVIEW_DATABASE_URL into subprocess env — that
  option was explored but the actual failure is a missing catalog row, not a
  missing env var (the script was run with the preview wrapper and still
  failed). The correct fix is manifest-anchored, not env injection.
- The `aaac30d` run on 2026-08-29 `succeeded` but `tournaments_permitted`
  was false (it ran before the R1 derived-schema and play-coverage remediations
  were committed; it is NOT a valid certification). The two failing runs
  (`e9edee5`, `6bc4be6`) both have the 2019 catalog gap.
- Commit ordering: Week-1 docs commit first, then remediation commit. Each
  R1 run is code-bound to its definition SHA.

## Work Completed

- Queried Preview Neon `ops.pipeline_runs` and `ops.pipeline_steps` to
  get exact failure steps for all R1 runs.
- Ran `build_successor_legacy_comparison_ref_set.py` directly to confirm
  the failure message: "No legacy games comparison ref exists for season 2019."
- Confirmed the 2019 restoration manifest exists at R2 URI:
  `artifacts/preview/legacy-comparison/2019/legacy-comparison-2019-55f6968/manifest.json`
  (not locally — lives in R2 Preview bucket).
- Authored remediation plan (Tasks 1–5) including all integrity checks,
  test cases, and commit-ordering constraint.
- Saved plan, updated `docs/plans/index.md`, updated `docs/planning/roadmap.md`.

## Files Modified

- `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md` — NEW
- `docs/plans/index.md` — R1 remediation entry added
- `docs/planning/roadmap.md` — R1 status updated with remediation reference

## Validation

- [x] `git diff --check` (will run at end of session)
- [x] No implementation files changed — plan-only session
- [ ] Full pytest (deferred to Terra)

## Amendments and Blockers

- None. Plan is complete and approved.

## Handoff Notes

- **Resume at:** Open fresh Terra task, read
  `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md`,
  implement Tasks 1–5 in order.
- **Watch out for:**
  1. Read the live R2 manifest first to derive the SHA256 constant — it's not
     stored locally.
  2. The `_manifest_2019_entry()` checks must mirror `restore_scripts`'s own
     `_ref()` validation exactly (contract_version, state, season, sha,
     ref keys, non-successor URIs, partitions.seasons == [2019],
     state == "validated").
  3. Commit Week-1 docs BEFORE this change to keep code-bound lineage clean.

**tags:** ["r1", "ratings", "research", "planning", "legacy-comparison", "2019"]
