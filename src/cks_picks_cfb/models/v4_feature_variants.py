"""Canonical, additive V4 preseason feature-variant definitions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

FAMILY_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "prior_core": (),
    "returning_production": ("home_return_", "away_return_"),
    "transfer_portal": ("home_transfer_", "away_transfer_"),
    "recruiting": ("home_recruiting_", "away_recruiting_"),
    "coaching": ("home_coach_", "away_coach_"),
    "roster_continuity": ("home_roster_", "away_roster_"),
    "preseason_rankings": ("home_preseason_", "away_preseason_"),
    "talent": ("home_talent", "away_talent"),
}


def additive_feature_variants(
    frame: pd.DataFrame,
    *,
    family_order: Sequence[str],
    context_features: Sequence[str],
) -> dict[str, list[str]]:
    """Return complete additive V4 variants in configured deterministic order.

    The first variant contains only structural context. Every later variant
    includes all preceding feature families. A family is unavailable when a
    required column is absent, non-numeric, missing, or non-finite on any row.
    """
    if not family_order or family_order[0] != "prior_core":
        raise ValueError("V4 feature variants must begin with prior_core")
    missing_context = sorted(set(context_features) - set(frame.columns))
    if missing_context:
        raise ValueError(f"V4 context features are missing: {missing_context}")
    selected = list(context_features)
    variants = {"prior_core": list(selected)}
    for family in family_order[1:]:
        if family not in FAMILY_PREFIXES:
            raise ValueError(f"Unknown V4 preseason feature family: {family}")
        prefixes = FAMILY_PREFIXES[family]
        columns = [
            column
            for column in frame.columns
            if any(column.startswith(prefix) for prefix in prefixes)
        ]
        if not columns:
            continue
        values = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
        if (
            values.isna().any().any()
            or not np.isfinite(values.to_numpy(dtype=float)).all()
        ):
            continue
        selected.extend(column for column in columns if column not in selected)
        variants[family] = list(selected)
    return variants


def selected_variant_features(
    frame: pd.DataFrame,
    *,
    family_order: Sequence[str],
    context_features: Sequence[str],
    variant: str,
) -> list[str]:
    """Return the exact frozen feature list for one selected V4 variant."""
    variants = additive_feature_variants(
        frame, family_order=family_order, context_features=context_features
    )
    if variant not in variants:
        raise ValueError(f"Frozen V4 feature variant is unavailable: {variant}")
    return variants[variant]
