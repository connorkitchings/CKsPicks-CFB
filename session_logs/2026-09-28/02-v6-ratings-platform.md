# Session: Isolated V6 ratings laboratory implementation

## TL;DR
- **Worked On:** Implemented the approved V6 ratings research architecture without changing V5 or production.
- **Outcome:** Research storage, pinned V5 corpus import, versioned measurements, replay engine, reference candidate, historical evaluation, CLI, config, tests, and operator guide are in place. Actual V5 parents and a full local-output run were verified.
- **Plan Contract:** `docs/plans/2026-09-28/v6-ratings-research-platform.md`
- **Approval / Status:** User accepted the architecture and instructed implementation. Contract remains **In Progress** pending dedicated R2 bucket and scoped credentials.
- **Blockers:** `CFB_R2_LAB_SOURCE_*` and `CFB_R2_LAB_*` are absent, so isolated cloud acceptance cannot run.
- **Next:** Provision the separate private research bucket and scoped credentials; run all CLI stages with `--apply`, verify deterministic rerun, record cloud manifest keys/runtime/storage, then close the plan.

## Context and Decisions
- The laboratory is physically separate from the source R2 bucket; no production or Preview fallback exists in its CLI. A local fixture store is available for tests and acceptance diagnostics.
- Historical information uses the accepted later-week and kickoff-plus-six-hour reconstructed policy. 2020 is excluded; the 2019→2021 gap is preserved.
- Candidate comparisons refit alpha-10 Ridge on the accepted V5 feature population, with only rating values swapped. Frozen V5 predictions and common-bridge V5 are separate benchmarks. The first carryover-only reference is infrastructure evidence, not a proposed production rating.

## Work Completed
- Pinned signed V5 Repair, measurement, rating, forecast, and independent verifier manifests and imported checked dataset refs. Actual source read returned 8,936 population rows, 8,935 eligible feature rows, and 7,318 frozen prediction rows.
- Built 35,744 individual PPP observations and 35,535 distinct cumulative snapshots with explicit contributor IDs. Replay produced 35,740 pregame states across the accepted historical corpus.
- Recomputed frozen V5 2025 MAE: 14.1596 margin and 13.3558 total, matching accepted results. Common bridge produced 7,318 rows for V5 and the carryover reference; carryover trailed V5 by 0.5969 margin and 0.0506 total MAE under the paired protocol. Separate 2018/2019/2021 diagnostics produced 5,318 rows.
- Completed local-output stage publication and checksum-verified reload; identical corpus rerun retained the same manifest key. End-to-end local run took approximately 43 seconds. The Preview credential was used only through the read-only source adapter for this diagnostic, not for lab cloud publication.
- Added operator documentation and linked the implementation contract and documentation index.

## Files Modified
- `src/cks_picks_cfb/ratings_lab/` — isolated storage, contracts, corpus, measurement, replay, stages, and evaluation modules.
- `scripts/research/ratings_lab.py` — dry-run-by-default research CLI.
- `conf/research/ratings_lab_v1/protocol.yaml` — fixed historical protocol.
- `tests/ratings_lab/test_platform.py` — boundary, immutable write, chronology, evidence semantics, coverage, and earlier-only fitting checks.
- `docs/research/ratings-lab-v1.md`, `docs/index.md`, `docs/plans/index.md`, `docs/plans/2026-09-28/v6-ratings-research-platform.md` — operations and contract progress.

## Validation
- [x] New focused tests passed (8 tests after final additions; see final test run).
- [x] 87 storage, repository-boundary, V5 rating, live-forecast and weekly-cycle regressions passed.
- [x] 60 additional forecast, materializer and cloud-storage regressions passed.
- [x] Actual pinned V5 source and local-output end-to-end run succeeded; frozen V5 score and population reproduced.
- [x] `uv run ruff check` on new code/tests passed.
- [x] `uv run mkdocs build` passed. Strict build reports 10 existing links to files outside the MkDocs tree, including links in the prior ratings audit; the new laboratory page adds no such link.
- [x] `git diff --check` passed.

## Amendments and Blockers
- No material architecture amendment. The separate cloud bucket and credentials are missing, so the contract cannot be marked Implemented. The local diagnostic does not establish bucket-scoped source credential permissions.

## Handoff Notes
- **Resume at:** Configure dedicated research R2 bucket and explicit `CFB_R2_LAB_SOURCE_*`/`CFB_R2_LAB_*` credentials, then follow `docs/research/ratings-lab-v1.md` for cloud acceptance.
- **Watch out for:** Do not repoint the research output to the existing source bucket, import 2020, treat cumulative snapshots as independent games, or promote a candidate from historical results alone. Preserve the uncommitted September 28 V5 audit docs in this worktree.
- **Proposed commit message:** `feat: add isolated V6 ratings research platform`

**tags:** ["ratings", "v6", "research", "r2", "replay", "evaluation"]
