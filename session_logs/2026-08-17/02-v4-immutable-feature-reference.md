# Session: V4 Immutable Point-in-Time Feature Reference

## TL;DR

- **Worked On:** Implemented the strict/reconstructed V4 feature-reference boundary and feature-prefix tournament provenance.
- **Outcome:** A strict immutable Preview team reference was created; source-family eligibility, reconstructed isolation, and frozen selected-feature variants are now enforced in code.
- **Plan Contract:** [Early-Season V4 Modeling and Game-4 Handoff](../../docs/plans/2026-08-17/early-season-v4-modeling.md)
- **Approval / Status:** User explicitly authorized the V4 reference plan on 2026-08-17. Contract remains `In Progress` because the Preview tournament could not be executed.
- **Blocker:** The Codex environment rejected further escalated commands at its usage limit. This blocked V5 Gold assembly and full-suite validation, not source-data validity.

## Decisions and Changes

- Added `v4_preseason_team_features`: an immutable, normalized strict or reconstructed team-season reference with deterministic reference SHA, source-family coverage, required feature definitions, and eligibility provenance.
- Strict family admission requires full 2021-2026 scheduled-team coverage plus `effective_at` before the season's first kickoff. The current strict reference therefore contains only the verified prior/current core; all added families are recorded unavailable.
- Added V5 model-ready assembly with a required feature track. Strict references are activation-eligible; reconstructed references remain separately marked and cannot accidentally replace active Gold.
- Added canonical additive feature variants: prior core, returning production, transfer portal, recruiting, coaching, roster continuity, preseason rankings, then talent. The candidate workflow now evaluates every complete prefix and freezes the selected prefix into the report/refit feature order.
- Reconstructed candidate reports require `--research-only`; they cannot be locked, finalized, refit, or loaded for inference.

## Preview Artifact Evidence

- Strict reference: `v4_preseason_team_features/8c47f6d5ccdced2365e4dfdd`
- Content SHA: `6bc8f8c1c38d4f83898c9b4bfb07c1d9e706770d861ab018631db87b3be10dc2`
- Reference SHA: `efa3271d7d64aea60072ab43425e36f44a3c103ef80ee90064357d80df4d4c9b`
- Ref URI: `artifacts/preview/refs/v4/strict-preseason-team-20260817.json`

## Validation

- [x] Focused V4 feature/reference, V3 bundle, ordinal-training, and preseason tests: 17 passed.
- [x] Focused Ruff checks passed.
- [x] `build_v4_preseason_feature_reference.py` successfully registered the strict immutable Preview reference.
- [ ] Full Python suite, contracts, MkDocs, web checks, and `git diff --check`: blocked before execution by the Codex environment usage limit.
- [ ] V5 strict selection Gold, sealed 2022-2024 selection, locked 2025 evaluation, refit, and private Preview rehearsal: blocked before execution by the same environment limit.

## Handoff Notes

Resume with the existing Preview wrapper and the immutable strict reference:

```bash
zsh scripts/ops/with_preview_env.sh make assemble-model-ready \
  YEAR=2026 ENV=preview AS_OF=2026-08-17T16:00:00Z \
  CORE_REF_URI=artifacts/preview/refs/history/point-in-time-core.json \
  BASELINES_REF_URI=artifacts/preview/refs/history/baselines-selection.json \
  PRESEASON_FEATURES_REF_URI=artifacts/preview/refs/v4/strict-preseason-team-20260817.json \
  FEATURE_TRACK=strict \
  OUTPUT_REF_URI=artifacts/preview/refs/v4/model-ready-strict-selection-20260817.json
```

Then generate and seal 2022-2024 strict candidates before creating any locked-2025 baseline/reference. Preserve the active V2 Preview run and do not use reconstructed research reports for route activation.

**tags:** ["modeling", "v4", "point-in-time", "feature-lineage", "preview"]
