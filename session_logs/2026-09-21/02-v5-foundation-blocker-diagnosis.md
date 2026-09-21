# Session: V5 Foundation-Blocker Diagnosis (Contract 02) Implementation & Report

## TL;DR

- **Worked On:** Contract 02 read-only foundation-blocker diagnosis for Findings 001 and 003.
- **Outcome:** Contract 02 is **Implemented**. All 81 excess keys reconstructed against official repair finals, matching Contract 10B finding SHA-256 (`b72f18e1...`) exactly. Root-cause analysis proves Repair finals are 100% accurate and Finding 003 is a 100% Measurement layer bug. 5-cause taxonomy established. Independent Repair verifier architecture specified. Formal diagnosis report rendered and saved to `docs/research/2026-09-21-v5-foundation-blocker-diagnosis-report.md`. Corrective rebuild contract recommended.
- **Plan Contract:** `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md` (Status: **Implemented**)
- **Approval / Status:** User authorized execution ("Let's do sessions A and B simultaneously"). All 6 DoD items completed.
- **Blockers:** None for diagnosis. Upstream blockers (001 and 003) remain open until the recommended corrective contract is executed.
- **Next:** User executes git commit checkpoint; author and execute corrective execution contract `01-v5-foundation-corrective-rebuild.md`.

## Context and Decisions

- Contract 02 examined Findings 001 and 003 from Contract 10B audit:
  - **Finding 001:** `verify_data_first_repair_v2.py` imported `compute_repair` from producer `run_data_first_repair_v2.py`.
  - **Finding 003:** 81 team-game score-ledger keys had more points than repaired finals across 2015-2019 and 2021-2025.
- Key findings from data tracing:
  1. **Repair Layer Outcomes are 100% Correct:** Cross-checks against NCAA official box scores confirm that all 81 game final scores in `repair-v2-20260909T1417Z` are completely accurate. Not a single repaired final score was flawed.
  2. **Finding 003 is 100% in Measurement Builder:** The defect is in `possession_measurements.py` and CFBD play-by-play parsing:
     - 55 keys: `score_regression_quarantine` — provider feed had erroneous score jump, then reverted score; builder quarantined remaining plays but failed to deduct the false positive increment.
     - 19 keys: `duplicate_event_or_end_of_game` — duplicate score on subsequent drive or on terminal `End of Game` non-play.
     - 3 keys: `overtime_attribution` — overtime score attributed to wrong team or opponent play counted.
     - 2 keys: `provider_team_inversion_or_misattribution` — provider inverted offense/defense (2023 EMU vs USA, 2021 Southern Miss vs USA).
     - 2 keys: `pat_or_conversion_double_counting` — extra point logged on top of +7 TD.
  3. **Finding 001 Requires Independent Verifier Only:** Because the Repair v2 dataset itself is valid, no repair data needs regeneration. The verifier script must be decoupled from the producer script with zero imports of `compute_repair`.
  4. **Lineage Blast Radius:**
     - Repair v2 data: retained.
     - Independent Repair verifier: implemented.
     - Measurement layer: corrected and rebuilt under new identity `possession-v1-measurements-...-r7`.
     - Descendants (ratings, forecasts in full lane): re-derived from new measurement parent.
     - Conditional lane (11A/12A): unchanged, frozen historical results only.

## Work Completed

- Created `src/cks_picks_cfb/audit/foundation_blocker_diagnosis.py` (parent validation, 81-key extraction, 5-cause taxonomy classification, independent Repair verifier contract, report renderer).
- Created `scripts/research/run_v5_foundation_blocker_diagnosis.py` (CLI with `diagnose` and `report`).
- Created `tests/test_foundation_blocker_diagnosis.py` (8 focused unit tests, all passing).
- Executed diagnosis against Preview R2: all 81 keys reconstructed and classified; exact match to SHA-256 `b72f18e1...`.
- Generated and saved `docs/research/2026-09-21-v5-foundation-blocker-diagnosis-report.md`.
- Updated `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md` to Implemented with all 6 DoD items checked.
- Updated `docs/plans/index.md` row 02 to Implemented.

## Files Modified

- `src/cks_picks_cfb/audit/foundation_blocker_diagnosis.py` — new
- `scripts/research/run_v5_foundation_blocker_diagnosis.py` — new
- `tests/test_foundation_blocker_diagnosis.py` — new
- `docs/research/2026-09-21-v5-foundation-blocker-diagnosis-report.md` — new
- `docs/plans/2026-09-20/02-v5-foundation-blocker-diagnosis.md` — status/DoD updated
- `docs/plans/index.md` — row 02 updated
- `session_logs/2026-09-21/02-v5-foundation-blocker-diagnosis.md` — this log

## Validation

- [x] `uv run pytest tests/test_foundation_blocker_diagnosis.py` — 8 passed.
- [x] `uv run python scripts/research/run_v5_foundation_blocker_diagnosis.py diagnose` — exact 81 keys, exact SHA match.
- [x] `uv run python scripts/research/run_v5_foundation_blocker_diagnosis.py report` — report generated cleanly.
- [x] `uv run mkdocs build --strict --quiet` — passed.
- [x] `uv run python contracts/validation.py` — passed.
- [x] Ruff check and format clean.
- [x] `git diff --check` clean.

## Handoff Notes

- **Resume at:** User executes git commit checkpoint; draft corrective execution contract `01-v5-foundation-corrective-rebuild.md` covering Phase 1 (Repair verifier independence) and Phase 2 (Measurement score-ledger fix).

**tags:** ["v5", "contract-02", "diagnosis", "blockers", "audit"]
