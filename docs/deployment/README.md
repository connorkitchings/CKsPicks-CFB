# V2 Deployment Documentation

> **⚠️ SUPERSEDED (historical reference).** These V2-era docs describe a
> local-joblib/MLflow/email deployment that predates the live 2026 system.
> Production today is Vercel + Neon + Cloudflare R2 with the V4 bundle — see
> the [Production Runbook](../ops/production_runbook.md) and
> [Weekly Pipeline](../ops/weekly_pipeline.md).

Welcome to the V2 deployment documentation. This section contains everything needed to deploy, operate, and maintain the V2 champion model in production.

---

## Documents

### Getting Started
- **[Quick Start Guide](quick_start.md)** - 5-minute guide for weekly operations
- **[Production Guide](production_guide.md)** - Comprehensive deployment and operations manual
- **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment validation

### Configuration
- Champion Model: `conf/model/champion.yaml`
- Weekly Bets: `conf/weekly_bets/v2_champion.yaml`
- Experiments: `conf/experiment/v2_champion_validation.yaml`

### Scripts
- **Generate Predictions:** `scripts/pipeline/generate_weekly_bets.py`
- **Score Results:** `scripts/pipeline/score_weekly_bets.py`
- **Training:** `src/cks_picks_cfb/train.py`

---

## Quick Links

- [V2 Workflow Overview](../process/experimentation_workflow.md)
- [Decision Log](../decisions/decision_log.md)
- [Feature Registry](../project_org/feature_registry.md)
- [Main README](../../README.md)

---

## Champion Model Summary

**Model:** Linear Regression (Ridge)  
**Features:** matchup_v1 (16 features)  
**Optimizations:**
- Bias correction: +1.14 points
- Dual-threshold betting (0.0 / 8.0)
- Totals threshold: 1.5

**Expected Performance:**
- Spread ROI: +0.78% (default), +2.03% (high confidence)
- Totals ROI: +6.35%
- Hit Rate: 52-55%

---

## Support

For issues or questions:
- Check the [Production Guide](production_guide.md) troubleshooting section
- Review [Decision Log](../decisions/decision_log.md) for historical context
- Contact: connor.kitchings@gmail.com
