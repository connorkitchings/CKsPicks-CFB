# Session: Possession-Based Rating Methodology Planning

## TL;DR

- **Worked On:** Sol planning session for step 3 of the approved handoff
  queue — the possession-based rating methodology specification.
- **Plan Contract:** `docs/plans/2026-09-11/possession-rating-methodology-specification.md`
- **Approval / Status:** User approved. The contract is `Approved`; Terra
  implementation (documentation tasks 1–5) is pending in a fresh task.
- **Outcome:** Every methodology decision area is settled: two competing
  rating definitions (true points per possession vs EPA per possession), full
  Phase 4A v2 prior/updater grid carried forward (including the net-new
  Kalman challenger), plays-per-drive volume proxy for v1, overtime excluded
  from rating evidence, and non-offense scoring as a translation-only state.
- **Blockers:** None.
- **Next:** Open a fresh Terra task with the implement-plan skill against the
  contract; afterward, author follow-on contract A (possession measurement
  certification).

## Context and Decisions

Prerequisite state verified at planning time: Phase 3 v2 certified Preview
apply completed earlier this session (`phase3-v2-compact-state-20260910-r2`,
verifier `verified`, idempotent rerun `already_applied`), so the methodology
stage was unblocked per the roadmap queue.

Three parallel read-only explorations grounded the plan: (1) Phase 3 v2
tournament internals — the selected `quality_core_epa_split` composition,
six adjusted components, equal-weight z composites, margin/total targets, and
gates; (2) possession-level data inventory — drives schema, eligibility
mechanics, the true-drive-points reconstruction, OT/defensive/ST scoring
identifiability, clock/tempo gaps, and FCS coverage; (3) historical estimator
mechanics — exact credibility/decay equations, the held Phase 4A v2 grid, the
2026-09-08 review's prior-feature findings, and evaluation rules.

User decisions (2026-09-11):

1. **Rating quantity:** compete both true-points-per-possession and
   EPA-per-possession definitions; the estimation tournament decides.
2. **Prior/updater grid:** carry the full Phase 4A v2 grid (6 priors × 5
   updaters) onto the new definitions.
3. **Possession volume v1:** plays-per-drive proxy; clock reconstruction
   deferred to a later challenger.
4. **Edge cases:** accept defaults — OT excluded from rating evidence;
   defensive/ST scores feed a separate non-offense translation state only.

Remaining decisions were settled by research-informed defaults documented in
the contract (D2 possession eligibility, D3 attribution, D5 no field-position
normalization in v1, D6 four-pass adjustment reuse, D7 z-scale with native
carried values, D10 uncertainty, D12 closed-form + bridge translation, D13
FCS/missing patterns, D14 evaluation) with a provisional-constants table that
downstream contracts must freeze from representative data.

## Work Completed

- Investigated the evidence base (three parallel explorations; authority
  docs: roadmap, documentation-alignment contract, rating requirements,
  measurement catalog, evaluation rules).
- Drafted, reviewed with the user, and persisted the approved methodology
  specification contract with the follow-on contract interfaces annex.

## Files Modified

- `docs/plans/2026-09-11/possession-rating-methodology-specification.md` -
  approved methodology contract (this planning task's only repo write).
- `.opencode/plans/possession-rating-methodology-specification.md` - staged
  copy used while plan mode blocked repo writes (scratch; not authoritative).

## Validation

- [ ] `uv run mkdocs build --strict --quiet` — run in this persistence step.
- [ ] `git diff --check` — run in this persistence step.

## Amendments and Blockers

- None. Note for the record: a first attempt to persist the contract during
  plan mode was permission-blocked; the staged `.opencode/plans/` copy was
  written instead and the canonical file was persisted after the mode switch
  (one D14 typo corrected in transfer).

## Handoff Notes

- **Resume at:** Fresh Terra task:
  `Use the repository-local implement-plan skill and implement the approved contract at: docs/plans/2026-09-11/possession-rating-methodology-specification.md`
- **Watch out for:** The contract authorizes documentation only — no
  estimator code, no data writes. Authority tests may need alignment (Task 5);
  do not weaken execution-hold or lineage checks. Provisional constants are
  to-freeze, not to-tune.

**tags:** ["methodology", "possession-ratings", "planning", "data-first", "research"]
