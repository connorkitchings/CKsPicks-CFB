# V5-10: Historical Foundation Audit

- **Status:** Draft
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** Pending; this contract does not authorize research execution.
- **Implementation log:** Pending; create `session_logs/YYYY-MM-DD/NN-v5-historical-foundation-audit.md` when authorized.
- **Commit policy:** Separate code, evidence, and report checkpoints; user controls Git operations.

## Goal and entry gate

Audit the complete V5 foundation through 2025 before any 2026 application.
The [common V5 contract](../2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
and historical-first reset are binding. Start only after this contract is
explicitly approved. The review is limited to development seasons 2015-2019
and 2021-2025; 2020 and all 2026 outcomes remain excluded.

## Scope and allowed writes

Trace exact source references through Repair, population, possession/scoring
ledgers, opponent adjustment, priors, rating updates, forecast features,
bridge fitting, and uncertainty. Review football meaning, units, exclusions,
FBS-FCS coverage, chronology, season transitions, fallbacks, code, tests, and
stored evidence. Write only versioned audit evidence and reports in the Preview
research namespace. Do not refit, tune, select, modify historical artifacts,
or write to production, Neon, catalog, web, or V4.

## Tasks

1. Build an evidence register that maps every claimed input, transformation,
   output, cutoff, and artifact to executable code and immutable source refs.
2. Test chronological isolation at each fitting and prediction boundary,
   including opponent adjustment, priors, season carryover, offsets, heads, and
   calibration.
3. Reconcile football semantics and coverage, including possession/scoring
   attribution, regulation/OT treatment, team roles, FBS-FCS games, omissions,
   and fallback paths.
4. Publish a findings register with evidence, severity, affected artifacts,
   permitted use, required correction, and closure criterion.

## Acceptance and validation

Every V5 component from Repair through forecast uncertainty has a traceable
lineage and documented audit result. Unresolved correctness findings block
downstream certification and are scoped into new implementation contracts;
the audit does not repair them. Run focused lineage/chronology tests, the full
relevant regression suite, strict MkDocs, and `git diff --check`.

## Definition of done and amendments

- [ ] Versioned audit and findings registers are published with immutable refs.
- [ ] Every finding has a disposition and closure condition.
- [ ] No unresolved blocking finding is treated as certified.
- [ ] Contract 11 dependency is explicitly resolved or amended.

Any change to methodology, data meaning, interfaces, gates, or selection
requires a separately approved amendment or contract before implementation.
