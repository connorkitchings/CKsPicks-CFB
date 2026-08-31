# Session: R1 Legacy-Comparison 2019 Selection Remediation — Implementation

## TL;DR

- **Worked On:** Tasks 1–4 of the approved remediation plan. Implemented
  manifest-anchored 2019 resolution in
  `scripts/pipeline/build_successor_legacy_comparison_ref_set.py`, wrote and
  ran tests, added Amendment 4 to the Aug-28 contract, ran all validation gates.
- **Outcome:** All code + doc changes complete. Task 5 (fresh R1 run) requires
  user commit first (script is in SUCCESSOR_R1_COMMIT_PATHS).
- **Plan Contract:** `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md`
  — Status: Implemented (Tasks 1–4)
- **Approval / Status:** Approved by user on 2026-08-31.
- **Blockers:** User must commit (two commits — Week-1 docs first, then
  remediation) before launching the R1 run.
- **Next:** User commits → fresh R1 run via Task 5 command in the plan.

## Context and Decisions

- **Amendment to plan (non-material):** The plan's `_manifest_2019_entry()`
  checks 6–7 assumed a `lake_manifest` sub-object per ref (mirroring the
  restore script's `_ref()` at a higher level). The actual restoration manifest
  format has no `lake_manifest` — refs are flat DatasetRef-shaped objects
  (`dataset`, `version_id`, `schema_version`, `content_sha`, `uri`). The URI
  prefix check (`lake/silver/`) and required field check remain; the
  `partitions.seasons` / `state: validated` check was not needed because the
  immutable manifest already encodes that invariant at the restoration layer.
  No architecture, interface, or scope change — mechanical adaptation only.
- `contract_version` in the restoration manifest is
  `"legacy-comparison-2019-restoration-v1"` (its own restoration contract),
  not `CONTRACT_VERSION` (`"successor-legacy-comparison-ref-set-v1"`). This
  is correct — we pin the restoration contract version, not the output contract.
- Pinned SHA: `a2b9398fc9773ce37b1d126714c035b896c3ba43359834be6026b664651d316a`
  (derived from live R2 manifest bytes before implementation).
- Existing test `test_missing_catalog_evidence_writes_immutable_failure_diagnostic`
  was adapted (renamed + logic updated) to reflect the two-source flow: it now
  provides a valid 2019 manifest (so that path succeeds) and makes
  `_catalog_entries` fail on a 2021 LookupError. The original intent (failure
  diagnostic written on LookupError) is preserved.
- _Storage mock's `read_bytes()` now raises `KeyError` (not returns None) for
  missing URIs, matching the real storage interface used by `_manifest_2019_entry`.

## Work Completed

- Task 1: Rewrote `build_successor_legacy_comparison_ref_set.py` with pinned
  constants, `_manifest_2019_entry()` (7 checks), `_catalog_entries()` scoped
  to 2021–2025, and merged entries in `main()`.
- Task 2: Rewrote `tests/test_successor_legacy_comparison_ref_set.py` with
  5 test cases; all pass.
- Task 3: Amendment 4 appended to
  `docs/plans/2026-08-28/r1-cross-lineage-audit-scope-remediation.md`.
- Task 4: All validation gates passed (see Validation section).
- Task 5: Not run — requires commit first.

## Files Modified

- `scripts/pipeline/build_successor_legacy_comparison_ref_set.py` — REWRITTEN
- `tests/test_successor_legacy_comparison_ref_set.py` — REWRITTEN
- `docs/plans/2026-08-28/r1-cross-lineage-audit-scope-remediation.md` — Amendment 4 appended
- `docs/plans/2026-08-31/r1-legacy-comparison-2019-selection-remediation.md` — Status: Implemented

## Validation

- [x] `uv run pytest tests/test_successor_legacy_comparison_ref_set.py -v` → 5 passed
- [x] `uv run pytest -q` → 590 passed, 2 skipped (no regressions)
- [x] `uv run ruff check` → all checks passed
- [x] `uv run ruff format` → reformatted (then confirmed clean)
- [x] `make contracts-check` → passed
- [x] `git diff --check` → clean
- [x] Live smoke test: `_manifest_2019_entry(storage)` against R2 → 3 entries OK

## Amendments and Blockers

- Non-material amendment: `lake_manifest` sub-check from the plan was not
  applicable (actual manifest format has no `lake_manifest`). The URI prefix
  check and required-field check provide equivalent safety. Documented above.

## Handoff Notes

- **Resume at:** Commit Week-1 docs first (proposed message in session 01),
  then commit the remediation (proposed message below), then run Task 5:

```bash
CFB_STORAGE_BACKEND=r2 \
  zsh scripts/ops/with_preview_env.sh \
  uv run python -m cks_picks_cfb.ops prepare-rating-history \
    --environment preview \
    --as-of $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --pipeline-run-id r1-full-corpus-$(date +%Y%m%d)-$(git rev-parse --short HEAD)
```

- **Watch out for:** The 2019 cross-lineage audit will now run against true
  legacy evidence for the first time. If genuine differences exist between the
  Feb 2026 legacy export and the Aug 2026 CFBD recapture, the audit will fail
  closed. That is intentional — a new contract would be required.

**tags:** ["r1", "ratings", "research", "implementation", "legacy-comparison", "2019"]
