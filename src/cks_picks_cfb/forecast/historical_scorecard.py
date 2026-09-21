"""Contract 12A conditional historical scorecard computation.

This module is deliberately independent of every forecast producer: it must
not import ``offsets``, ``heads``, ``horizons``, ``calibration``, or any
research runner.  It reads the 11A-verified population from storage and
recomputes every metric from first principles.

Permitted use: ``conditional_historical_results_only``.
"""

from __future__ import annotations

import hashlib
import io
import json
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import (
    verify_signed_payload,
)
from cks_picks_cfb.forecast.conditional_verification import (
    FROZEN_IDENTITIES,
    OPEN_LIMITATIONS,
    PERMITTED_USE,
)

# ---------------------------------------------------------------------------
# Contract-pinned constants
# ---------------------------------------------------------------------------

SCORECARD_SCHEMA = "data_first_conditional_scorecard_v1"
SCORECARD_MANIFEST_SCHEMA = "data_first_conditional_scorecard_manifest_v1"

OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/"
    "historical-scorecards/conditional-v1/runs"
)

# Exact 11A verification manifest identity (pinned by contract)
VERIFICATION_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/forecast-verification/"
    "conditional-v1/runs/conditional-v1-20260919-9265314-11a/"
    "verification-manifest.json"
)
VERIFICATION_MANIFEST_RAW_SHA256 = (
    "5a7e7d4861e954feb570d52d0e45f9a50d88918fc91dd825dc0a9d1a9ba1326d"
)
VERIFICATION_MANIFEST_CANONICAL_SHA256 = (
    "7ce47863e1e34874357f3f503ef1d8f1f232e48c9b199c5aff99dfb5606b93ad"
)
VERIFICATION_RECORD_RAW_SHA256 = (
    "7ee050b45ea8df9e00f44bdde3159f4d6a2ffe16878a93835e69ad068302cda2"
)

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
ALLOWED_COMPLETED_STAGES = (0, 1, 2, 3, 4)  # 4 = 4_plus

# Central Normal quantiles for 50/80/95% intervals (pinned by contract)
_Q50 = 0.6744897501960817
_Q80 = 1.2815515655446004
_Q95 = 1.959963984540054

TARGETS = ("margin", "total")

# Forecast prediction columns needed
PREDICTION_COLUMNS = frozenset(
    {
        "game_id",
        "season",
        "target",
        "prediction",
        "actual",
        "completed_games",
    }
)

# Calibration columns needed
CALIBRATION_COLUMNS = frozenset(
    {"target", "season", "residual_count", "variance", "fallback_reason"}
)


class ScorecardError(ValueError):
    """Raised when scorecard computation cannot proceed."""


# ---------------------------------------------------------------------------
# 11A manifest validation
# ---------------------------------------------------------------------------


def validate_verification_manifest(
    storage: Any,
) -> dict[str, Any]:
    """Re-read and validate the exact 11A verification manifest from R2.

    Validates:
    - manifest existence and valid signature
    - raw SHA-256 == VERIFICATION_MANIFEST_RAW_SHA256
    - canonical SHA-256 == VERIFICATION_MANIFEST_CANONICAL_SHA256
    - state == 'verified'
    - permitted_use == 'conditional_historical_results_only'
    - production_activation_authorized is False
    - forecast_eligibility_restored is False
    - record existence and raw SHA-256 == VERIFICATION_RECORD_RAW_SHA256
    - all 4 frozen artifact identities match

    Returns the verified manifest dict.
    Raises ScorecardError if any condition is not met.
    """
    try:
        raw = storage.read_bytes(VERIFICATION_MANIFEST_URI)
    except (OSError, FileNotFoundError) as exc:
        raise ScorecardError(
            f"11A verification manifest not found at {VERIFICATION_MANIFEST_URI!r}"
        ) from exc

    # Check raw SHA-256
    actual_raw_sha = hashlib.sha256(raw).hexdigest()
    if actual_raw_sha != VERIFICATION_MANIFEST_RAW_SHA256:
        raise ScorecardError(
            f"11A manifest raw SHA mismatch: "
            f"expected {VERIFICATION_MANIFEST_RAW_SHA256}, got {actual_raw_sha}"
        )

    try:
        manifest = json.loads(raw)
        verify_signed_payload(manifest, label="11A verification manifest")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ScorecardError("11A manifest signature invalid") from exc

    actual_canonical_sha = manifest.get("manifest_sha256")
    if actual_canonical_sha != VERIFICATION_MANIFEST_CANONICAL_SHA256:
        raise ScorecardError(
            f"11A manifest canonical SHA mismatch: "
            f"expected {VERIFICATION_MANIFEST_CANONICAL_SHA256}, "
            f"got {actual_canonical_sha}"
        )

    # Validate boundary fields
    if manifest.get("permitted_use") != PERMITTED_USE:
        raise ScorecardError(
            f"11A manifest permitted_use is not {PERMITTED_USE!r}: "
            f"{manifest.get('permitted_use')!r}"
        )
    if manifest.get("production_activation_authorized") is not False:
        raise ScorecardError(
            "11A manifest production_activation_authorized is not False"
        )
    if manifest.get("forecast_eligibility_restored") is not False:
        raise ScorecardError("11A manifest forecast_eligibility_restored is not False")
    if manifest.get("state") != "verified":
        raise ScorecardError(
            f"11A manifest state is not 'verified': {manifest.get('state')!r}"
        )

    # Validate the record itself
    record_uri = manifest.get("record_uri", "")
    try:
        record_raw = storage.read_bytes(record_uri)
    except (OSError, FileNotFoundError) as exc:
        raise ScorecardError(f"11A record not found at {record_uri!r}") from exc

    actual_record_sha = hashlib.sha256(record_raw).hexdigest()
    if actual_record_sha != VERIFICATION_RECORD_RAW_SHA256:
        raise ScorecardError(
            f"11A record raw SHA mismatch: "
            f"expected {VERIFICATION_RECORD_RAW_SHA256}, got {actual_record_sha}"
        )

    # Confirm frozen identities
    frozen = manifest.get("frozen_artifacts", {})
    for role, expected_id in FROZEN_IDENTITIES.items():
        actual_id = frozen.get(role, {}).get("identity")
        if actual_id != expected_id:
            raise ScorecardError(
                f"Frozen {role} identity mismatch: "
                f"expected {expected_id!r}, got {actual_id!r}"
            )

    return manifest


# ---------------------------------------------------------------------------
# Forecast population loading
# ---------------------------------------------------------------------------


def _load_predictions(storage: Any, manifest: dict[str, Any]) -> pd.DataFrame:
    """Load the 11A-verified forecast_prediction dataset."""
    from cks_picks_cfb.audit.corpus import concat_all, read_any

    record_uri = manifest.get("record_uri", "")
    if not record_uri:
        raise ScorecardError("11A manifest has no record_uri")
    try:
        record = json.loads(storage.read_bytes(record_uri))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScorecardError("Cannot read 11A verification record") from exc

    verification = record.get("verification", {})
    datasets = verification.get("stored_outputs", {})
    if "forecast_prediction" in datasets:
        pred_info = datasets["forecast_prediction"]
        uri = pred_info.get("ref", {}).get("uri", "")
        if not uri:
            raise ScorecardError("11A forecast_prediction ref has no URI")
        try:
            frame = pd.read_parquet(io.BytesIO(storage.read_bytes(uri)))
        except Exception as exc:
            raise ScorecardError(
                f"Cannot load forecast_prediction from {uri!r}"
            ) from exc
    else:
        # Load from verified forecast manifest in frozen_artifacts
        f_info = record.get("frozen_artifacts", {}).get("forecast", {})
        f_uri = f_info.get("manifest_uri", "")
        if not f_uri:
            raise ScorecardError("11A record has no forecast manifest reference")
        try:
            f_manifest = json.loads(storage.read_bytes(f_uri))
            pred_ref = f_manifest.get("output_refs", {}).get("forecast_prediction")
            if not pred_ref:
                raise ScorecardError("Forecast manifest has no forecast_prediction ref")
            frame = concat_all(read_any(storage, pred_ref))
        except ScorecardError:
            raise
        except Exception as exc:
            raise ScorecardError(
                f"Cannot load forecast_prediction from forecast manifest {f_uri!r}"
            ) from exc

    if (
        "completed_game_stage" in frame.columns
        and "completed_games" not in frame.columns
    ):
        frame["completed_games"] = frame["completed_game_stage"]

    return frame


def _load_calibration(storage: Any, manifest: dict[str, Any]) -> pd.DataFrame:
    """Load the 11A-verified forecast_calibration dataset."""
    from cks_picks_cfb.audit.corpus import concat_all, read_any

    record_uri = manifest.get("record_uri", "")
    if not record_uri:
        raise ScorecardError("11A manifest has no record_uri")
    try:
        record = json.loads(storage.read_bytes(record_uri))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScorecardError("Cannot read 11A verification record") from exc

    verification = record.get("verification", {})
    datasets = verification.get("stored_outputs", {})
    if "forecast_calibration" in datasets:
        cal_info = datasets["forecast_calibration"]
        uri = cal_info.get("ref", {}).get("uri", "")
        if not uri:
            raise ScorecardError("11A forecast_calibration ref has no URI")
        try:
            frame = pd.read_parquet(io.BytesIO(storage.read_bytes(uri)))
        except Exception as exc:
            raise ScorecardError(
                f"Cannot load forecast_calibration from {uri!r}"
            ) from exc
    else:
        # Load from verified forecast manifest in frozen_artifacts
        f_info = record.get("frozen_artifacts", {}).get("forecast", {})
        f_uri = f_info.get("manifest_uri", "")
        if not f_uri:
            raise ScorecardError("11A record has no forecast manifest reference")
        try:
            f_manifest = json.loads(storage.read_bytes(f_uri))
            cal_ref = f_manifest.get("output_refs", {}).get("forecast_calibration")
            if not cal_ref:
                raise ScorecardError(
                    "Forecast manifest has no forecast_calibration ref"
                )
            frame = concat_all(read_any(storage, cal_ref))
        except ScorecardError:
            raise
        except Exception as exc:
            raise ScorecardError(
                f"Cannot load forecast_calibration from forecast manifest {f_uri!r}"
            ) from exc

    return frame


# ---------------------------------------------------------------------------
# Population validation
# ---------------------------------------------------------------------------


def validate_population(
    predictions: pd.DataFrame,
    calibration: pd.DataFrame,
) -> dict[str, Any]:
    """Validate the exact contract-specified population.

    Returns a summary dict: source_count, included_count, excluded_count,
    exclusion_reasons, fallback_counts, residual_counts, rows_by_season,
    stage_counts_by_target.

    Raises ScorecardError if any blocking condition is encountered.
    """
    # Check required columns
    missing_pred = sorted(PREDICTION_COLUMNS - set(predictions.columns))
    if missing_pred:
        raise ScorecardError(f"forecast_prediction missing columns: {missing_pred}")
    missing_cal = sorted(CALIBRATION_COLUMNS - set(calibration.columns))
    if missing_cal:
        raise ScorecardError(f"forecast_calibration missing columns: {missing_cal}")

    source_count = len(predictions)
    # Reject forbidden seasons
    forbidden = set(predictions.loc[predictions["season"].isin([2020, 2026])].index)
    if forbidden:
        raise ScorecardError(
            f"Population contains forbidden seasons (2020/2026): {len(forbidden)} rows"
        )

    # Only reporting seasons
    out_of_scope = predictions[~predictions["season"].isin(REPORTING_SEASONS)]
    if not out_of_scope.empty:
        raise ScorecardError(
            f"Population has unexpected seasons: "
            f"{sorted(out_of_scope['season'].unique().tolist())}"
        )

    # Non-finite prediction or actual
    non_finite_mask = ~(
        np.isfinite(predictions["prediction"].to_numpy(float))
        & np.isfinite(predictions["actual"].to_numpy(float))
    )
    if non_finite_mask.any():
        raise ScorecardError(
            f"Population has {non_finite_mask.sum()} non-finite prediction/actual rows"
        )

    # Duplicate game_id + target
    dup_mask = predictions.duplicated(subset=["game_id", "target"], keep=False)
    if dup_mask.any():
        raise ScorecardError(
            f"Population has {dup_mask.sum()} duplicate game_id+target rows"
        )

    # Both targets must be present for every game
    by_game_target = predictions.groupby("game_id")["target"].apply(set)
    incomplete = by_game_target[by_game_target != set(TARGETS)]
    if not incomplete.empty:
        raise ScorecardError(
            f"Population has {len(incomplete)} games with incomplete targets"
        )

    included_count = len(predictions)

    # Row counts
    if included_count != EXPECTED_TOTAL_ROWS:
        raise ScorecardError(
            f"Population total row count mismatch: "
            f"expected {EXPECTED_TOTAL_ROWS}, got {included_count}"
        )
    game_count = predictions["game_id"].nunique()
    if game_count != EXPECTED_TOTAL_GAMES:
        raise ScorecardError(
            f"Population game count mismatch: "
            f"expected {EXPECTED_TOTAL_GAMES}, got {game_count}"
        )

    # Per-season row counts (per target; each season should have 2 rows/game)
    rows_by_season: dict[int, int] = {}
    for season in REPORTING_SEASONS:
        season_rows = int((predictions["season"] == season).sum())
        # Each season has 2 targets * n_games rows
        per_target_rows = season_rows // len(TARGETS)
        expected = EXPECTED_ROWS_BY_SEASON[season]
        if per_target_rows != expected:
            raise ScorecardError(
                f"Season {season} per-target row count mismatch: "
                f"expected {expected}, got {per_target_rows}"
            )
        rows_by_season[season] = per_target_rows

    # Stage counts (across both targets, per stage; validate against margin target)
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

    # Calibration: must have entries for all targets × seasons
    cal_keys = set(
        zip(
            calibration["target"].tolist(),
            calibration["season"].tolist(),
        )
    )
    for target in TARGETS:
        for season in REPORTING_SEASONS:
            if (target, season) not in cal_keys:
                raise ScorecardError(
                    f"Calibration missing entry for target={target!r}, season={season}"
                )

    fallback_counts = {
        target: int(
            (
                calibration.loc[calibration["target"] == target, "fallback_reason"]
                != ""
            ).sum()
        )
        for target in TARGETS
    }
    residual_counts = {
        target: int(
            calibration.loc[calibration["target"] == target, "residual_count"].sum()
        )
        for target in TARGETS
    }

    return {
        "source_count": source_count,
        "included_count": included_count,
        "excluded_count": 0,
        "exclusion_reasons": [],
        "fallback_counts": fallback_counts,
        "residual_counts": residual_counts,
        "rows_by_season": rows_by_season,
        "stage_counts": stage_counts,
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
    """Compute all metrics for a single target slice.

    calibration_variances: {target: {season: variance}}
    """
    rows = predictions[predictions["target"] == target].copy()
    if rows.empty:
        raise ScorecardError(f"No rows for target={target!r}")

    errors = rows["prediction"].to_numpy(float) - rows["actual"].to_numpy(float)
    n = len(errors)

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    bias = float(np.mean(errors))

    # CRPS and intervals recomputed from calibration variance (per-season)
    sigmas = np.array(
        [
            float(np.sqrt(calibration_variances[target].get(int(s), 1e-6)))
            for s in rows["season"]
        ]
    )

    # Gaussian CRPS: E[|X-Y|] - 0.5*E[|X-X'|] for X ~ N(mu, sigma^2)
    # = sigma * (z * (2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi))
    # where z = (actual - pred) / sigma
    from scipy.special import ndtr as _ndtr
    from scipy.stats import norm as _norm

    z = errors / np.where(sigmas > 0, sigmas, 1e-8)
    phi_z = _ndtr(z)
    pdf_z = _norm.pdf(z)
    crps_vals = sigmas * (z * (2 * phi_z - 1) + 2 * pdf_z - 1 / np.sqrt(np.pi))
    crps = float(np.mean(crps_vals))

    # Coverage and width
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
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "crps": crps,
        "coverage_50": cov50,
        "width_50": wid50,
        "coverage_80": cov80,
        "width_80": wid80,
        "coverage_95": cov95,
        "width_95": wid95,
    }


def _stage_key(completed_games: int) -> str:
    if completed_games >= 4:
        return "4_plus"
    return str(completed_games)


def compute_scorecard(
    predictions: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    population_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compute the full conditional scorecard evidence block.

    Returns a structured dict with headline_2025, context_by_season,
    pooled_2022_2025, and by_completed_game_stage for each target.
    """
    # Build calibration variance lookup: {target: {season: variance}}
    cal_variances: dict[str, dict[int, float]] = {t: {} for t in TARGETS}
    for _, row in calibration.iterrows():
        target = str(row["target"])
        season = int(row["season"])
        variance = float(row["variance"])
        if target in cal_variances and season in REPORTING_SEASONS:
            cal_variances[target][season] = variance

    results: dict[str, Any] = {}
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
            if stage_rows.empty:
                stage_results[key] = {"n": 0}
            else:
                stage_results[key] = _metrics_for_slice(
                    stage_rows, cal_variances, target=target
                )
        four_plus_rows = predictions[
            (predictions["target"] == target) & (predictions["completed_games"] >= 4)
        ]
        stage_results["4_plus"] = _metrics_for_slice(
            four_plus_rows, cal_variances, target=target
        )
        target_block["by_completed_game_stage"] = stage_results

        results[target] = target_block

    return {
        "targets": results,
        "population": population_summary,
        "frozen_identities": {k: v for k, v in FROZEN_IDENTITIES.items()},
        "open_limitations": [dict(lim) for lim in OPEN_LIMITATIONS],
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
        "readiness_recommendation": None,
        "v4_comparison": None,
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
    """Render a readable Markdown report from verified scorecard evidence.

    The report is conditional_historical_results_only and must not make
    a readiness recommendation or compare V4.
    """
    targets = scorecard_evidence.get("targets", {})
    pop = scorecard_evidence.get("population", {})
    limitations = scorecard_evidence.get("open_limitations", [])
    frozen = scorecard_evidence.get("frozen_identities", {})

    def _fmt_metrics(m: dict[str, Any]) -> str:
        if m.get("n", 0) == 0:
            return "  _No observations_"
        lines = [
            f"  - N: {m['n']}",
            f"  - MAE: {m['mae']:.3f}",
            f"  - RMSE: {m['rmse']:.3f}",
            f"  - Bias: {m['bias']:+.3f}",
            f"  - CRPS: {m['crps']:.3f}",
            f"  - 50% coverage / width: {m['coverage_50']:.3%} / {m['width_50']:.2f}",
            f"  - 80% coverage / width: {m['coverage_80']:.3%} / {m['width_80']:.2f}",
            f"  - 95% coverage / width: {m['coverage_95']:.3%} / {m['width_95']:.2f}",
        ]
        return "\n".join(lines)

    sections = [
        "# V5 Conditional Historical Scorecard",
        "",
        "> **Permitted use:** `conditional_historical_results_only`  ",
        "> **Production activation authorized:** false  ",
        "> **Readiness recommendation:** none — this scorecard answers the 2025",
        "> historical question only; it cannot clear any blocker or replace the",
        "> full audit and final review.",
        "",
        "## Frozen artifact identities",
        "",
    ]
    for role, identity in frozen.items():
        sections.append(f"- **{role}:** `{identity}`")

    sections += [
        "",
        "## Open limitations (from Contract 10B audit)",
        "",
    ]
    for lim in limitations:
        sections.append(
            f"- **{lim['finding_id']}** ({lim['disposition']}): {lim['summary']}"
        )

    sections += [
        "",
        "## Population",
        "",
        f"- Source rows: {pop.get('source_count', '?')}",
        f"- Included rows: {pop.get('included_count', '?')}",
        f"- Excluded rows: {pop.get('excluded_count', 0)} "
        "(malformed/duplicate/non-finite rows block publication; exclusions are zero)",
        f"- Games: {EXPECTED_TOTAL_GAMES}",
        f"- Seasons: {', '.join(str(s) for s in REPORTING_SEASONS)}",
        "",
    ]
    for season, count in sorted((pop.get("rows_by_season") or {}).items()):
        sections.append(f"  - {season}: {count} rows per target")

    for target in TARGETS:
        t_data = targets.get(target, {})
        sections += [
            "",
            f"## Target: {target}",
            "",
            "### Headline — 2025",
            "",
        ]
        sections.append(_fmt_metrics(t_data.get("headline_2025", {})))

        sections += ["", "### Context — 2022–2024", ""]
        for season in CONTEXT_SEASONS:
            sections.append(f"**{season}:**")
            sections.append(
                _fmt_metrics(t_data.get("context_by_season", {}).get(str(season), {}))
            )

        sections += ["", "### Pooled 2022–2025", ""]
        sections.append(_fmt_metrics(t_data.get("pooled_2022_2025", {})))

        sections += ["", "### By completed-game stage", ""]
        for stage_key in ("0", "1", "2", "3", "4_plus"):
            label = f"Stage {stage_key}" if stage_key != "4_plus" else "Stage 4+"
            sections.append(f"**{label}:**")
            sections.append(
                _fmt_metrics(
                    t_data.get("by_completed_game_stage", {}).get(stage_key, {})
                )
            )

    sections += [
        "",
        "## Evidence provenance",
        "",
        f"- Run ID: `{run_id}`",
        f"- Scorecard manifest URI: `{manifest_uri}`",
        f"- Scorecard manifest raw SHA-256: `{manifest_raw_sha256}`",
        f"- Entry record: `{VERIFICATION_MANIFEST_URI}`",
        "",
        "---",
        "_This report is conditional historical development evidence only. "
        "It is not readiness evidence, 2026 authorization, a V4 comparison, "
        "or prospective forecasting permission._",
    ]

    return "\n".join(sections) + "\n"
