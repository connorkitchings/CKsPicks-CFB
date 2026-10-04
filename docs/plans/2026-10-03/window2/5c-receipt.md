# Window 2 Step 5C: exit receipt (draft for user review)

- **Status:** Built, verified locally, not reviewed or signed. **Nothing was written to R2, Neon or any database; no Silver or Gold dataset was published.** The ledgers below exist only in a local scratch directory; the decisions and report are committed under `5c-data/`.
- **Authority:** [Appendix A, 5C](data-contracts-and-certification.md) and its Amendment 2; user directives of 2026-10-04.

## Result (historical 2015-2019, 2021-2025; 8,936 games)

| Decision | Groups | Net points |
|---|---|---|
| Admitted (corroborated by CFBD drives) | 1,416 | +104 |
| Reverted, contradicted by usable drives | 28 | +56 not admitted |
| Reverted, unverified | 1,749 | +6,789 not admitted |
| **Total changed groups** | **3,193** | |

- The 402 recovery groups that were uncorroborated all reverted; only 8 recovery groups (104 points) are admitted. Every other point-changing group reverts, so the admitted ledger adds 104 points to the baseline in total.
- Admitted ledger: 85,457 scoring events (baseline 86,937; unconstrained R1 82,416). 9,803 events are in changed groups. Admitted groups by cause: dip/restore 1,389, category or possession reassignment 22, incomplete stream 4, restoration above eight 1. No final-cap group is admitted.
- By season, admitted groups: 2015 62, 2016 73, 2017 90, 2018 51, 2019 41, 2021 241, 2022 216, 2023 212, 2024 237, 2025 193. Full tables in `5c-data/admission_report.json`; per-group decisions in `5c-data/admission_decisions.csv` (sha256 `dcabd4e6...97294db`; report `ba1a1c03...e27609`).

## Verification (independent)

- `verify_admitted_ledger` returned **ok with no problems** on the full corpus (about 11 minutes, 1.52 million plays): the baseline reproduces, the independently derived candidate has 82,416 events (equal to the 5A candidate count), 9,803 changed events all belong to a decided group, no group crosses a linked conversion, the admitted ledger equals the derivation from the decisions, reverted groups equal baseline exactly, and the admitted group count is 1,416.
- The admitted ledger converts to `football_scoring_ledger_v1` with **0 contract problems** (85,457 rows).
- Unit tests (`tests/test_admission_5c.py`, 9) include tampered admitted ledgers, uncovered changes, a changed baseline, a phantom group event and a wrong admitted count; full suite with CI flags 1,824 passed, 9 skipped; ruff clean.

## Materiality (raw PPP only; my computation, not independently verified)

Computed on admitted versus baseline eligible-offense points per eligible possession. Because admitted groups change only 104 net points, the movement is category reassignment: points the baseline left in non-offense or unresolved categories become offense points.

| Population | Team-seasons | Raw PPP changed | PPP change above 0.05 | Raw PPP rank move above 5 | Largest PPP / rank move |
|---|---|---|---|---|---|
| At least 60 eligible possessions (about full-season teams) | 1,310 | 710 | **399** | **178** | 0.364 / 19 |
| All team-seasons (includes FCS teams with 4-20 possessions) | 2,040 | 765 | 454 | 356 | 1.273 / 113 |

By the Appendix A threshold (above 0.05 raw PPP or more than five rank positions) the repair is **material**. Adjusted/state deltas and rating-level rank moves are not computed here; they need the 6A rebuild. An earlier draft of this calculation used the wrong population; the table above is the corrected one.

## Limits and open items

- **Corroboration is weak for point recoveries** (5A caveat stands): the admitted set is almost entirely attribution-only. The 28 contradicted groups and the 1,749 unverified groups keep baseline errors where they exist; the baseline's known over- and under-credits remain there.
- **2026** weeks 0-4 (132 groups) remain baseline; no evidence exists.
- **Evidence table not built**: terms URI and rights basis for CFBD data need your decision.
- The verifier checks the admission against the decisions and an independent reconstruction; it does not re-run the CFBD corroboration. The 5A corroboration code is shared with the producer.
- The scratch ledgers (`admitted_events.parquet`, `admitted_ledger_v1.parquet`) are reproducible by `scripts/analysis/build_admitted_ledger_5c.py` but not retained; durable publication is 6A.
- The 5A baseline events were reused from the sizing run for speed; the verifier independently reproduced them.

## For your review

1. Accept the admission result and the material finding, and approve the Amendment 2 decision mapping.
2. Decide the rights basis/terms URI for CFBD evidence (needed before any evidence table or Gold publish).
3. Authorize 6A (historical rebuild and refit), which needs R2 write approval.
