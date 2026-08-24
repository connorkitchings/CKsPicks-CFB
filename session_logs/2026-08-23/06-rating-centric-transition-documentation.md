# Session: Rating-Centric Transition Documentation

## TL;DR

- **Worked On:** Implemented the approved documentation contract for the
  current V4 architecture, rating-centric 2027 target, phased migration, and
  protected prospective evaluation policy.
- **Outcome:** Existing authority documents now consistently preserve V4 as the
  2026 production champion while defining the target measurement → adjustment
  → rating/state → prediction → optional residual → probabilistic output →
  market flow.
- **Plan Contract:**
  [`docs/plans/2026-08-23/rating-centric-transition-documentation.md`](../../docs/plans/2026-08-23/rating-centric-transition-documentation.md)
- **Approval / Status:** User explicitly authorized implementation on
  2026-08-23; contract is `Implemented`.
- **Blockers:** None.
- **Next:** Use a fresh Sol planning session for Phase 1's architecture audit,
  conceptual measurement catalog, and rating-engine requirements contract.

## Context and Decisions

- The current architecture is documented as immutable canonical data →
  team-game measurements → recency aggregation → iterative opponent adjustment
  → point-in-time matchup features → empirical-Bayes shrinkage → V4 routing →
  spread/total prediction → market edge/publication.
- Ratings-first is an approved architecture direction, not an implemented
  model. Exact estimator, scale, priors, uncertainty method, special teams,
  residual ML, and artifact interfaces remain deferred.
- Opponent adjustment remains primarily at the measurement layer for the
  minimum baseline. Rating-assisted adjustment is a separately attributable
  challenger to prevent schedule-strength double-counting.
- V4 remains unchanged in 2026 and is the comparison benchmark. Rating
  candidates remain research/shadow-only until a separate promotion contract.
- Each candidate must freeze its design before inspecting eligible 2026
  outcomes. Protected outcomes cannot be reused for iterative tuning.
- Scoped stale facts were corrected: modularized source paths, the verified
  60% coverage posture, and the August 21 predictions reveal.

## Work Completed

- Added the approved current/target architecture and Phase 0–5 transition to
  the strategic roadmap.
- Reframed future feature work as an interpretable measurement system with
  conceptual families, provenance, exposure, adjustment, and redundancy
  requirements.
- Established the continuous credibility-weighting successor alongside the
  authoritative V4 route contract.
- Added ordered rating-quality, game-prediction, and market-value evaluation,
  plus the protected prospective 2026 policy.
- Recorded the architecture decision and aligned contributor/assistant entry
  points without creating a new blueprint or navigation entry.

## Files Modified

- `docs/plans/2026-08-23/rating-centric-transition-documentation.md` — approved
  and implemented task contract.
- `docs/planning/roadmap.md` — current-state, target-state, and Phase 0–5
  transition roadmap.
- `docs/modeling/features.md` — measurement-system direction and scoped
  as-built corrections.
- `docs/modeling/early_season_regimes.md` — V4 benchmark and continuous-state
  transition.
- `docs/modeling/evaluation.md` — ordered evaluation and protected 2026 policy.
- `docs/decisions/decision_log.md` — approved 2027 architecture decision.
- `AGENTS.md`, `.agent/CONTEXT.md`, `README.md` — aligned orientation and scoped
  current-state corrections.
- `session_logs/2026-08-23/06-rating-centric-transition-documentation.md` —
  implementation evidence and handoff.

## Validation

- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`
- [x] Internal documentation targets exist; MkDocs resolved the edited pages.
- [x] Terminology review confirms V4 remains 2026 production, ratings-first is
  the approved future direction, and 2026 is protected prospective evidence.
- [x] Changed-path review confirms no source, configuration, schema, model,
  artifact, database, or production file changed.

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Plan Phase 1 as a documentation/research contract: audit the
  actual raw/derived fields, build the conceptual measurement catalog, map
  overlapping responsibilities, and define rating-engine requirements before
  selecting an estimator.
- **Watch out for:** Do not use protected 2026 outcomes before a candidate's
  design and eligible cutoff are frozen; do not modify V4 production as part of
  foundational rating research.

**tags:** ["architecture", "ratings", "modeling", "measurement", "roadmap"]
