# Session: V5 Documentation Authority Reset and Contract 08 Reconciliation

## TL;DR

- **Worked On:** Task 1 of [the V5 documentation reset and completion-sequence contract](../../docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md), followed by Contract 08 runner and Preview-parent reconciliation.
- **Outcome:** Active documentation reflects the accepted September 22 V5 state and the `07 → 08 → 09 → 06 → conditional Phase 7` sequence. Contract 08 is Implemented for Weeks 0–3 as independently verified Preview replay `possession-v1-rating-replay-20260922-fcaa571`.
- **Plan Contract:** `docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md` — In Progress; Task 1 complete.
- **Approval / Status:** User explicitly authorized the contract on 2026-09-22.
- **Blockers:** None. Week 4 finals must stabilize before the required new-ID refresh of Contracts 07 and 08 and Contract 09 readiness work.
- **Next:** After Week 4 finals stabilize, refresh Contracts 07 and 08 under new immutable IDs through Week 4, then execute Contract 09 for Week 5 readiness.

## Context and Decisions

- The canonical data-first roadmap is now the detailed status authority. Active entry points report that historical V5 development is accepted, all four findings are closed, Contract 07 is Implemented with 157 live games through Week 3, and Contract 08 is next.
- Dated Contract 10B/11A/12A evidence remains in place. The documentation labels 10B's then-open findings as historical at-publication state and records their later closure.
- Read-only Preview R2 inventory found all Contract 08 parents: live measurement manifest `possession-v1-measurements-20260922-2026c`, Repair-2026 `repair-2026-20260922T145500Z`, historical 11B rating manifest `possession-v1-ratings-20260921-11d59ee-r9cert`, plus existing 2026 recruiting, returning-production, and coaching snapshots dated 2026-08-14. No provider capture is required.
- `run_data_first_possession_ratings.py` only accepts the historical R6/Repair-v2 parent contract and recomputes the full 60-candidate selection tournament. Its independent verifier has the same historical-parent boundary. Reusing either would violate Contract 08's no-reselection and historical-byte-stability requirements.

## Work Completed

- Added orchestration contract `02-v5-documentation-reset-and-completion-sequence.md` and marked Task 1 complete.
- Updated README, documentation home, assistant guides, quickstart, operations and data-first roadmaps, plans index, methodology, measurement, evaluation, rating requirements, and repository boundaries.
- Updated authority regression tests to require the current live sequence while preserving dated conditional/audit records.
- Inspected Contract 08's runner, verifier, input interfaces, and live Preview parents without writing R2, Neon, production, or web state.
- Added Amendment 2 and the isolated Contract 08 replay core, configuration,
  and Preview-only preflight/apply runner. The runner binds the certified 07
  measurement manifest, frozen 11B definition, r9 terminal parent, and three
  2026 preseason manifests. Its first real-parent dry run is deterministic:
  276 priors, 628 rating states, and 314 team states across Weeks 0–3.
- Replaced an inapplicable global next-game boundary with the frozen
  pre-kickoff rule applied to each source team's next certified weekly game.
  The global rule could resolve only seven live PPP observations because live
  snapshots are keyed to the team playing in the target game. The corrected
  team-specific rule resolves 326 source observations without changing a
  selected parameter, historical artifact, or production boundary.
- Added a verifier-owned reconstruction module and CLI. They independently
  validate all parent raw checksums, the exact three preseason manifests,
  output schemas, row counts, partitions, and record digests without importing
  the producer, historical tournament materializer, or research runners.
- Added agreement, perturbation, and import-boundary tests. Producer and
  verifier frames match exactly for priors, rating states, and team states.
- Applied replay `possession-v1-rating-replay-20260922-fcaa571` from clean code
  SHA `fcaa57168702e6005dfe786c0e3489a6c04c6df2`. The retained manifest raw SHA
  is `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.
- Independently verified 276 priors, 628 rating states, and 314 team states
  across 157 eligible games in Weeks 0–3. Verifier SHA is
  `568113873d5a1329d68f54b46bd0f507e79c24ebe770e76accc9db1d6557a709`.
- Repeated both producer and verifier idempotently. The producer returned
  `already_applied`; the verifier returned the same signed SHA. Historical 11B
  parent raw SHA remained `9d00e63564691c0323fa203b76b4ee49a9fff5aa945fdb8fa000142f640e4ba0`.
- Marked Contract 08 Implemented and advanced active documentation to the Week
  4 refresh of Contracts 07 and 08, followed by Contract 09.

## Files Modified

- `README.md`, `docs/index.md`, `AGENTS.md`, `.agent/CONTEXT.md`, `.codex/QUICKSTART.md` — active checkpoint reset.
- `docs/planning/roadmap.md`, `docs/planning/data-first-football-forecasting-roadmap.md`, `docs/plans/index.md` — canonical sequence and lifecycle reset.
- `docs/modeling/` and `docs/architecture/repository_boundaries.md` — current V5 authority alignment.
- `tests/test_data_first_documentation_authority.py` — current-sequence coverage and historical-record handling.
- `docs/plans/2026-09-22/02-v5-documentation-reset-and-completion-sequence.md` — governing contract.
- `src/cks_picks_cfb/ratings/possession_live_replay_verification.py` — independent replay reconstruction and artifact verifier.
- `scripts/research/verify_data_first_possession_rating_replay.py` — Preview verifier CLI and parent-envelope checks.
- `tests/ratings/test_possession_live_replay.py` — producer/verifier agreement, perturbation, and isolation tests.

## Validation

- [x] `uv run pytest tests/test_data_first_documentation_authority.py` — 38 passed.
- [x] `uv run python contracts/validation.py` — passed.
- [x] `uv run mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.
- [x] Focused replay core tests — 3 passed.
- [x] Replay producer/verifier and historical rating regression tests — 20 passed.
- [x] Focused Ruff — passed.
- [x] Ruff formatting check — passed.
- [x] Verifier CLI help smoke test — passed.
- [x] Read-only real-parent preflight — passed; no R2 writes.
- [x] Committed-HEAD Preview preflight/apply/verify/repeat — passed.
- [x] Preview object inventory confined to the replay run prefix; historical
  11B parent checksum unchanged.
- [x] Final documentation authority tests — 38 passed.
- [x] `uv run python contracts/validation.py` — passed.
- [x] `uv run mkdocs build --strict --quiet` — passed.

## Amendments and Blockers

- Contract 08 Amendment 2 defines the isolated live replay and independent
  verification interfaces. The historical tournament code and artifacts remain
  unchanged.
- The Weeks 0–3 replay is now immutable Preview evidence. Its required Week 4
  refresh must use new Contract 07 and 08 run identities after finals stabilize.

## Handoff Notes

- **Resume at:** Run the final documentation and contract checks, commit the
  evidence checkpoint, then wait for stabilized Week 4 finals before the
  required 07/08 refresh and Contract 09.
- **Watch out for:** The historical runner and verifier are sealed to R6/Repair-v2 and the 60-candidate selection tournament. Do not add a CLI-only parent override, reuse the selection path, or apply an R2 run while the repository is uncommitted; the existing runner's apply gate requires a clean committed worktree.

**tags:** ["v5", "documentation", "authority", "contract-08", "rating-replay"]
