# Session: Phase 1 Data and Evidence Audit Execution

## TL;DR

- **Worked On:** Resumed the in-progress Phase 1 audit; fixed the schedule
  concat defect, validated, committed, and executed the full `resolve` +
  `audit` pipeline against Preview.
- **Outcome:** Immutable Phase 1 audit report sealed at
  `artifacts/research/data-first-football-v1/phase1/2026-09-05T1510Z-phase1-evidence-audit-v2/`
  (9 artifacts, state `complete_with_blockers`, 57 issues, all 5 research
  results `unsupported` pending Phase 2 repair).
- **Plan Contract:** `docs/plans/2026-09-05/01-data-and-evidence-audit.md`
- **Approval / Status:** User approved the detailed Phase 1 implementation
  (Amendment 1) and each commit; contract is `Implemented`.
- **Blockers:** Audit findings block certification of audited inputs (by
  design); no workflow blocker.
- **Next:** Scope Phase 2 repair from the sealed issue register.

## Context and Decisions

- The prior session left the audit tooling uncommitted with the live run not
  started. This session validated it (688 passed / 2 skipped), the user
  committed it as `3ae875e`, and the first `resolve` succeeded (21/21 roots,
  56 datasets, 4,825 captures, 52 catalog-missing blockers).
- The first `audit` attempt crashed before writing artifacts: CFBD games
  captures carry both `year`+`season` and `id`+`game_id`, so the blanket
  post-concat rename created duplicate `season` columns and
  `pd.to_numeric` raised `TypeError`. The superseded v1 run directory (resolve
  manifest only) is retained immutably.
- Fix: normalize aliases per capture before concat (`_canonical_columns`,
  prefer canonical, drop redundant alias, skip empty captures), committed as
  `ca17bc5` with a regression test. The v2 run re-executed both stages against
  the new HEAD.
- Run sealing: resolve and audit both verify `--expected-code-sha` against
  committed HEAD; run-ids are single-use because the writer rejects divergent
  bytes at the same URI.

## Work Completed

- `resolve` (v2): 21/21 evidence roots resolved; 56 dataset versions; 4,825
  source captures; 52 high-severity unresolved-lineage blockers (catalog
  registration missing for parent version_ids discovered in traversal).
- `audit` (v2): complete_with_blockers. Schedule-derived denominator of 8,521
  FBS-involved games (2015–2019 + 2021–2025, 2020 rejected). Key findings:
  - **critical postseason-capture-gap:** zero postseason capture requests; the
    approved population cannot be fully counted from captures.
  - **critical silver-fbs-fcs-exclusion:** all 1,144 FBS-FCS schedule games
    are outside Silver games (production games_v1 is FBS-FBS only).
  - **high dataset-correctness:** `preseason_team_inputs` has 434 duplicate
    key rows (196 columns).
  - **high downstream-game-outside-denominator:** silver_games 761 and
    outcomes 888 game_ids outside the denominator (production/2026 lineage
    expected); outcomes/silver left-only joins quantified.
  - **coverage:** completed FBS-FBS regular-season admitted rates —
    silver_games 100%, plays/outcomes/reconciled_team_game 50.57%
    (3,730/7,376; the 2015–2019 corpus was never ingested to Silver),
    predictions 40.63%.
  - **dispositions:** all five research results `unsupported`;
    prediction-bearing results lack immutable prediction-and-label rows for
    recomputation; `fixed_rating_baseline` remains blocked-pending-repair.
  - **hypothesis map:** fbs_fcs/first_game/asymmetric_experience/overtime are
    descriptively available from the denominator; the six football hypotheses
    are unavailable in audited evidence; model selection remains prohibited.
  - **source comparison:** CFBD retained ($4/mo of $15 ceiling); NCAA/sites
    verification-only; NOAA/Open-Meteo candidates after a Phase 2 timing
    proof; Sportradar/SportsDataIO rejected pending quotes; no purchase
    authorized.
- Validation: focused suite 16/16; full suite 689 passed / 2 skipped; ruff
  format + check clean; `git diff --check` clean.

## Files Modified

- `scripts/research/audit_data_first_evidence.py` - per-capture canonical
  column normalization; empty-capture skip; blanket rename removed.
- `tests/test_data_first_evidence_audit.py` - duplicate-alias regression test.
- `docs/plans/2026-09-05/01-data-and-evidence-audit.md` - status to
  Implemented.
- `session_logs/2026-09-05/03-phase1-data-evidence-audit.md` - this log.

## Validation

- [x] `uv run pytest tests/test_data_first_evidence_audit.py -q` (16 passed)
- [x] `uv run pytest -q` (689 passed, 2 skipped)
- [x] `uv run ruff format` + `uv run ruff check` on changed files
- [x] `git diff --check`
- [x] Both stages re-runnable only under new run-ids (immutable writer)

## Amendments and Blockers

- No plan amendment; the defect fix is in-scope implementation repair.
- Known cosmetic `FutureWarning` on games concat from all-NA capture columns;
  does not affect outputs.

## Handoff Notes

- **Resume at:** Phase 2 scoping against the sealed issue register
  (`issue-register.json`, 57 issues with phase2 actions); prioritize the two
  critical gaps (postseason captures, FBS-FCS Silver variant) and the
  2015–2019 Silver ingestion decision.
- **Watch out for:** Never reuse run-ids; the v1 run directory is superseded
  evidence; 2026 production games legitimately sit outside the development
  denominator; no production activation or subscription purchase without a
  new approved contract.

**tags:** ["data-first", "audit", "research", "phase1", "evidence"]
