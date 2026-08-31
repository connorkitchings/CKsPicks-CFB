# R1 Legacy-Comparison 2019 Selection Remediation (Manifest-Anchored)

- **Status:** Implemented (Tasks 1–4 complete; Task 5 pending user commit + R1 run)
- **Created:** 2026-08-31
- **Planner:** Sol (plan-session) — fresh task
- **Implementation session:** `session_logs/2026-08-31/03-r1-legacy-comparison-2019-implementation.md`
- **Approval source:** User approved on 2026-08-31 in session `82f2fd38`.
- **Commit policy:** Modified script is in SUCCESSOR_R1_COMMIT_PATHS; must be
  committed before R1 launch. Week-1 docs committed separately first to keep
  commits clean.
- **Out of scope:** R2–R4, catalog.py changes, re-running the restoration,
  production/Week-1 ops, V4.

## Goal

Make `freeze_successor_legacy_comparison_evidence` resolve season-2019
comparison refs from the completed, immutable restoration manifest in R2,
keep the v1 catalog pin for 2021–2025, then complete a fresh code-bound
R1 run through certification with `tournaments_permitted: true`.

## Background

The `r1-full-corpus-20260829-e9edee5` run succeeded through every step
(cross-lineage audit ✅, foundation ✅, certification ✅) but failed at the
final step `freeze_successor_legacy_comparison_evidence` because
`build_successor_legacy_comparison_ref_set.py` looked up season-2019
evidence via `_catalog_entries()` (a Neon `catalog.dataset_versions` query).
The 2019 restoration artifacts live in R2 under a manifest at:

```
artifacts/preview/legacy-comparison/2019/legacy-comparison-2019-55f6968/manifest.json
```

…but they were never registered in the catalog (restoration predates the
catalog ingestion integration). The v1 catalog pin covers 2021–2025 only.

## Proposed Changes

### Task 1 — `scripts/pipeline/build_successor_legacy_comparison_ref_set.py`

**Two-source merge:** `_catalog_entries()` covers 2021–2025 (unchanged).
New `_manifest_2019_entry()` reads the pinned restoration manifest from R2,
runs integrity and contract checks, and returns the single 2019 ref. Both
are merged before the existing payload-shape validation and `.failure.json`
diagnostic path.

**Pinned constants (top of file):**
```python
LEGACY_COMPARISON_2019_MANIFEST_URI = (
    "artifacts/preview/legacy-comparison/2019/"
    "legacy-comparison-2019-55f6968/manifest.json"
)
LEGACY_COMPARISON_2019_MANIFEST_SHA256 = "<sha256-of-manifest-json>"
```

**`_manifest_2019_entry()` checks (mirrors the restore script's own `_ref()`):**
1. `contract_version` matches `CONTRACT_VERSION`
2. `state == "complete"`
3. `season == 2019`
4. SHA-256 of the raw manifest bytes == `LEGACY_COMPARISON_2019_MANIFEST_SHA256`
5. Ref keys exactly `{"games", "game_outcomes", "teams"}`
6. Each ref URI starts with `lake/silver/` (non-successor)
7. Each ref's lake manifest `partitions.seasons == [2019]` and
   `state == "validated"`

All failures raise and are caught by the existing `.failure.json` diagnostic
path — same as catalog failures.

**`CONTRACT_VERSION` and merged payload shape:** unchanged. Terra verifies
no consumer parses `selection_mode` before merging.

### Task 2 — `tests/test_successor_legacy_comparison_ref_set.py`

- **Success path:** manifest 2019 + catalog 2021–2025 → all 18 required
  entries present (3 datasets × 6 seasons).
- **Tampered manifest SHA:** immutable failure diagnostic + `SystemExit`.
- **Missing manifest (R2 raises `KeyError`):** failure diagnostic +
  `SystemExit`.
- **Incomplete manifest (state != "complete"):** failure diagnostic +
  `SystemExit`.

### Task 3 — Docs

- **Amendment 4** in
  `docs/plans/2026-08-28/r1-cross-lineage-audit-scope-remediation.md`:
  records that the v1 catalog pin excluded the restored 2019 evidence; this
  run's certification supersedes prior certified results.
- **`docs/plans/index.md`:** entry for this plan under R1 remediation.
- **`docs/planning/roadmap.md`:** R1 status line updated to reflect the
  remediation plan and expected re-run.

### Task 4 — Validation

```bash
uv run pytest tests/test_successor_legacy_comparison_ref_set.py -v
uv run pytest -q                          # full suite, no regressions
uv run ruff check scripts/pipeline/build_successor_legacy_comparison_ref_set.py
make contracts-check
mkdocs build --strict                     # optional, if MkDocs configured
git diff --check
```

### Task 5 — Fresh code-bound R1 run (after commit)

```bash
CFB_STORAGE_BACKEND=r2 \
  zsh scripts/ops/with_preview_env.sh \
  uv run python -m cks_picks_cfb.ops prepare-rating-history \
    --environment preview \
    --as-of <fresh-timestamp> \
    --pipeline-run-id r1-full-corpus-$(date +%Y%m%d)-$(git rev-parse --short HEAD)
```

Full recapture through certification (~57 min). Success =
`tournaments_permitted: true` against true legacy evidence for all six
seasons. Then run the identical recovery rerun to confirm idempotence.

## Key Risks

1. **Genuine 2019 cross-lineage differences:** The cross-lineage audit
   compares the Feb 2026 legacy export against the Aug 2026 CFBD recapture.
   Any real differences fail-closed and require a new contract. This is
   intentional — not a bug.
2. **Manifest SHA must be correct:** Terra reads the live manifest from R2
   first to derive the SHA constant, then pins it. If the manifest is later
   mutated in R2 (it should not be — immutable), the pin catches it.
3. **Commit ordering:** Week-1 docs commit must precede this commit so that
   the code-bound R1 run's `definition_sha` reflects only the remediation
   change.

## Definition of Done

- [ ] `_manifest_2019_entry()` implemented and pinned with correct SHA.
- [ ] All integrity checks pass against the live R2 manifest.
- [ ] Tests pass: success path (18 entries) + 3 failure modes.
- [ ] Amendment 4 added to Aug-28 contract.
- [ ] `docs/plans/index.md` and `roadmap.md` updated.
- [ ] `uv run pytest -q` green (no regressions).
- [ ] `git diff --check` clean.
- [ ] Week-1 docs committed separately before this commit.
- [ ] Fresh R1 run completes with `tournaments_permitted: true`.
- [ ] Recovery rerun is idempotent.
