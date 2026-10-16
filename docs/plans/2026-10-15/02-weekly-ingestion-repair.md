# Repair weekly ingestion and stage an honest Week 8 template

- **Status:** Superseded — the operational ingestion repair was delivered by Phase 1 of
  [the review contract](01-review-fixes-and-v5-streamline.md) (`2807e087`) via the
  `build_season_revision.py` controller flow, which replaces this contract's manual
  checklist design. The log-13 correction and fixture tests were integrated under
  [03-weekly-ingestion-repair-integration](03-weekly-ingestion-repair-integration.md);
  the manual runbook section and the Week 8 template were deliberately rejected.
- **Created:** 2026-10-15
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation of this exact approved plan in this chat.
- **Implementation log:** session_logs/2026-10-15/06-weekly-ingestion-repair-implementation.md
- **Commit policy:** User-controlled git operations; plan may be committed with implementation.
- **Import note:** Committed on `codex/weekly-ingestion-repair` (`bb2f1fe8`) but never
  merged; imported to `dev` renumbered from `01-repair-weekly-ingestion-and-w8-template.md`
  to avoid collision with `01-review-fixes-and-v5-streamline.md`.

## Goal and acceptance

Fix the three broken connections (request inventory, market capture identity, cumulative input refresh) using existing commands and builders, fixture-only validation, and an honest Week 8 template. Preserve all original uncommitted work. No new orchestration command, schema, model, numerical changes, live captures, paid requests, database mutations, or release activation. Complete only when the checklist wiring has meaningful fixture coverage and required scoped gates pass; future operational data readiness remains separate.

## Baseline and constraints

Baseline dev baf6b1b8; source checkout contains modified weekly_runbook.md and untracked revision_manifest_w8_v1.json plus session log13. These three files are copied intact into the isolated worktree before repairs; primary checkout remains untouched. Existing season preparation derives observations/scoring events when imported pins are absent. Never use ./data or real credentials during tests. Block actual provider/network/database access in fixture harness. Historical refs must come from accepted explicit lineage, never an unqualified latest query. Preserve required release/rehearsal rules and accepted nullable PPA/corrections.

## Ordered changes

1. Runbook: establish explicit Preview targeting, verify R2 configuration, require Bronze dual-write/catalog registration. Capture season schedule including scores. Build a pinned schedule/canonical-policy request inventory. Ingest completed-week plays and game_stats separately with --request-inventory and IDs RUN_ID:plays / RUN_ID:game_stats. Record exact capture IDs; combine retained earlier-week captures with new ones for cumulative Silver games/outcomes/plays/stats. Use existing team-game builder for byplay/drives/reconciliation; missing coverage or blocking reconciliation stops advancement.
2. Markets: define one unique RUN_ID per attempt. Capture upcoming-week CFBD lines under RUN_ID:betting_lines and Odds API quotes under RUN_ID:market_quotes. Show estimate before explicit --confirm. Snapshot gets same RUN_ID and honest as-of strictly after capture completion. Preserve historical quote history in cumulative season input, identify retained/new captures explicitly, and reconcile full FBS spread/total coverage. Record capture timestamp, missing IDs, next refresh and gates.
3. Rename untracked Week 8 manifest to revision_manifest_w8_v1.template.json. Retain Week7 post-cutoff 2026-10-18T15:00:00Z and Week8 pre-cutoff 2026-10-20T18:00:00Z. Record expected 56 games and 2026-10-20T23:00:00Z first kickoff as prior schedule evidence requiring fresh operational reconciliation. Replace mutable refs with pending URI and <PENDING_POST_W7_INGESTION_SHA256> placeholders and capture time with pending timestamp. Template deliberately fails operational validation. Document creating original operational manifest only after fresh validated/hashes exist. Omit imported observations/scoring_events so real season preparation derives them. Normal live mode before kickoff; --reconstruct-next-week is deliberate retrospective reconstruction, not triggered by merely having mid-week scheduled games.
4. Correct October14 log13 to retract operational-readiness/runnable/no-blockers claims and defer readiness to post-Week7 Sunday October18 gate. Update plan index and create planning/implementation logs; no status.md serving changes.

## Validation

Exercise inventory → entity-specific captures → snapshot selection with fake providers/catalog/storage; missing inventory fails before provider requests and mismatched IDs cannot produce usable snapshot output. Season fixtures prove cumulative coverage, native derivation, historical quote retention, and rejection of missing finals/drives/reconciliation or changed checksums. Placeholder template fails validation. Run focused inventory/market/Silver suites, full season suite, scoped lint, contracts validation, MkDocs and git diff --check. No live storage/catalog or paid requests. Preserve existing tests and original files; no broad dirty-worktree formatting.

## Handoff and amendments

Persist approved contract and planning log before fresh Terra workers implement in this isolated worktree. Mark In Progress during execution, Implemented only after required local validation; clarify future operational gates. Nonmaterial mechanical amendments may proceed if scope/acceptance remain unchanged; material conflicts return for review. Future capture hashes remain pending. Git operations remain user-controlled.

## Implementation evidence

Implemented in the isolated worktree `weekly-ingestion-repair/ckspicks-cfb`; primary checkout and its three original uncommitted files were preserved. No application code, schema, numerical behavior, live captures or activation changed.

- Focused ingestion/inventory/market/Silver and complete season suites: 418 passed in 26.92s. Strengthened real-ingester mixed FBS–FBS/FBS–FCS fixture then reran: 7 passed in 1.86s.
- Scoped Ruff check/format, contracts validation, quality registry (32 checks/zero problems), MkDocs and diff whitespace checks passed.
- Three review lenses completed: design/simplicity, functionality/testing and security/reliability. Corrected two findings: inventory must pin full raw FBS-involved schedule instead of serving Silver; scalar lineage extraction must fail before optional-parent builder arguments are assembled. Reviewers verified both corrections.
- Future operational readiness remains deferred until October 18 post-Week-7 ingestion, provenance/hash validation, fresh schedule/market reconciliation and Preview rehearsal. The template intentionally fails operational validation.
