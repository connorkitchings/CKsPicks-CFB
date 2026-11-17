# Session: V5 offensive and defensive ratings audit implementation

## TL;DR

- **Worked On:** Independent Week 9 v2 offense/defense arithmetic and source audit, separate active-release source/projection checks, and actual matchup period selection.
- **Outcome:** Audit CLI, pure computations, focused tests, report and JSON evidence implemented and exercised against read-only R2/Production. Calculations/projections agree; narrow case ordering is sensitive to partial-quarantine policy.
- **Plan Contract:** [V5 ratings audit](../../docs/plans/2026-11-08/v5-offense-defense-ratings-audit.md)
- **Approval / Status:** Owner explicitly requested implementation on 2026-11-08. Contract In Progress solely for unresolved original-artifact verification and documented evidence limitations.
- **Blockers:** Historical original prepared manifest/parquet files and active original feature/rating/prediction parquet files unavailable. No reconstructed artifacts were substituted for them.
- **Next:** Restore original prepared artifacts, supply checksum-matched `--run-manifest` arguments, rerun original feature/rating comparisons. Model corrections, UI changes and retention changes require separate scope.

**tags:** ["implementation", "ratings", "audit", "read-only"]

## Context and Decisions

Worktree `.worktrees/codex-v5-ratings-audit`, branch `codex/v5-ratings-audit`, starts at `7505a4c20940063eeb268c36e9fb80b71d311400`. Intervening operations changes from the original planning baseline do not modify audited estimator/web calculations. Preserve the concurrent rollover worktree and root checkout. The owner subsequently authorized committing this work with "go ahead with commit"; retain the separate planning and implementation commits. No push, release, provider captures or production writes were performed.

The historical scope is ten pregame generations (0–9) and nine post-week generations (0–8), excluding completed Week 9 observations. An independent active release capture is read under repeatable-read/read-only isolation and its own pinned inputs are verified. Operational R2 uses its matching credentials through `ReadOnlyStorage`; the source-only historical bucket is not used for operational rebuilt inputs. Secrets were not printed.

## Work Completed

- Persisted the approved five-section contract and planning log, then delegated separate pure-math/tests and CLI/tests file groups to fresh implementation workers.
- Added independent four-pass adjustment, posterior/prior reconstruction, role-scale and population diagnostics, per-game contribution checks, exact-key/provenance comparisons, and source-quarantine classification.
- Added scoring-side paired validity checks, original scoring/possession traces, one/two-hop SEC influence paths, and individual/joint diagnostic exclusions.
- Implemented hash-bound original artifact inspection, protected output paths, sanitized failures, actual TypeScript period selection, source-qualified serving comparisons and both-head feature comparison support.
- Verified all 19 component generations and nine adjusted generations in each evidence scope. Rebuilt and matched 1,776 active-source PPP rows. All 500 games in each scope have both forecast heads, and all four page-selected versus projected-pregame rating fields agree exactly.
- Documented the case: Florida's larger opponent adjustment explains its 1.856944 versus Georgia's 1.839377 offensive rating; stronger Georgia priors narrow the gap. Defensive values and directions reproduce.
- Documented 98 excluded role observations over 44 games, with 39 partial and five whole-game quarantines; all 88 scoring pairs agree in validity. Removing retained edges of the three partially quarantined SEC games reverses the narrow offensive ordering diagnostically. Production inputs are unchanged.
- Verified exact scales and demonstrated equal exposure-weighted historical centers despite unequal team-equal centers. Historical division labels use the 2026 catalogue and do not pretend to establish exact 2025 membership.
- Searched local season artifacts/worktrees, relevant temporary files, the configured unmounted external data root, GitHub weekly receipts and operational R2 prepared-run prefixes. Recovered the active original receipt manifest only. Missing original parquet checks remain unavailable.
- Verified deployed web commit and the three relevant loader/helper file hashes against the checkout through connected Vercel/GitHub read tools; recorded safe provenance in JSON. No live release IDs were copied into the report or evidence.
- Ran design, functionality/testing, security/reliability, external-boundary and performance reviews. Fixed preseason `k=None` false positives, FBS-only adjusted projection comparison, hidden original-state discrepancies, provenance wiring, source-independent active checks and output/error handling. Final rechecks found no remaining actionable issues.

## Files Modified

- `scripts/analysis/audit_v5_ratings.py` — read-only CLI and evidence/report rendering.
- `src/cks_picks_cfb/audit/v5_ratings.py` — independent arithmetic and source checks.
- `tests/test_v5_ratings_audit.py`, `tests/test_v5_ratings_audit_cli.py` — behavioral/boundary regressions.
- `docs/modeling/v5_offense_defense_ratings_audit_2026.md`, `docs/modeling/evidence/v5_offense_defense_ratings_audit_2026.json` — reviewed findings and machine evidence.
- Contract, plans index, `mkdocs.yml`, planning log and this log — lifecycle/navigation/evidence.

## Validation

- [x] `uv run --no-sync pytest tests/test_v5_ratings_audit.py tests/test_v5_ratings_audit_cli.py tests/ratings/test_possession_intended_update.py -q` — 30 passed.
- [x] Scoped `uv run --no-sync ruff check` — passed for four new Python files.
- [x] Scoped `uv run --no-sync ruff format --check` — four files already formatted.
- [x] Final approved CLI execution with explicit R2 backend and restricted Production wrapper — succeeded; final script/math SHA-256 values match the evidence.
- [x] `uv run --no-sync mkdocs build --strict --quiet` — passed (Material's informational banner is not a build warning).
- [x] Report/JSON consistency and hygiene checks — no database URLs or live release/run identifiers in committed evidence; JSON is valid and approximately 3.5 MB.
- [x] `git diff --check` — passed.

Commands used the existing project environment with `UV_PROJECT_ENVIRONMENT` pointing to the root virtual environment, `UV_CACHE_DIR` in temporary storage, and `PYTHONPATH=src:.` in the isolated worktree. No dependency files changed. No web production code changed, so browser release gates were not applicable.

## Amendments and Blockers

See the contract's mechanical amendments for baseline reconciliation, unavailable-original operation and reviewed provenance. The contract is not marked Implemented because original forecast-artifact verification remains incomplete. Arithmetic agreement and original manifest digests do not certify missing original feature bytes. Provider source truth and exact historical division membership remain bounded evidence limitations.

## Handoff Notes

- **Resume at:** Review the report and restore original prepared artifacts if available; run the same CLI with their original checksum-bound manifests. The audit command can already compare those files.
- **Watch out for:** CLI reruns replace the generated Markdown/JSON. Reattach separately verified deployment provenance and review the narrative after a new capture. Do not promote diagnostic quarantine exclusions into V5 behavior.
- **Commit proposal:** Keep the approved planning contract/log as a separate documentation commit, then `feat(audit): add independent V5 ratings and lineage audit` for implementation/report/tests/navigation. User controls staging, commits and integration into `dev`.
