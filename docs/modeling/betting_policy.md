# Market Decision and Betting Policy

> **2026 posture:** display-only, fail-closed publication. This document does
> not authorize wagering, bankroll management, or a production change.

## Boundary

Football modeling finishes before market evaluation begins:

```text
measurements → opponent adjustment → team state → game prediction
→ uncertainty/probabilistic output → timestamped market decision
```

Spreads, totals, moneylines, bookmaker features, ROI, and historical-market
outcomes must not enter measurements, ratings, football predictions, candidate
selection, or promotion. Untimestamped legacy market references are permanently
ineligible for leans, grades, ROI, and model selection.

## 2026 production behavior

- V4 is the active production model and Vercel publication uses the explicit
  fail-closed release policy.
- Games with missing or stale timestamped prices may remain visible, but cannot
  produce market decisions or confidence claims.
- Any pricing/edge display must retain prediction run, market timestamp,
  source/provenance, and publication-state lineage.
- The rating successor stays shadow-only. Its market evaluation begins only
  after football-model quality succeeds under the [evaluation policy](evaluation.md).

Future unit sizing, exposure, and wagering policy require a separate product
and compliance decision. Historical V2 betting-policy material remains available
through the [documentation archive](../archive.md).
