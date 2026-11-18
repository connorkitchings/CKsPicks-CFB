# Session: Holdout replay readiness, Phase 1 (Tasks 1 and 3)

## TL;DR

- **Worked On:** [Holdout replay readiness](../../docs/plans/2026-11-12/05-holdout-replay-readiness.md), Phase 1 only: the read-only pin recovery check (Task 1) and the read-only export tool (Task 3).
- **Result:** All 12 revision manifests reproduce their pins. Task 2 (controller and builder changes) and Task 4 (running the real export) are deferred to after the 2026-12-13 final close.
- **Touched:** `scripts/research/verify_2026_manifest_pins.py`, `scripts/research/export_2026_holdout.py`, `tests/test_export_2026_holdout.py`, docs. No live-pipeline file, no database write, no provider call.

## Task 1: recovery check

`verify_2026_manifest_pins.py` finds the git version of `conf/season/2026/score_reconciliation_exceptions.json` whose bytes match each manifest's pinned SHA-256, restores it into a temporary root, points `season.inputs.REPOSITORY` at that root at runtime (no source edit), then runs `validate_model`, `validate_revision` and `load_inputs` (through the last completed week) against Preview R2. It ran under `scripts/ops/with_preview_env.sh` with `CFB_STORAGE_BACKEND=r2` and the `CFB_R2_PREVIEW_*` variables present (checked by name only).

The contract listed 5 file versions and 10 manifests. The file now has 6 versions (`8145ebe8`, the Week 12 manifest commit, is the sixth) and there are 12 manifests (`w12_v1` and `w12_v2` added).

| Manifest | Pinned exceptions SHA-256 | Git commit | Result |
| --- | --- | --- | --- |
| `w7_v1` | `939ec41c62731ce9fe846c100100e61ec8f2a6bf94823e105f32140fd0bea8cb` | `2807e087` | PASS (through week 6) |
| `w8_v1` | `081f9d0f78a22d56883285da6009b272de86e6d38b6a739f4cab0fd99957da4d` | `fa1b2b61` | PASS (through week 7) |
| `w8_v2` | `081f9d0f78a22d56883285da6009b272de86e6d38b6a739f4cab0fd99957da4d` | `fa1b2b61` | PASS (through week 7) |
| `w8_v3` | `081f9d0f78a22d56883285da6009b272de86e6d38b6a739f4cab0fd99957da4d` | `fa1b2b61` | PASS (through week 7) |
| `w9_v1` | `a9c7541e2db0b1769ba0aa514d2ab226b74ba7aa7cf49785a578a00366d39237` | `d8c5ac35` | PASS (through week 8) |
| `w9_v2` | `a9c7541e2db0b1769ba0aa514d2ab226b74ba7aa7cf49785a578a00366d39237` | `d8c5ac35` | PASS (through week 8) |
| `w9_v3` | `a9c7541e2db0b1769ba0aa514d2ab226b74ba7aa7cf49785a578a00366d39237` | `d8c5ac35` | PASS (through week 8) |
| `w10_v1` | `10b86bbaeeec30736e47de1acf4aa900014bb0d39a6d7837a8b38ac63a31e2f4` | `c3ee43ee` | PASS (through week 9) |
| `w11_v1` | `3c978b7c5e1e56ea20cded105123ee2a07b2db7d20e0824576c041fd62227ada` | `e613add3` | PASS (through week 10) |
| `w11_v2` | `3c978b7c5e1e56ea20cded105123ee2a07b2db7d20e0824576c041fd62227ada` | `e613add3` | PASS (through week 10) |
| `w12_v1` | `e4dd1f6cf99f20249b12391fa57798df3ad1f92d575bbbc7efccd0fbf6771934` | `8145ebe8` | PASS (through week 11) |
| `w12_v2` | `e4dd1f6cf99f20249b12391fa57798df3ad1f92d575bbbc7efccd0fbf6771934` | `8145ebe8` | PASS (through week 11) |

No failures; no pin other than the exceptions file failed, and no provider call was needed.

## Task 3: export tool

`export_2026_holdout.py` writes a canonical sorted JSON manifest (`holdout_export_v1`) and prints its SHA-256. Per revision manifest it lists every pinned input with URI and SHA-256, roles `outcomes` (finals), `early_week_lines` (`market_quotes`, `historical_lines`) and `pre_kickoff_input`; model inputs are listed once. Near-kickoff captures are supplied by file and appear only under `analysis_only`; one that is also a pinned input is rejected. A manifest captured after its newest pre-week cutoff is rejected; with a reader, a pinned quote stamped after the manifest's capture time is also rejected.

`tests/test_export_2026_holdout.py` covers byte-identical reruns, hash-pinned inputs with roles, the cutoff rule (accepts and rejects), the quote-after-capture rejection and the analysis-only separation. The real export has not been run (Task 4).

## Next

1. After the 2026-12-13 final close, add the final close manifest to the check and run the export (Task 4).
2. Task 2 (per-manifest exceptions pin) with Stage 1a, after 2026-12-13.
