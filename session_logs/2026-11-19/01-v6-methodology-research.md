# Session: V6 methodology research survey

## TL;DR

- **Worked On:** Six-track web research pass on rating systems, rating architectures, totals modeling, sportsbook practice, evaluation statistics and point-in-time input feasibility, written up as one survey.
- **Outcome:** New `docs/research/v6-methodology-survey-2026-11.md` with ranked recommendations, each carrying a policy label and a feasibility rating, plus a gap map to Operational V5 gaps. Evidence is mostly secondary or non-CFB; the survey says so per claim.
- **Plan Contract:** `N/A (fast path)` — documentation only, no code, model, config or production change.
- **Approval / Status:** Owner-requested research plan for this session; docs-only on local `dev`, committed locally, not pushed.
- **Blockers:** None. Several primary pages (SP+/FEI methodology, Sagarin, Massey, PredictionTracker, KenPom) could not be fetched.
- **Next:** Owner decisions listed in section 8 of the survey (L3 policy question, 90% vs 95% interval, 2026 as confirmation season, totals diagnostic as first post-2026-12-13 contract).

**tags:** ["research", "v6", "methodology", "docs-only"]

## Context and Decisions

- V5 is frozen for the 2026 record; model research starts after the 2026-12-13 final close, so this work is documentation only.
- All V5 figures use Operational V5 from the baseline audit (13.7151 margin MAE, 13.3709 total MAE, predicted-total SD 1.57 vs 16.90, neutral-site margin bias -2.69 on 126 games, stage-0 bias +7.51). The backlog's older -4.32 neutral-site figure includes postseason games and was not used.
- Market views are labelled L2 or L3 per Amendment 5; none is recommended as an input.

## Work Completed

- Ran six parallel research agents; synthesized by theme and flagged thin evidence (three of the six had LOW or LOW-MEDIUM confidence).
- Wrote the survey, added it to the research nav and linked it from backlog section B.

## Files Modified

- `docs/research/v6-methodology-survey-2026-11.md` — new survey
- `mkdocs.yml` — nav entry next to the V6 architecture design page
- `docs/planning/offseason-2027-backlog.md` — one-line link in section B
- `session_logs/2026-11-19/01-v6-methodology-research.md` — this log

## Validation

- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`
- [x] `git status` shows only the four files above; `docs/status.md` unchanged

## Amendments and Blockers

- Confirmed gap: `ratings_lab/evaluation.py` `paired_comparison` returns 90% intervals; protocol adoption thresholds use 95% (Amendment 2 unapplied). Not changed here.

## Handoff Notes

- **Resume at:** Session complete; next step is the owner decisions in survey section 8.
- **Watch out for:** The survey's power table and sigma estimates are the survey's own arithmetic (game-level iid assumption). CFBD point-in-time verdicts are unverified until checked against the live API.

## Follow-up: owner decisions and reconciliation (same day)

- **Owner decisions applied:** stay L1 for the first V6 wave; two-sided 95% paired interval (Amendment 2) with season/week block resampling as primary; 2026 is the one-shot confirmation holdout for new frozen finalists; totals diagnostic is draft only; live CFBD audit approved; no push, no amend.
- **Survey reconciled with steps 4C and 4D:** the first draft wrongly treated bridge specification and the neutral-site flag as untested. Both were run 2026-11-15 with no gain (flat total is a signal limit; the venue flag overshoots). The survey now frames the totals diagnostic around what 4C did not test and sends the fix upstream if it is also null. The existing drive-sample declaration (`docs/modeling/offseason_totals_drive_sample.md`) is referenced instead of duplicated.
- **Amendment 2 applied:** `paired_comparison` in `src/cks_picks_cfb/ratings_lab/evaluation.py` now takes `confidence_level` (default 0.95) and reports `lower`, `upper`, `confidence_level` (the old `lower_90`/`upper_90` keys are gone); two scripts that read the old keys were updated (`scripts/research/run_v6_tournament.py`, `scripts/research/re_evaluate_checkpoint.py`). Recorded in the protocol, `protocol.yaml` and the audit contract. A game-level sensitivity interval is declared alongside.
- **Measured sigma and design effect (read-only, scratchpad scripts):** sigma is 1.1-1.4 for variants close to Operational V5, about 4.1 for one first-boundary margin variant and 8.3-8.8 for structurally different margin models; season-week design effect mostly 0.9-1.6; team clustering is larger for totals (home-team 1.4-1.9). Candidates from steps 4B to 4D have no per-game outputs on disk and are not covered.
- **Live CFBD audit (91 calls, Tier 2):** no endpoint has an as-of timestamp; portal data starts 2021; `/roster` behaves as an archive but class-year is unreliable; FCS plays and drives are present in 15 sampled games; weather has no forecast-vs-observed marker and looks gridded; `/lines` has no capture time and `spreadOpen` is empty before 2021. Key never printed or stored.
- **Draft contract:** `docs/plans/2026-11-19/pooled-team-score-totals-diagnostic.md`, linked from `docs/plans/index.md`. Nothing is approved to run.

## Follow-up files modified

- `docs/research/v6-methodology-survey-2026-11.md`, `docs/plans/2026-11-19/pooled-team-score-totals-diagnostic.md` (new), `docs/plans/index.md`
- `docs/plans/2026-11-12/02-offseason-research-protocol.md`, `conf/research/offseason_2027/protocol.yaml`, `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`
- `src/cks_picks_cfb/ratings_lab/evaluation.py`, `tests/ratings_lab/test_platform.py`, `scripts/research/run_v6_tournament.py`, `scripts/research/re_evaluate_checkpoint.py`

## Follow-up handoff

- **Watch out for:** `run_v6_tournament.py` gates on the interval lower bound, now the 2.5th percentile, so its promotion gate is stricter than before. Scratchpad sigma and CFBD audit outputs are session-local and not committed.
