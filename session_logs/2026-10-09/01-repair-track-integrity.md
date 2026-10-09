# Session: Repair-track integrity continuation

## TL;DR
- **Worked On:** First correctness and enforcement tasks from the approved October 4 repair-track plan.
- **Outcome:** Added schedule-derived weekly request inventories, completed-game capture coverage, Silver version ambiguity rejection, exact keys in published comparisons and a fail-closed `byplay_v1` collision guard. The full play-identity repair remains an unapplied draft pending versioned downstream identities.
- **Plan Contract:** `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md`
- **Approval / Status:** User explicitly requested complete implementation; In Progress.
- **Blockers:** Week 6 finals/stabilization and still-open scoring/source discrepancies prevent the real reconstruction and release rehearsal. Other implementation work remains actionable.
- **Next:** Integrate required policy and builder receipts; design `byplay_v2` and attribute its downstream differences; complete source and numerical reconciliation; certify affected descendants.

## Context and decisions
- Integrity closure precedes Week 7 release timing. Preserve the B2 recipe and recertify any descendants changed by corrected sources.
- Existing uncommitted October 8 work and unrelated committed web changes were preserved. No commit, cloud write, database mutation or serving change occurred.

## Work completed
- New `byplay_v1` derivations collapse exact repeated records and reject distinct records at the same sequence before they can be silently removed. A read-only smoke test rejected the actual 2021 pinned collision. The draft change to retain distinct provider play IDs is not applied because `byplay_v1` requires the old sequence key; `byplay_v2` and dependent drive/possession identities are required first.
- Inventory generation derives exact plays and game-stats requests from a byte-pinned raw schedule and canonical-week policy; R2 ingestion re-reads the underlying sources, compares generated and attempted requests, and blocks absent completed-game responses before promotion. A returned but incomplete capture is retained in Bronze for diagnosis while the ingestion run fails before compatibility publication.
- The pinned Bronze/Silver play census covered all 11 B2 seasons, verified 168 Bronze capture object hashes and 1,673,337 source rows, and found 28 complete-sequence collisions with distinct provider IDs: one in 2021 and 27 in 2025. All collision identities match the Silver parents. The current sequence dedup has 28 candidate removals; 19 carry non-null PPA and three are scoring plays. Exact affected IDs and 75,032 Bronze rows with incomplete sequence keys are reported in `docs/plans/2026-10-08/repair-track-evidence/play-identity-census.json`. Descendant impact remains open.
- Detailed review found 25 cross-period collisions in 2025, with 24 regulation plays among the current `keep="first"` removal candidates. This requires a linked by-play, drive, possession and scoring identity change; retaining rows under a new by-play key alone is insufficient.
- The Week 5 pinned Silver games artifact has 56 FBS–FBS games; the raw-games index also has three FBS–FCS games. A byte-pinned raw-games inventory covers all 59 and exactly matches the real plays and game-stats request enumerators. No provider API call or write was made.
- The same exact-byte inventory matched both real ingesters for canonical Weeks 0, 1, 5, 6 and 7. This verifies request enumeration, not provider response completeness or current quote coverage.
- The Silver quality reader limits explicit pins to the requested season/cutoff and rejects multiple newest versions at one as-of time.
- Published comparison reports now enumerate every one-sided population key and its reason bucket. The 95 adjusted rows still require live exact-key disposition; code delivery is not that disposition.

## Validation
- Full Python suite: 2,237 passed, 14 skipped with warnings as errors. Ruff format/check passed across the repository; shared-contract validation passed.
- Serial PostgreSQL integration against a disposable local PostgreSQL 16 database: 29 passed. The container was removed. The quality registry reports 32 checks with no registration problems. The evidence manifest verified 13 local files, including the new census.
- Web lint, typecheck, production build, publication tests (141 passed, 1 skipped) and browser tests (51 passed) passed. Strict MkDocs build passed after replacing eight dead site links into `session_logs/` with repository paths.

## Amendments and blockers
- Existing by-play artifacts may have silently removed source events. New builds fail closed until the versioned repair and downstream attribution are ready; the protective guard does not itself correct the measurements.
- The six quality follow-ups, scoring defects, independent metric population, 2025 matchup backfill, Week 6 certification and Preview cutover remain open.

## Handoff notes
- **Resume at:** Quality builder integration and full-source discrepancy ledger, then update the completion matrix with exact receipts.
- **Watch out for:** Current c2/B2 evidence is valid only for its existing inputs. Preserve historical artifacts when publishing corrected successors.
- **Commit proposal:** `feat(quality): enforce schedule-based ingestion coverage and version policy`

**tags:** ["pipeline", "quality", "integrity", "release"]
