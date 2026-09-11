# Data-First Football Forecasting Roadmap

> **Status:** Approved 2026-09-05; corrective replacement approved 2026-09-08
> **Production authority:** V4 remains unchanged
> **Research namespace:** `artifacts/research/data-first-football-v1/`

## Purpose

Improve spread and total forecasts by establishing trustworthy data, validating
football measurements, selecting simple team ratings, and evaluating frozen
forecasts prospectively. Authentic timestamped lines are comparison evidence
after football-model evaluation. Bet selection, staking, bankroll management,
and betting-policy optimization are deferred.

Preserving the working system is mandatory. The program does not modify V4
production predictions, weekly operations, publication, bundle loading, or
rollback behavior. Corrected research behavior receives new versioned
identities when a shared change could affect production.

## Governing boundaries

- Target all games involving at least one FBS team, including FBS-FCS games.
- Develop historically on 2015-2019 and 2021-2025; exclude 2020 everywhere.
- Treat 2025 as development evidence only in this new program. Existing
  experiments retain their original evaluation contracts.
- Use future predictions frozen before kickoff as independent evidence.
- Prefer automated sources and simple, interpretable benchmarks.
- Keep recurring data subscriptions at or below $15/month total, including the
  existing reported $4 CFBD subscription. Purchases require separate approval.
- Permit recent-era feature families on declared shorter windows when coverage
  and chronological evaluation requirements pass.
- Let evidence determine timing; there is no deadline for replacing V4.

## Architecture

```text
Current production (preserved)
R2 data/artifacts -> V4 inference -> Neon serving state -> Vercel

New research (isolated)
audited data -> football measurements -> opponent adjustment
-> offense/defense team state + uncertainty -> spread/total forecast
-> prospective evaluation -> timestamped line comparison
```

Top-level responsibilities remain stable: reusable Python under
`src/cks_picks_cfb/`, production entry points under `scripts/pipeline/`, active
research entry points under `scripts/research/`, exploratory work under
`research/`, configurations under `conf/`, and current authority under `docs/`.

## Ordered phases

The [approved review and replacement contracts](../plans/2026-09-08/transformation-review-and-authority-reset.md)
are the current authority. Implemented engineering and verified predictive
eligibility are separate statuses.

| Stage | Contract | Exit decision |
| --- | --- | --- |
| Repair | [Repair and recertification v2](../plans/2026-09-08/data-first-repair-and-recertification-v2.md) | Population and auxiliary semantics are recertified; rejected families are explicit. |
| 3 | [Compact-state measurement/core benchmark v2](../plans/2026-09-10/phase3-v2-compact-tournament-state.md) | Certified Preview apply `phase3-v2-compact-state-20260910-r2` (2026-09-11): preflight, verifier, and idempotent rerun passed; selection `quality_core_epa_split`. |
| Methodology | [Possession-based rating methodology specification](../plans/2026-09-11/possession-rating-methodology-specification.md) | Decision-complete first-generation specification persisted in [possession rating methodology](../modeling/possession_rating_methodology.md). |
| Replacement contracts | Phase 4A–6 replacements or reaffirmations | Define rating estimation, score forecasting, and prospective evidence from the methodology annex. |

Repair v2 is implemented and independently verified in Preview. Phase 3 v2 is
certified: its no-write Preview preflight, immutable materialization,
independent verification, and idempotent rerun all passed on 2026-09-11. The
possession-based rating methodology is specified (2026-09-11); possession
measurements remain uncertified until the measurement certification contract
passes. The September 8 Phase 4A–6 contracts retain their approved historical
records but remain on execution hold pending replacement contracts; their
prior/updater grid is reaffirmed only as carried forward onto the possession
rating definitions by the methodology contract. Phase 7 remains a future
promotion contract.
Ratings are the mandatory forecast foundation; direct-core Ridge and polls are
diagnostic-only. Auxiliary football information is tested inside preseason priors.

## Current checkpoint

**Corrective work is complete and the methodology is specified; replacement
execution contracts are next.** The 2026-09-08 review's findings (same-game
context leakage in Phase 4B, constant coaching features, incorrect roster
continuity, and 32 completed schedule games omitted from the Phase 3
population) were repaired by Repair v2, and the corrected Phase 3 v2 benchmark
was certified on 2026-09-11. The old Phase 4B retained manifest remains
prohibited as a forecasting parent; its 11.36% apparent margin gain is not
valid pregame predictive evidence.

Phase 0 alignment, corrected Phase 1 dispositions, and unaffected Phase 2
engineering evidence remain retained. Phase 3 EPA-only and Phase 4A
`rho_0_60__exposure` selections remain historical reduced-population references;
their descendants require repair and renewed selection. The review's
[evidence table](../plans/2026-09-08/transformation-review-and-authority-reset.md#review-evidence-and-dispositions)
is the canonical record of findings, actual metrics, population counts, checksum
types and permitted uses.

The current next step is to issue the possession measurement certification
contract (annex A of the [methodology specification]
(../modeling/possession_rating_methodology.md)), followed by rating estimation,
score forecasting, and prospective evaluation contracts. The Phase 3 v2 output
(`phase3-v2-compact-state-20260910-r2`, selection `quality_core_epa_split`) is
benchmark evidence, not automatic authority for the possession estimator.
Historical sequence: [Phase 3](../plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md),
[Phase 4A](../plans/2026-09-07/02-phase4a-context-free-rating-selection.md),
[Phase 4B](../plans/2026-09-07/03-phase4b-target-context-selection.md),
[Phase 5](../plans/2026-09-07/04-phase5-final-spread-total-selection.md), and
[Phase 6](../plans/2026-09-07/05-phase6-prospective-evidence-and-market-diagnostics.md)
are superseded execution authority. In that historical sequence, Phase 4B, not Phase 3,
first consumed the Phase 2e auxiliary manifest. That historical admission does
not certify repaired prior features or authorize current forecasting.

## Historical predecessor identities (use subject to review dispositions)

| Phase/evidence | Immutable identity and code binding | Timing and permitted use | Activation |
| --- | --- | --- | --- |
| Phase 0 alignment | [Implemented contract](../plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md) and its compatibility baseline | Repository boundary and V4-regression protection; no model input | Not applicable |
| Corrected Phase 1 audit v3 | `artifacts/research/data-first-football-v1/phase1/2026-09-06T0055Z-phase1-evidence-audit-v3/` | Preserves the exact unsupported/correction-required dispositions of historical results | Research evidence only |
| Phase 2d audit | `phase1/2026-09-06T2358Z-phase2d-recertification-v2/audit-v5.json` — SHA `0fd8a32a13ce64a261fa8a0179cdaa1de1cb93e428e362d50ad0aa9970c7761f`, code `285422026816bc933279a69e997021847b4bfb31` | Certifies core lineage, omissions, coverage, and timing for measurement construction | False |
| Phase 2d automation admission | `phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/automation-admission.json` — SHA `7a46adfaff0bcb89b86f244c586d93085557ba3119699da81824ffa4e83f5518`, code `285422026816bc933279a69e997021847b4bfb31` | Enables only the verified Preview capture workflow; it is not a model artifact | False |
| Phase 2d core handoff | `phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/eligibility-manifest.json` — SHA `cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760`, 70 exact refs | Historical Phase 3 parent; current use is repair input | False |
| Phase 2e auxiliary capture set | `phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/capture-set.json` — SHA `c2ff56b084e58b5cd159f884171df05187746c0dc40b42817912866a540de650`, code `80aba46df8b5e92959024510140cbd06de6b3b3e`, 63 Bronze captures | Reconstructed-only historical evidence; captures cover recruiting, returning production, coaching, roster continuity, rankings, and market references | False |
| Phase 2e auxiliary handoff | `phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json` — SHA `d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad` | Six Preview datasets: recruiting, returning production, coaching, roster continuity, strictly lagged polls, and reconstructed market references. Historical football-context admission requires semantic recertification; markets remain post-selection diagnostics only. | False (`eligible_reconstructed_only`) |
| Phase 3 retained core | `phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json` — raw SHA `c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234`, code `6addf437e7d76f5e39f198c41acd47c4e9b2c5b4`, selected `epa_only` | Historical reduced-population Phase 4A parent; 302,702 observations, 1,210,808 adjusted measurements, 202,048 fold predictions | False |
| Phase 4A retained rating | `phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json` — canonical manifest checksum `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612`, code `3547844111c90f71c85760cbf841ae11787591a8`, selected `rho_0_60__exposure` | Historical reduced-population Phase 4B parent; 101,024 fold predictions, 284,896 rating states, 142,448 team states | False |

The earlier checksum-invalid Phase 2d eligibility artifact is superseded. The
first partial Phase 2e apply is unregistered diagnostic evidence and has no
eligible downstream use. The corrected source inventory records 1,300
returning-production Bronze captures and 26,844 betting-line Bronze captures;
lower compatibility-projection counts are not source inventory totals. Game
statistics are reconciliation evidence, not a separate required play source;
the obsolete 2016–2018 play-gap claim is not current authority.

Historical R2 and direct early-game results keep their exact Phase 1
dispositions. The former R2 winner is unsupported for this program and cannot
enter Phase 4 without renewed evidence.

## Authority transition

This roadmap replaces the pending R3/R4 sequence and the unfinished research
portion of the historical-expansion roadmap. The 2026-09-05 and 2026-09-07 Phase 3–6 contracts
are superseded historical planning records; the 2026-09-08 corrective sequence
is the sole active path. Completed R1/R2 work, candidate v1, and direct early-game
research remain immutable historical evidence subject to Phase 1 audit
disposition. V4 remains the production benchmark and rollback authority
throughout.
