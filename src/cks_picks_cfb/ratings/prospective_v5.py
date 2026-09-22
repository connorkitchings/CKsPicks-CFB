"""Contract 06 prospective eligibility and reporting calculations for V5."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


class V5EvidenceError(ValueError):
    """Raised when prospective V5 evidence is incomplete or malformed."""


MINIMUM_PAIRED_GAMES = 40
FREEZE_HARD_LEAD_SECONDS = 3600
SCORE_STABILIZATION_SECONDS = 24 * 3600
REQUIRED_SLATES = 6
TARGETS = ("margin", "total")


@dataclass(frozen=True)
class EvidenceReview:
    candidate: str
    qualifying_slates: int
    slate_ledger: pd.DataFrame
    football_report: Mapping[str, Any]
    recommendation: str


def _utc(value: Any, *, label: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise V5EvidenceError(
            f"{label} must be a valid timezone-aware timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise V5EvidenceError(f"{label} must include a timezone")
    return parsed.tz_convert("UTC")


def derive_eligibility(
    attempts: pd.DataFrame,
    evaluations: pd.DataFrame,
    *,
    expected_candidate: str,
) -> pd.DataFrame:
    """Derive one disposition per attempt from verified parent evidence."""
    attempt_required = {
        "candidate",
        "season",
        "week",
        "run_id",
        "diagnostic_only",
        "readiness_verified",
        "readiness_overall",
        "first_kickoff",
        "freeze_completed_at",
        "declared_games",
        "paired_games",
        "normal_coverage",
        "freeze_manifest_sha256",
        "freeze_ref",
    }
    evaluation_required = {
        "candidate",
        "season",
        "week",
        "run_id",
        "outcome_version",
        "score_completed_at",
        "last_game_completed_at",
        "outcome_ref",
        "evaluation_ref",
        "evaluation_manifest_sha256",
        "evaluation_verified",
    }
    if missing := sorted(attempt_required - set(attempts)):
        raise V5EvidenceError(f"attempt ledger lacks columns: {missing}")
    if missing := sorted(evaluation_required - set(evaluations)):
        raise V5EvidenceError(f"evaluation ledger lacks columns: {missing}")
    if attempts.duplicated(["candidate", "season", "week", "run_id"]).any():
        raise V5EvidenceError("attempt ledger duplicates a run identity")
    joined = attempts.merge(
        evaluations,
        on=["candidate", "season", "week", "run_id"],
        how="left",
        suffixes=("", "_evaluation"),
        validate="one_to_many",
    )
    dispositions: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in joined.to_dict("records"):
        reasons: list[str] = []
        candidate = str(row["candidate"])
        season, week = int(row["season"]), int(row["week"])
        key = (candidate, season, week)
        if candidate != expected_candidate:
            reasons.append("candidate_identity_mismatch")
        if int(row["week"]) < 5:
            reasons.append("week_before_prospective_window")
        if bool(row["diagnostic_only"]):
            reasons.append("diagnostic_only")
        if not bool(row["readiness_verified"]) or row["readiness_overall"] != "ready":
            reasons.append("readiness_not_verified_ready")
        if pd.isna(row.get("first_kickoff")) or pd.isna(row.get("freeze_completed_at")):
            reasons.append("freeze_missing_or_unverified")
        else:
            first = _utc(row["first_kickoff"], label="first kickoff")
            freeze = _utc(row["freeze_completed_at"], label="freeze completion")
            lead = (first - freeze).total_seconds()
            if lead < FREEZE_HARD_LEAD_SECONDS:
                reasons.append("freeze_missed_t_minus_1h")
        if not bool(row["normal_coverage"]):
            reasons.append("schedule_coverage_incomplete")
        if int(row["paired_games"]) < MINIMUM_PAIRED_GAMES:
            reasons.append("paired_games_below_40")
        if int(row["paired_games"]) > int(row["declared_games"]):
            reasons.append("paired_population_exceeds_declared")
        if not row.get("freeze_manifest_sha256") or not row.get("freeze_ref"):
            reasons.append("freeze_manifest_unverified")
        evaluation_present = pd.notna(row.get("evaluation_ref")) and bool(
            str(row.get("evaluation_ref", "")).strip()
        )
        if not evaluation_present:
            reasons.append("evaluation_missing")
        else:
            if not bool(row.get("evaluation_verified")):
                reasons.append("evaluation_not_independently_verified")
            if not row.get("evaluation_manifest_sha256") or not row.get("outcome_ref"):
                reasons.append("outcome_lineage_missing")
            if evaluation_present and pd.notna(row.get("last_game_completed_at")):
                completed = _utc(
                    row["last_game_completed_at"], label="last game completion"
                )
                if pd.isna(row.get("score_completed_at")):
                    reasons.append("score_completion_time_missing")
                    scored = completed
                else:
                    scored = _utc(row["score_completed_at"], label="score completion")
                if (scored - completed).total_seconds() < SCORE_STABILIZATION_SECONDS:
                    reasons.append("outcomes_not_stable_for_24h")
            else:
                reasons.append("final_completion_time_missing")
        if key in seen:
            reasons.append("slate_already_disposed")
        qualifying = not reasons
        if qualifying:
            seen.add(key)
        dispositions.append(
            {
                "candidate": candidate,
                "season": season,
                "week": week,
                "run_id": str(row["run_id"]),
                "outcome_version": row.get("outcome_version"),
                "qualifying": qualifying,
                "reason": ";".join(reasons),
                "paired_games": int(row["paired_games"]),
                "freeze_ref": row.get("freeze_ref"),
                "evaluation_ref": row.get("evaluation_ref"),
                "freeze_manifest_sha256": row.get("freeze_manifest_sha256"),
                "evaluation_manifest_sha256": row.get("evaluation_manifest_sha256"),
                "supersedes_score_manifest_uri": row.get(
                    "supersedes_score_manifest_uri"
                ),
            }
        )
    result = pd.DataFrame.from_records(dispositions)
    if result.empty:
        return result
    return result.sort_values(
        ["season", "week", "run_id"], kind="mergesort"
    ).reset_index(drop=True)


def football_metrics(evaluations: pd.DataFrame) -> dict[str, Any]:
    """Summarize paired V5/V4 football results independently of quote inputs."""
    required = {
        "season",
        "week",
        "game_id",
        "target",
        "actual",
        "v5_mean",
        "v5_variance",
        "v4_mean",
        "completed_game_stage",
        "broader_population",
        "paired_population",
    }
    if missing := sorted(required - set(evaluations)):
        raise V5EvidenceError(f"football evaluation lacks columns: {missing}")
    if evaluations.duplicated(["season", "week", "game_id", "target"]).any():
        raise V5EvidenceError("football evaluation duplicates a game-target row")
    result: dict[str, Any] = {"row_count": int(len(evaluations)), "targets": {}}
    for target, rows in evaluations.groupby("target", sort=True):
        if target not in TARGETS:
            raise V5EvidenceError(f"unknown target: {target}")
        actual = pd.to_numeric(rows["actual"], errors="coerce").to_numpy(float)
        v5 = pd.to_numeric(rows["v5_mean"], errors="coerce").to_numpy(float)
        v4 = pd.to_numeric(rows["v4_mean"], errors="coerce").to_numpy(float)
        variance = pd.to_numeric(rows["v5_variance"], errors="coerce").to_numpy(float)
        if (
            not all(np.isfinite(values).all() for values in (actual, v5, variance))
            or (variance <= 0).any()
        ):
            raise V5EvidenceError(
                f"target {target} contains invalid forecast or outcome values"
            )
        paired = rows["paired_population"].astype(bool).to_numpy()
        if not np.isfinite(v4[paired]).all():
            raise V5EvidenceError(
                f"target {target} has invalid V4 values in the paired population"
            )
        err5, err4 = v5 - actual, v4[paired] - actual[paired]
        paired_rows = rows.loc[paired].copy()
        delta = np.abs(err5[paired]) - np.abs(err4)
        result["targets"][str(target)] = {
            "count": int(len(rows)),
            "v5_mae": float(np.mean(np.abs(err5))),
            "v5_rmse": float(np.sqrt(np.mean(np.square(err5)))),
            "v5_bias": float(np.mean(err5)),
            "v4_count": int(paired.sum()),
            "v4_mae_paired": float(np.mean(np.abs(err4))) if paired.any() else None,
            "v4_rmse_paired": (
                float(np.sqrt(np.mean(np.square(err4)))) if paired.any() else None
            ),
            "v4_bias_paired": float(np.mean(err4)) if paired.any() else None,
            "paired_mae_delta_v5_minus_v4": (
                float(np.mean(delta)) if paired.any() else None
            ),
            "paired_mae_delta_ci95": _cluster_bootstrap_interval(
                paired_rows, absolute_error_delta=delta
            ),
            "v5_crps": float(np.mean(_gaussian_crps(actual, v5, variance))),
            "v5_coverage_95": float(
                np.mean(np.abs(err5) <= 1.959963984540054 * np.sqrt(variance))
            ),
            "v5_mean_interval_width_95": float(
                np.mean(2 * 1.959963984540054 * np.sqrt(variance))
            ),
            "broader_games": int(
                rows.loc[rows["broader_population"].astype(bool), "game_id"].nunique()
            ),
            "paired_games": int(
                rows.loc[rows["paired_population"].astype(bool), "game_id"].nunique()
            ),
            "by_stage": {
                str(int(stage)): {
                    "count": int(len(group)),
                    "v5_mae": float(
                        np.mean(
                            np.abs(
                                group["v5_mean"].to_numpy(float)
                                - group["actual"].to_numpy(float)
                            )
                        )
                    ),
                    "paired_count": int(group["paired_population"].astype(bool).sum()),
                    "v4_mae_paired": _nullable_paired_mae(group),
                }
                for stage, group in rows.groupby("completed_game_stage", sort=True)
            },
        }
    return result


def _nullable_paired_mae(rows: pd.DataFrame) -> float | None:
    paired = rows[rows["paired_population"].astype(bool)]
    if paired.empty:
        return None
    return float(
        np.mean(
            np.abs(paired["v4_mean"].to_numpy(float) - paired["actual"].to_numpy(float))
        )
    )


def _cluster_bootstrap_interval(
    paired: pd.DataFrame,
    *,
    absolute_error_delta: np.ndarray,
    seed: int = 20260922,
    samples: int = 2000,
) -> dict[str, Any]:
    """Estimate a paired V5-minus-V4 MAE interval by resampling slate blocks."""
    if paired.empty:
        return {"estimate": None, "lower_95": None, "upper_95": None, "blocks": 0}
    block_keys = list(zip(paired["season"].astype(int), paired["week"].astype(int)))
    blocks = sorted(set(block_keys))
    estimate = float(np.mean(absolute_error_delta))
    if len(blocks) < 2:
        return {
            "estimate": estimate,
            "lower_95": None,
            "upper_95": None,
            "blocks": len(blocks),
            "reason": "fewer than two independent slate blocks",
        }
    values_by_block = {
        block: absolute_error_delta[
            np.array([key == block for key in block_keys], dtype=bool)
        ]
        for block in blocks
    }
    rng = np.random.default_rng(seed)
    estimates = np.empty(samples, dtype=float)
    for index in range(samples):
        selected = rng.choice(len(blocks), size=len(blocks), replace=True)
        estimates[index] = float(
            np.mean(
                np.concatenate([values_by_block[blocks[item]] for item in selected])
            )
        )
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return {
        "estimate": estimate,
        "lower_95": float(lower),
        "upper_95": float(upper),
        "blocks": len(blocks),
        "method": "paired slate-cluster bootstrap",
        "seed": seed,
        "samples": samples,
    }


def _gaussian_crps(
    actual: np.ndarray, mean: np.ndarray, variance: np.ndarray
) -> np.ndarray:
    from scipy.special import ndtr

    sigma = np.sqrt(variance)
    z = (actual - mean) / sigma
    phi = np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)
    return sigma * (z * (2 * ndtr(z) - 1) + 2 * phi - 1 / np.sqrt(np.pi))


def quote_diagnostic(
    football: pd.DataFrame,
    quotes: pd.DataFrame,
    *,
    cutoff: str,
) -> dict[str, Any]:
    """Describe authentic quote coverage without changing football metrics."""
    if not {"game_id", "target"} <= set(football):
        raise V5EvidenceError("football rows lack quote join keys")
    cap = _utc(cutoff, label="quote cutoff")
    if quotes.empty:
        return {
            "quote_rows": 0,
            "covered_games": 0,
            "missing_games": int(
                football[["game_id", "target"]].drop_duplicates().shape[0]
            ),
            "declared_game_targets": int(
                football[["game_id", "target"]].drop_duplicates().shape[0]
            ),
            "cutoff": cap.isoformat(),
        }
    required = {
        "game_id",
        "target",
        "provider",
        "quote_id",
        "captured_at",
        "effective_at",
        "line",
    }
    if missing := sorted(required - set(quotes)):
        raise V5EvidenceError(f"quote refs lack provenance fields: {missing}")
    capture = pd.to_datetime(quotes["captured_at"], utc=True, errors="coerce")
    effective = pd.to_datetime(quotes["effective_at"], utc=True, errors="coerce")
    if capture.isna().any() or effective.isna().any():
        raise V5EvidenceError("quote times must be authentic and timezone-aware")
    if (capture > cap).any() or (effective > cap).any():
        raise V5EvidenceError("quote source time exceeds its declared cutoff")
    if quotes.duplicated(["game_id", "target", "provider", "quote_id"]).any():
        raise V5EvidenceError("quote identifiers are not unique")
    if quotes[["provider", "quote_id"]].isna().any().any():
        raise V5EvidenceError("quote provider and quote IDs must be present")
    lines = pd.to_numeric(quotes["line"], errors="coerce").to_numpy(float)
    if not np.isfinite(lines).all():
        raise V5EvidenceError("quote lines must be finite numeric values")
    declared = set(
        map(tuple, football[["game_id", "target"]].drop_duplicates().to_numpy())
    )
    quote_keys = set(
        map(tuple, quotes[["game_id", "target"]].drop_duplicates().to_numpy())
    )
    return {
        "quote_rows": int(len(quotes)),
        "covered_games": len(declared & quote_keys),
        "missing_games": len(declared - quote_keys),
        "declared_game_targets": len(declared),
        "cutoff": cap.isoformat(),
        "providers": sorted(quotes["provider"].astype(str).unique().tolist()),
    }


def recommendation(
    *,
    qualifying_slates: int,
    validity_passed: bool,
    material_regression: bool,
    operational_problem: bool,
    satisfactory_review: bool,
) -> str:
    if qualifying_slates < REQUIRED_SLATES:
        return "continue_shadowing"
    if not validity_passed or material_regression or operational_problem:
        return "retain_v4"
    if satisfactory_review:
        return "prepare_phase7"
    return "continue_shadowing"


def review_evidence(
    attempts: pd.DataFrame,
    evaluations: pd.DataFrame,
    football_rows: pd.DataFrame,
    *,
    expected_candidate: str,
    validity_passed: bool = True,
    material_regression: bool = False,
    operational_problem: bool = False,
    satisfactory_review: bool = False,
) -> EvidenceReview:
    ledger = derive_eligibility(
        attempts, evaluations, expected_candidate=expected_candidate
    )
    count = (
        int(
            ledger.loc[ledger["qualifying"], ["season", "week"]]
            .drop_duplicates()
            .shape[0]
        )
        if not ledger.empty
        else 0
    )
    return EvidenceReview(
        candidate=expected_candidate,
        qualifying_slates=count,
        slate_ledger=ledger,
        football_report=football_metrics(football_rows),
        recommendation=recommendation(
            qualifying_slates=count,
            validity_passed=validity_passed,
            material_regression=material_regression,
            operational_problem=operational_problem,
            satisfactory_review=satisfactory_review,
        ),
    )
