"""Pure comparison math for the attribution arms (no I/O, no model code).

Every function compares frames on explicit keys. Missing and extra rows, null flips and the
size of changes are reported separately so a difference can never hide inside an average.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

MATERIAL = 0.05  # change treated as material for raw, adjusted and rating values


def frame_digest(frame: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(frame.reset_index(drop=True), index=False)
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


def canonical_digest(frame: pd.DataFrame) -> str:
    """Record hash independent of row order, column order and numeric dtype.

    Columns are sorted, numerics become float64, other values become text, and rows are
    sorted on every column before hashing, so equal records hash equally however they were
    produced.
    """
    columns = sorted(frame.columns)
    normalized = frame[columns].copy()
    for column in columns:
        series = normalized[column]
        if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
            normalized[column] = series.astype("float64")
        else:
            normalized[column] = series.map(lambda v: None if pd.isna(v) else str(v))
    ordered = normalized.sort_values(columns, kind="mergesort", na_position="last")
    return frame_digest(ordered)


def json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def frame_delta(
    base: pd.DataFrame,
    other: pd.DataFrame,
    *,
    keys: Sequence[str],
    columns: Sequence[str],
    threshold: float = MATERIAL,
) -> dict[str, Any]:
    """Row-aligned change summary of ``other`` against ``base`` on ``keys``."""
    merged = base[[*keys, *columns]].merge(
        other[[*keys, *columns]],
        on=list(keys),
        how="outer",
        suffixes=("_b", "_o"),
        indicator=True,
    )
    both = merged[merged["_merge"] == "both"]
    report: dict[str, Any] = {
        "rows_base": int(len(base)),
        "rows_other": int(len(other)),
        "only_base": int((merged["_merge"] == "left_only").sum()),
        "only_other": int((merged["_merge"] == "right_only").sum()),
        "columns": {},
    }
    for column in columns:
        x = pd.to_numeric(both[f"{column}_b"], errors="coerce")
        y = pd.to_numeric(both[f"{column}_o"], errors="coerce")
        flip = x.isna() != y.isna()
        delta = (y - x).abs()
        changed = delta.gt(1e-12) | flip
        report["columns"][column] = {
            "compared": int((~x.isna() & ~y.isna()).sum()),
            "changed": int(changed.sum()),
            "null_flips": int(flip.sum()),
            "over_threshold": int(delta.gt(threshold).sum()),
            "max_abs": float(delta.max()) if delta.notna().any() else 0.0,
            "mean_abs": float(delta.mean()) if delta.notna().any() else 0.0,
        }
    return report


def final_ranks(team_states: pd.DataFrame) -> pd.DataFrame:
    """Each team's last pregame state per season, ranked within the season (min ties)."""
    ordered = team_states.sort_values(["season", "team", "cutoff_utc", "game_id"])
    last = ordered.groupby(["season", "team"], sort=False).tail(1).copy()
    for column in ("offense_rating", "defense_rating", "overall_rating"):
        last[f"{column}_rank"] = last.groupby("season")[column].rank(
            ascending=False, method="min"
        )
    return last[
        ["season", "team"] + [c for c in last.columns if c.endswith("_rank")]
    ].reset_index(drop=True)


def rank_moves(
    base: pd.DataFrame, other: pd.DataFrame, *, over: int = 5
) -> dict[str, Any]:
    merged = base.merge(other, on=["season", "team"], suffixes=("_b", "_o"))
    out: dict[str, Any] = {"team_seasons": int(len(merged))}
    for column in ("offense_rating", "defense_rating", "overall_rating"):
        move = (merged[f"{column}_rank_o"] - merged[f"{column}_rank_b"]).abs()
        out[column] = {
            "moved": int(move.gt(0).sum()),
            "over_threshold": int(move.gt(over).sum()),
            "max_move": int(move.max()) if len(move) else 0,
        }
    return out


def predict(bundle: Mapping[str, Any], features: pd.DataFrame) -> pd.DataFrame:
    """In-sample forecasts of a frozen bridge on its own feature frame."""
    out = features[["season", "week", "game_id"]].copy()
    for target in ("margin", "total"):
        entry = bundle["targets"][target]
        names = entry["feature_names"]
        center = np.asarray([entry["center"][n] for n in names], dtype=float)
        scale = np.asarray([entry["scale"][n] for n in names], dtype=float)
        coefficients = np.asarray(entry["coefficients"], dtype=float)
        matrix = (features[names].to_numpy(float) - center) / scale
        ridge = float(entry["intercept"]) + (matrix * coefficients).sum(axis=1)
        out[f"pred_{target}"] = features[f"offset_{target}"].to_numpy(float) + ridge
    return out.sort_values(["season", "week", "game_id"]).reset_index(drop=True)


def bundle_delta(base: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for target in ("margin", "total"):
        a, b = base["targets"][target], other["targets"][target]
        names = sorted(set(a["feature_names"]) | set(b["feature_names"]))

        def coefficient(entry: Mapping[str, Any], name: str) -> float:
            if name not in entry["feature_names"]:
                return 0.0
            return float(entry["coefficients"][entry["feature_names"].index(name)])

        diffs = {n: coefficient(b, n) - coefficient(a, n) for n in names}
        out[target] = {
            "coefficient_deltas": diffs,
            "max_abs_coefficient_delta": max(
                (abs(v) for v in diffs.values()), default=0.0
            ),
            "intercept_delta": float(b["intercept"]) - float(a["intercept"]),
            "calibration_variance": [
                float(a["calibration_variance"]),
                float(b["calibration_variance"]),
            ],
            "calibration_variance_delta": float(b["calibration_variance"])
            - float(a["calibration_variance"]),
            "alpha": [a["alpha"], b["alpha"]],
        }
    return out


def interaction(
    forecasts: Mapping[str, pd.DataFrame], *, baseline: str = "baseline"
) -> dict[str, Any]:
    """combined - baseline - sum of the single-factor effects, per game and target."""
    keys = ["season", "week", "game_id"]
    base = forecasts[baseline].set_index(keys)
    out: dict[str, Any] = {}
    for target in ("pred_margin", "pred_total"):
        total = forecasts["combined"].set_index(keys)[target] - base[target]
        parts = sum(
            forecasts[arm].set_index(keys)[target] - base[target]
            for arm in ("epa_only", "scoring_only", "offset_only")
        )
        residual = (total - parts).abs()
        out[target] = {
            "games": int(len(residual)),
            "nonzero": int(residual.gt(1e-9).sum()),
            "max_abs": float(residual.max()),
            "mean_abs": float(residual.mean()),
            "combined_mean_abs": float(total.abs().mean()),
        }
    return out
