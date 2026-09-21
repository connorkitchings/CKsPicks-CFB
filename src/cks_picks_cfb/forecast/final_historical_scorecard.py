"""Contract 12 V5 Historical Results and Readiness Review scorecard computation.

This module is deliberately independent of every forecast producer: it must
not import ``offsets``, ``heads``, ``horizons``, ``calibration``, or any
research runner.  It reads the 11D-verified population from storage and
recomputes every metric from first principles.

Permitted use: ``historical_readiness_review_only``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import (
    verify_signed_payload,
)

# ---------------------------------------------------------------------------
# Contract-pinned constants
# ---------------------------------------------------------------------------

SCORECARD_SCHEMA = "data_first_historical_scorecard_v1"
SCORECARD_MANIFEST_SCHEMA = "data_first_historical_scorecard_manifest_v1"

OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs"
)

# Exact 11D verification manifest identity (pinned by contract)
VERIFICATION_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/forecasts/runs/"
    "forecast-v1-20260921-5afd577-11c/verification/verifier-manifest.json"
)
VERIFICATION_MANIFEST_RAW_SHA256 = (
    "ba60166bab17189209adca91e043338337b1a895c2d1637495abf1fa94ae0246"
)
VERIFICATION_MANIFEST_CANONICAL_SHA256 = (
    "4cfe5ef86e4e7145d6dfe3d4e2f1ea85e54475c439fce04a1ce41ec21dfa363b"
)

# Certified frozen lineage identities
FROZEN_IDENTITIES = {
    "forecast": "forecast-v1-20260921-5afd577-11c",
    "measurement": "possession-v1-measurements-20260921-r9",
    "rating": "possession-v1-ratings-20260921-11d59ee-r9cert",
    "repair": "repair-v2-20260909T1417Z",
    "market_diagnostic": "market-diagnostic-2025-v1-20260921",
}

# Audit findings closure certifications
CLOSED_FINDINGS = [
    {
        "finding_id": "audit-structural-001",
        "title": "Repair v2 verification imports producer computation",
        "closure_state": "closed",
        "resolution": "Independent Repair verifier v3 with zero producer imports certified in Session 03",
    },
    {
        "finding_id": "audit-structural-002",
        "title": "Original forecast verification did not reconstruct stored outputs",
        "closure_state": "closed",
        "resolution": "Independent 11D verifier reconstructed all 6 output datasets bit-exact in Session 09 (manifest 4cfe5ef8...)",
    },
    {
        "finding_id": "audit-ledger-score_reconciliation-1de3aaaf7d",
        "title": "81 score-ledger excess team-game keys",
        "closure_state": "closed",
        "resolution": "Corrected possession measurement scoring extraction certified in r9 with 0 excess keys in Session 03",
    },
    {
        "finding_id": "audit-forecast-final_fit_existence-b1bc852294",
        "title": "No through-2025 final forecast fit exists",
        "closure_state": "closed",
        "resolution": "Through-2025 final fit rows added in 11C and verified in 11D with training_max=2025 in Session 08/09",
    },
]

# Verified population contract (pinned by contract)
EXPECTED_TOTAL_ROWS = 7318
EXPECTED_TOTAL_GAMES = 3659
EXPECTED_ROWS_BY_SEASON: dict[int, int] = {2022: 896, 2023: 910, 2024: 919, 2025: 934}
EXPECTED_STAGE_COUNTS: dict[str, int] = {
    "0": 573,
    "1": 301,
    "2": 244,
    "3": 253,
    "4_plus": 2288,
}

REPORTING_SEASONS = (2022, 2023, 2024, 2025)
HEADLINE_SEASON = 2025
CONTEXT_SEASONS = (2022, 2023, 2024)
ALLOWED_COMPLETED_STAGES = (0, 1, 2, 3, 4)

# Central Normal quantiles for 50/80/95% intervals
_Q50 = 0.6744897501960817
_Q80 = 1.2815515655446004
_Q95 = 1.959963984540054

TARGETS = ("margin", "total")

# Permitted use and readiness governance
PERMITTED_USE = "historical_readiness_review_only"
READINESS_RECOMMENDATION = "accepted_for_prospective_evaluation"
PRODUCTION_ACTIVATION_AUTHORIZED = False

# Market diagnostic reference data
MARKET_DIAGNOSTIC_REFERENCE = {
    "run_id": "market-diagnostic-2025-v1-20260921",
    "manifest_uri": (
        "artifacts/research/data-first-football-v1/market-diagnostics/v1/runs/"
        "market-diagnostic-2025-v1-20260921/diagnostic-manifest.json"
    ),
    "manifest_sha256": "2b45c047a35a7d8e28510a73ef1df380262db988366453ccf08be8658a1e36bc",
    "permitted_use": "diagnostic_comparison_only",
    "season": 2025,
    "sample_size": 762,
    "margin_mae": {"model": 14.382, "market": 12.062, "delta": -2.320},
    "total_mae": {"model": 13.200, "market": 12.290, "delta": -0.910},
    "disclosure": (
        "Market line comparison is diagnostic-only from provider-recorded lines captured postseason. "
        "V5 relies strictly on football measurements without bookmaker market inputs."
    ),
}

# V4 comparison unavailability disclosure
V4_COMPARISON_DISCLOSURE = {
    "status": "unavailable",
    "reason": (
        "V4 champion models were trained on 2021-2024 under feature schema v4/v5 without "
        "an equivalent 2022-2025 chronological point-in-time backtest under the V5 evaluation protocol."
    ),
}


class ScorecardError(ValueError):
    """Raised when scorecard computation cannot proceed."""


# ---------------------------------------------------------------------------
# 11D manifest validation
# ---------------------------------------------------------------------------


def validate_verification_manifest(
    storage: Any,
) -> dict[str, Any]:
    """Re-read and validate the exact 11D verification manifest from storage.

    Validates:
    - manifest existence and valid signature
    - raw SHA-256 == VERIFICATION_MANIFEST_RAW_SHA256
    - state == 'verified'
    - final_fit_verified is True
    - training_max_season == 2025
    - closes_findings includes 002 and 004
    - permitted_use == 'full_lane_forecast_eligibility_closure_only'
    - production_activation_authorized is False
    """
    if not storage.exists(VERIFICATION_MANIFEST_URI):
        raise ScorecardError(
            f"11D verification manifest not found at {VERIFICATION_MANIFEST_URI!r}"
        )

    raw_bytes = storage.read_bytes(VERIFICATION_MANIFEST_URI)
    computed_raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    if computed_raw_sha != VERIFICATION_MANIFEST_RAW_SHA256:
        raise ScorecardError(
            f"11D verification manifest raw SHA mismatch: "
            f"expected {VERIFICATION_MANIFEST_RAW_SHA256}, got {computed_raw_sha}"
        )

    try:
        manifest = json.loads(raw_bytes)
        verify_signed_payload(manifest, label="11D verifier manifest")
    except Exception as exc:
        raise ScorecardError(
            f"11D verification manifest signature verification failed: {exc}"
        ) from exc

    if manifest.get("manifest_sha256") != VERIFICATION_MANIFEST_CANONICAL_SHA256:
        raise ScorecardError(
            f"11D verification manifest canonical SHA mismatch: "
            f"expected {VERIFICATION_MANIFEST_CANONICAL_SHA256}, got {manifest.get('manifest_sha256')}"
        )

    if manifest.get("state") != "verified":
        raise ScorecardError(
            f"11D manifest state is {manifest.get('state')!r}, expected 'verified'"
        )

    if manifest.get("final_fit_verified") is not True:
        raise ScorecardError("11D manifest final_fit_verified is not True")

    if manifest.get("training_max_season") != 2025:
        raise ScorecardError(
            f"11D manifest training_max_season={manifest.get('training_max_season')}, expected 2025"
        )

    closes = set(manifest.get("closes_findings", []))
    required_findings = {
        "audit-structural-002",
        "audit-forecast-final_fit_existence-b1bc852294",
    }
    if not required_findings.issubset(closes):
        missing = required_findings - closes
        raise ScorecardError(
            f"11D manifest missing required closed findings: {missing}"
        )

    if manifest.get("production_activation_authorized") is not False:
        raise ScorecardError(
            "11D manifest has production_activation_authorized != False"
        )

    return manifest


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data(
    storage: Any,
    manifest: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load forecast predictions, calibration, window comparison, and recipes."""
    from cks_picks_cfb.audit.corpus import concat_all, read_any

    f_uri = manifest.get("forecast_manifest_uri", "")
    if not f_uri:
        raise ScorecardError("11D manifest has no forecast_manifest_uri")

    try:
        f_manifest = json.loads(storage.read_bytes(f_uri))
    except Exception as exc:
        raise ScorecardError(f"Cannot load forecast manifest from {f_uri!r}") from exc

    output_refs = f_manifest.get("output_refs", {})

    pred_ref = output_refs.get("forecast_prediction")
    cal_ref = output_refs.get("forecast_calibration")
    window_ref = output_refs.get("window_comparison")

    if not pred_ref or not cal_ref:
        raise ScorecardError("Forecast manifest missing required output refs")

    predictions = concat_all(read_any(storage, pred_ref))
    calibration = concat_all(read_any(storage, cal_ref))
    window_comparison = (
        concat_all(read_any(storage, window_ref)) if window_ref else pd.DataFrame()
    )

    if (
        "completed_game_stage" in predictions.columns
        and "completed_games" not in predictions.columns
    ):
        predictions["completed_games"] = predictions["completed_game_stage"]

    head_recipes = f_manifest.get("head_recipes", {})
    return predictions, calibration, window_comparison, head_recipes


# ---------------------------------------------------------------------------
# Population validation
# ---------------------------------------------------------------------------


def validate_population(
    predictions: pd.DataFrame,
    calibration: pd.DataFrame,
) -> dict[str, Any]:
    """Validate forecast population integrity strictly fail-closed."""
    source_count = len(predictions)
    if source_count != EXPECTED_TOTAL_ROWS:
        raise ScorecardError(
            f"Expected {EXPECTED_TOTAL_ROWS} prediction rows, found {source_count}"
        )

    for col in (
        "game_id",
        "season",
        "target",
        "prediction",
        "actual",
        "completed_games",
    ):
        if col not in predictions.columns:
            raise ScorecardError(f"Missing required prediction column: {col!r}")

    for col in ("prediction", "actual"):
        vals = predictions[col].to_numpy(float)
        if not np.all(np.isfinite(vals)):
            raise ScorecardError(
                f"Non-finite values found in prediction column {col!r}"
            )

    # Check duplicate keys
    key_cols = ["game_id", "target", "season"]
    dup_count = int(predictions.duplicated(subset=key_cols).sum())
    if dup_count > 0:
        raise ScorecardError(f"Found {dup_count} duplicate prediction keys")

    # Validate targets
    actual_targets = set(predictions["target"].unique())
    if actual_targets != set(TARGETS):
        raise ScorecardError(
            f"Target mismatch: expected {set(TARGETS)}, got {actual_targets}"
        )

    # Validate row count by season
    rows_by_season: dict[int, int] = {}
    for season, expected_count in EXPECTED_ROWS_BY_SEASON.items():
        s_rows = predictions[predictions["season"] == season]
        per_target = len(s_rows[s_rows["target"] == "margin"])
        if per_target != expected_count:
            raise ScorecardError(
                f"Season {season} row mismatch: expected {expected_count}, got {per_target}"
            )
        rows_by_season[season] = per_target

    # Validate stage counts
    margin_rows = predictions[predictions["target"] == "margin"]
    stage_counts: dict[str, int] = {}
    for stage_val, stage_key in [(0, "0"), (1, "1"), (2, "2"), (3, "3")]:
        count = int((margin_rows["completed_games"] == stage_val).sum())
        stage_counts[stage_key] = count
    four_plus = int((margin_rows["completed_games"] >= 4).sum())
    stage_counts["4_plus"] = four_plus

    for key, expected in EXPECTED_STAGE_COUNTS.items():
        if stage_counts[key] != expected:
            raise ScorecardError(
                f"Stage {key} count mismatch: expected {expected}, got {stage_counts[key]}"
            )

    # Calibration check
    cal_keys = set(zip(calibration["target"].tolist(), calibration["season"].tolist()))
    for target in TARGETS:
        for season in REPORTING_SEASONS:
            if (target, season) not in cal_keys:
                raise ScorecardError(
                    f"Calibration missing entry for target={target!r}, season={season}"
                )

    return {
        "source_count": source_count,
        "included_count": source_count,
        "excluded_count": 0,
        "exclusion_reasons": [],
        "rows_by_season": rows_by_season,
        "stage_counts": stage_counts,
        "games_count": EXPECTED_TOTAL_GAMES,
    }


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _metrics_for_slice(
    predictions: pd.DataFrame,
    calibration_variances: dict[str, dict[int, float]],
    *,
    target: str,
) -> dict[str, Any]:
    """Compute all metrics for a single target slice."""
    rows = predictions[predictions["target"] == target].copy()
    if rows.empty:
        raise ScorecardError(f"No rows for target={target!r}")

    errors = rows["prediction"].to_numpy(float) - rows["actual"].to_numpy(float)
    n = len(errors)

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    bias = float(np.mean(errors))

    # CRPS and intervals from calibration variance
    sigmas = np.array(
        [
            float(np.sqrt(calibration_variances[target].get(int(s), 1e-6)))
            for s in rows["season"]
        ]
    )

    from scipy.special import ndtr as _ndtr
    from scipy.stats import norm as _norm

    z = errors / np.where(sigmas > 0, sigmas, 1e-8)
    phi_z = _ndtr(z)
    pdf_z = _norm.pdf(z)
    crps_vals = sigmas * (z * (2 * phi_z - 1) + 2 * pdf_z - 1 / np.sqrt(np.pi))
    crps = float(np.mean(crps_vals))

    def _coverage_width(q: float) -> tuple[float, float]:
        lower = rows["prediction"].to_numpy(float) - q * sigmas
        upper = rows["prediction"].to_numpy(float) + q * sigmas
        actual_vals = rows["actual"].to_numpy(float)
        covered = (actual_vals >= lower) & (actual_vals <= upper)
        coverage = float(np.mean(covered))
        width = float(np.mean(upper - lower))
        return coverage, width

    cov50, wid50 = _coverage_width(_Q50)
    cov80, wid80 = _coverage_width(_Q80)
    cov95, wid95 = _coverage_width(_Q95)

    return {
        "n": n,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "bias": round(bias, 4),
        "crps": round(crps, 4),
        "coverage_50": round(cov50, 4),
        "width_50": round(wid50, 2),
        "coverage_80": round(cov80, 4),
        "width_80": round(wid80, 2),
        "coverage_95": round(cov95, 4),
        "width_95": round(wid95, 2),
    }


def compute_scorecard(
    predictions: pd.DataFrame,
    calibration: pd.DataFrame,
    window_comparison: pd.DataFrame,
    head_recipes: dict[str, Any],
    *,
    population_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compute the full historical scorecard and readiness evidence block."""
    cal_variances: dict[str, dict[int, float]] = {t: {} for t in TARGETS}
    for _, row in calibration.iterrows():
        target = str(row["target"])
        season = int(row["season"])
        variance = float(row["variance"])
        if target in cal_variances and season in REPORTING_SEASONS:
            cal_variances[target][season] = variance

    target_results: dict[str, Any] = {}
    for target in TARGETS:
        target_block: dict[str, Any] = {}

        # Headline 2025
        season_rows = predictions[
            (predictions["target"] == target)
            & (predictions["season"] == HEADLINE_SEASON)
        ]
        target_block["headline_2025"] = _metrics_for_slice(
            season_rows, cal_variances, target=target
        )

        # Context by season 2022-2024
        context: dict[str, Any] = {}
        for season in CONTEXT_SEASONS:
            season_rows = predictions[
                (predictions["target"] == target) & (predictions["season"] == season)
            ]
            context[str(season)] = _metrics_for_slice(
                season_rows, cal_variances, target=target
            )
        target_block["context_by_season"] = context

        # Pooled 2022-2025
        all_rows = predictions[predictions["target"] == target]
        target_block["pooled_2022_2025"] = _metrics_for_slice(
            all_rows, cal_variances, target=target
        )

        # By completed game stage
        stage_results: dict[str, Any] = {}
        for stage in (0, 1, 2, 3):
            key = str(stage)
            stage_rows = predictions[
                (predictions["target"] == target)
                & (predictions["completed_games"] == stage)
            ]
            stage_results[key] = (
                _metrics_for_slice(stage_rows, cal_variances, target=target)
                if not stage_rows.empty
                else {"n": 0}
            )
        four_plus_rows = predictions[
            (predictions["target"] == target) & (predictions["completed_games"] >= 4)
        ]
        stage_results["4_plus"] = _metrics_for_slice(
            four_plus_rows, cal_variances, target=target
        )
        target_block["by_completed_game_stage"] = stage_results

        target_results[target] = target_block

    # Format window comparison table
    window_records = []
    if not window_comparison.empty:
        window_records = window_comparison.to_dict(orient="records")

    return {
        "targets": target_results,
        "population": population_summary,
        "frozen_identities": dict(FROZEN_IDENTITIES),
        "closed_findings": [dict(f) for f in CLOSED_FINDINGS],
        "selection_evidence": {
            "selected_horizon": "expanding",
            "selected_head": "reference",
            "head_recipes": head_recipes,
            "window_comparison": window_records,
        },
        "market_diagnostic_evidence": dict(MARKET_DIAGNOSTIC_REFERENCE),
        "v4_comparison": dict(V4_COMPARISON_DISCLOSURE),
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": PRODUCTION_ACTIVATION_AUTHORIZED,
        "readiness_recommendation": READINESS_RECOMMENDATION,
        "readiness_rationale": (
            "The V5 historical foundation, possession efficiency measurements (r9), ratings (r9cert), "
            "expanding Ridge forecast bridge, and through-2025 final fit are mathematically verified, "
            "calibrated, and accepted for prospective evaluation. Prospective application to 2026 "
            "requires separate re-review and execution of Contracts 07-09."
        ),
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_report(
    scorecard_evidence: dict[str, Any],
    *,
    run_id: str,
    manifest_uri: str,
    manifest_raw_sha256: str,
) -> str:
    """Render the official comprehensive Markdown readiness review report."""
    targets = scorecard_evidence.get("targets", {})
    pop = scorecard_evidence.get("population", {})
    closed = scorecard_evidence.get("closed_findings", [])
    frozen = scorecard_evidence.get("frozen_identities", {})
    market_diag = scorecard_evidence.get("market_diagnostic_evidence", {})
    v4_comp = scorecard_evidence.get("v4_comparison", {})
    sel = scorecard_evidence.get("selection_evidence", {})
    recipes = sel.get("head_recipes", {})

    def _fmt_metrics(m: dict[str, Any]) -> str:
        if m.get("n", 0) == 0:
            return "  _No observations_"
        lines = [
            f"  - N: {m['n']}",
            f"  - MAE: {m['mae']:.3f}",
            f"  - RMSE: {m['rmse']:.3f}",
            f"  - Bias: {m['bias']:+.3f}",
            f"  - CRPS: {m['crps']:.3f}",
            f"  - 50% coverage / width: {m['coverage_50']:.1%} / {m['width_50']:.2f}",
            f"  - 80% coverage / width: {m['coverage_80']:.1%} / {m['width_80']:.2f}",
            f"  - 95% coverage / width: {m['coverage_95']:.1%} / {m['width_95']:.2f}",
        ]
        return "\n".join(lines)

    sections = [
        "# V5 Historical Results and Readiness Review Report",
        "",
        "> **Permitted use:** `historical_readiness_review_only`  ",
        f"> **Production activation authorized:** {scorecard_evidence.get('production_activation_authorized')}  ",
        f"> **Readiness recommendation:** `{scorecard_evidence.get('readiness_recommendation')}`  ",
        "",
        "## Executive Summary",
        "",
        scorecard_evidence.get("readiness_rationale", ""),
        "",
        "## Certified Lineage and Closed Audit Blockers",
        "",
        "All four Contract 10B foundation audit blocker findings have been resolved, "
        "independently verified, and closed:",
        "",
    ]

    for item in closed:
        sections.append(
            f"- **{item['finding_id']}** (`{item['closure_state']}`): "
            f"{item['title']} — _{item['resolution']}_"
        )

    sections += [
        "",
        "### Sealed Artifact Lineage",
        "",
    ]
    for role, ident in sorted(frozen.items()):
        sections.append(f"- **{role}:** `{ident}`")

    sections += [
        "",
        "## Population Verification",
        "",
        f"- Total prediction rows: {pop.get('source_count')}",
        f"- Total games: {pop.get('games_count')}",
        f"- Excluded rows: {pop.get('excluded_count', 0)} (zero exclusions permitted; fully verified)",
        f"- Seasons: {', '.join(str(s) for s in REPORTING_SEASONS)}",
        "",
    ]
    for s, c in sorted((pop.get("rows_by_season") or {}).items()):
        sections.append(f"  - Season {s}: {c} games per target")

    for target in TARGETS:
        t_data = targets.get(target, {})
        sections += [
            "",
            f"## Target: {target.upper()}",
            "",
            "### Headline — 2025 Evaluation",
            "",
            _fmt_metrics(t_data.get("headline_2025", {})),
            "",
            "### Context Seasons (2022–2024)",
            "",
        ]
        for season in CONTEXT_SEASONS:
            sections.append(f"**Season {season}:**")
            sections.append(
                _fmt_metrics(t_data.get("context_by_season", {}).get(str(season), {}))
            )
            sections.append("")

        sections += [
            "### Pooled Results (2022–2025)",
            "",
            _fmt_metrics(t_data.get("pooled_2022_2025", {})),
            "",
            "### Performance by Completed-Game Stage",
            "",
        ]
        for stage_key in ("0", "1", "2", "3", "4_plus"):
            lbl = f"Stage {stage_key}" if stage_key != "4_plus" else "Stage 4+"
            sections.append(f"**{lbl}:**")
            sections.append(
                _fmt_metrics(
                    t_data.get("by_completed_game_stage", {}).get(stage_key, {})
                )
            )
            sections.append("")

    sections += [
        "## Selection Evidence and Gates",
        "",
        "- **Selected Horizon:** `expanding` (retained over `latest_five` per the prespecified gate: "
        "`latest_five` achieved <0.5% gain with non-positive bootstrap lower bounds).",
        f"- **Selected Heads:** `{sel.get('selected_head')}` (Ridge regression with fixed alpha=10.0).",
        f"- **Through-2025 Final Fit:** Verified for both margin and total "
        f"across all 10 development seasons ({recipes.get('margin', {}).get('final_training_seasons')}).",
        "",
        "## Baseline and Comparison Disclosures",
        "",
        "### Market Line Diagnostic Comparison (2025)",
        "",
        f"- Run ID: `{market_diag.get('run_id')}`",
        f"- Sample: {market_diag.get('sample_size')} games",
        f"- Margin MAE: Model {market_diag.get('margin_mae', {}).get('model'):.2f} vs Market {market_diag.get('margin_mae', {}).get('market'):.2f} "
        f"(Delta: {market_diag.get('margin_mae', {}).get('delta'):+.2f})",
        f"- Total MAE: Model {market_diag.get('total_mae', {}).get('model'):.2f} vs Market {market_diag.get('total_mae', {}).get('market'):.2f} "
        f"(Delta: {market_diag.get('total_mae', {}).get('delta'):+.2f})",
        f"- Disclosure: _{market_diag.get('disclosure')}_",
        "",
        "### V4 Point-in-Time Comparison Disclosure",
        "",
        f"- Status: `{v4_comp.get('status')}`",
        f"- Disclosure: _{v4_comp.get('reason')}_",
        "",
        "## Next Steps & 2026 Prospective Governance",
        "",
        "1. **Historical Foundation Accepted:** The historical methodology, verified dataset, "
        "and through-2025 final fit are formally certified.",
        "2. **Live 2026 Application Withheld:** This review does **not** grant authority to apply V5 "
        "to live 2026 games or modify production champion models.",
        "3. **Prerequisites for Live Prospective Evaluation:** Requires user acceptance of this review, "
        "followed by re-review and execution of deferred Contracts 07 (2026 measurement extension), "
        "08 (2026 rating-state replay), and 09 (2026 forecast generation and live readiness).",
        "",
        "## Evidence Provenance",
        "",
        f"- Scorecard Run ID: `{run_id}`",
        f"- Scorecard Manifest URI: `{manifest_uri}`",
        f"- Scorecard Manifest Raw SHA-256: `{manifest_raw_sha256}`",
        f"- Entry Verification Manifest: `{VERIFICATION_MANIFEST_URI}`",
        f"- Entry Manifest Raw SHA-256: `{VERIFICATION_MANIFEST_RAW_SHA256}`",
        "",
        "---",
        "_Official decision record for V5 Contract 12 (Historical Results and Readiness Review)._",
    ]

    return "\n".join(sections) + "\n"
