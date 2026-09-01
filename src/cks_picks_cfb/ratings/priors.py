"""Sealed between-season prior estimators for the successor-v2 R2 tournament.

Each estimator implements the ``compute_prior`` interface and returns a
DataFrame with columns ``(team, measurement_id, unit_role, prior_mean,
prior_variance)``.  All estimators:

- Are read-only with respect to 2025 data (the policy enforces this).
- Apply the 2019→2021 gap transition with ``annual_decay_steps=2``.
- Never fit transition parameters on the 2019→2021 gap itself.
- Fall back to ``(neutral_mean=0.0, neutral_variance=1.0)`` for unknown teams.
- Never admit market-derived or bookmaker features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.season_lineage import SeasonLineagePolicy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIOR_SCHEMA_VERSION = "r2_prior_v1"

PRIOR_COLUMNS = (
    "team",
    "measurement_id",
    "unit_role",
    "prior_mean",
    "prior_variance",
    "candidate_id",
    "prior_source_season",
    "annual_decay_steps",
    "quality_flags",
)

CANDIDATE_IDS = (
    "neutral_population",
    "fixed_rho_0_60",
    "learned_offense_defense",
    "partially_pooled_components",
    "terminal_ewma_half_life_1",
    "terminal_ewma_half_life_2",
    "terminal_ewma_half_life_3",
    "continuity_ridge_alpha_0_1",
    "continuity_ridge_alpha_1",
    "continuity_ridge_alpha_10",
    "continuity_ridge_alpha_100",
)


class PriorError(ValueError):
    """Raised for invalid inputs to any prior estimator."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TerminalEntry:
    """One (team, measurement_id, unit_role) terminal posterior."""

    team: str
    measurement_id: str
    unit_role: str
    posterior_mean: float
    posterior_variance: float


def _extract_terminal(
    terminal_states: pd.DataFrame,
    *,
    source_season: int,
) -> dict[tuple[str, str, str], _TerminalEntry]:
    """Return a lookup of terminal posteriors for one source season."""
    mask = pd.to_numeric(terminal_states["season"], errors="coerce") == source_season
    rows = terminal_states[mask]
    result: dict[tuple[str, str, str], _TerminalEntry] = {}
    for row in rows.itertuples(index=False):
        key = (str(row.team), str(row.measurement_id), str(row.unit_role))
        result[key] = _TerminalEntry(
            team=str(row.team),
            measurement_id=str(row.measurement_id),
            unit_role=str(row.unit_role),
            posterior_mean=float(row.posterior_mean),
            posterior_variance=float(row.posterior_variance),
        )
    return result


def _apply_decay(
    mean: float,
    variance: float,
    *,
    rho: float,
    annual_decay_steps: int,
) -> tuple[float, float]:
    """Apply the annual decay operator ``annual_decay_steps`` times."""
    decay = rho**annual_decay_steps
    new_mean = decay * mean
    new_variance = decay**2 * variance + (1.0 - decay**2)
    return new_mean, new_variance


def _build_prior_rows(
    *,
    candidate_id: str,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    terminal_lookup: dict[tuple[str, str, str], _TerminalEntry],
    rho: float,
    annual_decay_steps: int,
    prior_source_season: int | None,
    neutral_mean: float = 0.0,
    neutral_variance: float = 1.0,
) -> pd.DataFrame:
    """Build prior rows for every (team, measurement_id, unit_role) combination."""
    rows: list[dict[str, Any]] = []
    for team in sorted(all_teams):
        for measurement_id, unit_role in sorted(all_measurements):
            key = (team, measurement_id, unit_role)
            entry = terminal_lookup.get(key)
            if entry is not None:
                mean, variance = _apply_decay(
                    entry.posterior_mean,
                    entry.posterior_variance,
                    rho=rho,
                    annual_decay_steps=annual_decay_steps,
                )
                flag = None
            else:
                mean, variance = neutral_mean, neutral_variance
                flag = "neutral_preseason_prior"
            rows.append(
                {
                    "team": team,
                    "measurement_id": measurement_id,
                    "unit_role": unit_role,
                    "prior_mean": mean,
                    "prior_variance": variance,
                    "candidate_id": candidate_id,
                    "prior_source_season": prior_source_season,
                    "annual_decay_steps": annual_decay_steps,
                    "quality_flags": flag,
                }
            )
    return pd.DataFrame(rows, columns=PRIOR_COLUMNS)


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------


def _validate_inputs(
    terminal_states: pd.DataFrame,
    target_season: int,
    policy: SeasonLineagePolicy,
) -> int:
    """Validate inputs and return the source season for the transition."""
    policy.assert_allowed(target_season)
    if not policy.is_historical(target_season):
        raise PriorError(f"Target season {target_season} is not historical development")
    if (
        not terminal_states.empty
        and pd.to_numeric(
            terminal_states.get("season", pd.Series(dtype=float)), errors="coerce"
        )
        .isin([2025, 2026, 2020])
        .any()
    ):
        raise PriorError("terminal_states may not contain 2025, 2026, or 2020 rows")
    transition = policy.prior_transition_for(target_season)
    if transition is None:
        # Seed season — no prior transition; use neutral
        return -1
    return transition.source_season


# ---------------------------------------------------------------------------
# Public: compute_prior dispatcher
# ---------------------------------------------------------------------------


def compute_prior(
    *,
    candidate_id: str,
    terminal_states: pd.DataFrame,
    target_season: int,
    policy: SeasonLineagePolicy,
    training_terminal_states: dict[int, pd.DataFrame] | None = None,
    admitted_context: pd.DataFrame | None = None,
    neutral_mean: float = 0.0,
    neutral_variance: float = 1.0,
) -> pd.DataFrame:
    """Dispatch to the correct estimator and return a prior DataFrame.

    Parameters
    ----------
    candidate_id:
        One of the 11 sealed candidate IDs.
    terminal_states:
        Season-terminal measurement component states for the *source* season.
        Must not contain 2025, 2026, or 2020 rows.
    target_season:
        The season whose preseason prior we are estimating.
    policy:
        The sealed successor-v2 season lineage policy.
    training_terminal_states:
        Mapping of season -> terminal states for all seasons preceding the
        target.  Required for ``learned_offense_defense``,
        ``partially_pooled_components``, EWMA, and Ridge candidates.
    admitted_context:
        Admitted preseason football context (required for Ridge candidates).
    neutral_mean / neutral_variance:
        Population fallback for unknown teams.
    """
    if candidate_id not in CANDIDATE_IDS:
        raise PriorError(f"Unknown candidate_id {candidate_id!r}")

    source_season = _validate_inputs(terminal_states, target_season, policy)
    transition = policy.prior_transition_for(target_season)
    annual_decay_steps = transition.annual_decay_steps if transition else 1

    # Collect universe of teams and (measurement_id, unit_role) pairs
    all_teams: set[str] = (
        set(terminal_states["team"].astype(str)) if not terminal_states.empty else set()
    )
    if training_terminal_states:
        for df in training_terminal_states.values():
            if not df.empty:
                all_teams |= set(df["team"].astype(str))
    all_measurements: set[tuple[str, str]] = set()
    if not terminal_states.empty and "measurement_id" in terminal_states.columns:
        all_measurements = set(
            zip(
                terminal_states["measurement_id"].astype(str),
                terminal_states["unit_role"].astype(str),
            )
        )
    if not all_measurements and training_terminal_states:
        for df in training_terminal_states.values():
            if not df.empty and "measurement_id" in df.columns:
                all_measurements |= set(
                    zip(df["measurement_id"].astype(str), df["unit_role"].astype(str))
                )

    if not all_measurements:
        raise PriorError(
            "terminal_states must contain measurement_id and unit_role columns"
        )

    if candidate_id == "neutral_population":
        return _neutral_population(
            target_season=target_season,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    if candidate_id == "fixed_rho_0_60":
        return _fixed_rho(
            candidate_id=candidate_id,
            terminal_states=terminal_states,
            source_season=source_season,
            annual_decay_steps=annual_decay_steps,
            rho=0.60,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    if candidate_id == "learned_offense_defense":
        return _learned_offense_defense(
            terminal_states=terminal_states,
            training_terminal_states=training_terminal_states or {},
            source_season=source_season,
            target_season=target_season,
            annual_decay_steps=annual_decay_steps,
            policy=policy,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    if candidate_id == "partially_pooled_components":
        return _partially_pooled_components(
            terminal_states=terminal_states,
            training_terminal_states=training_terminal_states or {},
            source_season=source_season,
            target_season=target_season,
            annual_decay_steps=annual_decay_steps,
            policy=policy,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    if candidate_id.startswith("terminal_ewma_half_life_"):
        half_life = int(candidate_id.split("_")[-1])
        return _ewma(
            candidate_id=candidate_id,
            training_terminal_states=training_terminal_states or {},
            source_season=source_season,
            annual_decay_steps=annual_decay_steps,
            policy=policy,
            target_season=target_season,
            half_life=half_life,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    if candidate_id.startswith("continuity_ridge_alpha_"):
        if admitted_context is None or admitted_context.empty:
            raise PriorError(
                f"{candidate_id} requires admitted_context; "
                "use Option A (skip context candidates) or run context admission first"
            )
        alpha_str = candidate_id.replace("continuity_ridge_alpha_", "").replace(
            "_", "."
        )
        alpha = float(alpha_str)
        return _continuity_ridge(
            candidate_id=candidate_id,
            terminal_states=terminal_states,
            training_terminal_states=training_terminal_states or {},
            admitted_context=admitted_context,
            source_season=source_season,
            target_season=target_season,
            annual_decay_steps=annual_decay_steps,
            policy=policy,
            alpha=alpha,
            all_teams=all_teams,
            all_measurements=all_measurements,
            neutral_mean=neutral_mean,
            neutral_variance=neutral_variance,
        )

    raise PriorError(f"Unhandled candidate_id {candidate_id!r}")


# ---------------------------------------------------------------------------
# Individual estimator implementations
# ---------------------------------------------------------------------------


def _neutral_population(
    *,
    target_season: int,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidate 0: always return the population neutral prior."""
    rows: list[dict[str, Any]] = []
    for team in sorted(all_teams):
        for measurement_id, unit_role in sorted(all_measurements):
            rows.append(
                {
                    "team": team,
                    "measurement_id": measurement_id,
                    "unit_role": unit_role,
                    "prior_mean": neutral_mean,
                    "prior_variance": neutral_variance,
                    "candidate_id": "neutral_population",
                    "prior_source_season": None,
                    "annual_decay_steps": 0,
                    "quality_flags": "neutral_preseason_prior",
                }
            )
    return pd.DataFrame(rows, columns=PRIOR_COLUMNS)


def _fixed_rho(
    *,
    candidate_id: str,
    terminal_states: pd.DataFrame,
    source_season: int,
    annual_decay_steps: int,
    rho: float,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidate 1: fixed rho=0.60 applied ``annual_decay_steps`` times."""
    terminal_lookup = _extract_terminal(terminal_states, source_season=source_season)
    return _build_prior_rows(
        candidate_id=candidate_id,
        all_teams=all_teams,
        all_measurements=all_measurements,
        terminal_lookup=terminal_lookup,
        rho=rho,
        annual_decay_steps=annual_decay_steps,
        prior_source_season=source_season,
        neutral_mean=neutral_mean,
        neutral_variance=neutral_variance,
    )


def _fit_rho_per_role(
    *,
    training_terminal_states: dict[int, pd.DataFrame],
    normal_transition_sources: set[int],
    role: str,
) -> float:
    """OLS estimate of the decay slope for one role across normal transitions."""
    x_vals: list[float] = []
    y_vals: list[float] = []
    for source_season in sorted(training_terminal_states):
        if source_season not in normal_transition_sources:
            continue
        target_season = source_season + 1
        if target_season not in training_terminal_states:
            continue
        source_df = training_terminal_states[source_season]
        target_df = training_terminal_states[target_season]
        src_mask = source_df["unit_role"].astype(str) == role
        tgt_mask = target_df["unit_role"].astype(str) == role
        src_rows = source_df[src_mask].set_index(["team", "measurement_id"])
        tgt_rows = target_df[tgt_mask].set_index(["team", "measurement_id"])
        common = src_rows.index.intersection(tgt_rows.index)
        for idx in common:
            x_vals.append(float(src_rows.loc[idx, "posterior_mean"]))
            y_vals.append(float(tgt_rows.loc[idx, "posterior_mean"]))
    if len(x_vals) < 4:
        return 0.60
    x = np.array(x_vals)
    y = np.array(y_vals)
    rho = float(np.clip(np.dot(x, y) / (np.dot(x, x) + 1e-8), 0.0, 1.0))
    return rho


def _learned_offense_defense(
    *,
    terminal_states: pd.DataFrame,
    training_terminal_states: dict[int, pd.DataFrame],
    source_season: int,
    target_season: int,
    annual_decay_steps: int,
    policy: SeasonLineagePolicy,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidate 2: separate learned rho per role (offense / defense).

    Parameters are fit only on normal one-year transitions.  The 2019->2021
    gap is never used as a fitting example.
    """
    normal_sources = {t.source_season for t in policy.normal_transitions}
    training_before = {
        s: df
        for s, df in training_terminal_states.items()
        if s < target_season and s not in policy.forbidden_seasons
    }
    rho_offense = _fit_rho_per_role(
        training_terminal_states=training_before,
        normal_transition_sources=normal_sources,
        role="offense",
    )
    rho_defense = _fit_rho_per_role(
        training_terminal_states=training_before,
        normal_transition_sources=normal_sources,
        role="defense",
    )
    terminal_lookup = _extract_terminal(terminal_states, source_season=source_season)
    rows: list[dict[str, Any]] = []
    for team in sorted(all_teams):
        for measurement_id, unit_role in sorted(all_measurements):
            rho = rho_offense if unit_role == "offense" else rho_defense
            key = (team, measurement_id, unit_role)
            entry = terminal_lookup.get(key)
            if entry is not None:
                mean, variance = _apply_decay(
                    entry.posterior_mean,
                    entry.posterior_variance,
                    rho=rho,
                    annual_decay_steps=annual_decay_steps,
                )
                flag = None
            else:
                mean, variance = neutral_mean, neutral_variance
                flag = "neutral_preseason_prior"
            rows.append(
                {
                    "team": team,
                    "measurement_id": measurement_id,
                    "unit_role": unit_role,
                    "prior_mean": mean,
                    "prior_variance": variance,
                    "candidate_id": "learned_offense_defense",
                    "prior_source_season": source_season,
                    "annual_decay_steps": annual_decay_steps,
                    "quality_flags": flag,
                }
            )
    return pd.DataFrame(rows, columns=PRIOR_COLUMNS)


def _partially_pooled_components(
    *,
    terminal_states: pd.DataFrame,
    training_terminal_states: dict[int, pd.DataFrame],
    source_season: int,
    target_season: int,
    annual_decay_steps: int,
    policy: SeasonLineagePolicy,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidate 3: per-(measurement_id, role) rho pooled toward a shared slope.

    Ridge penalty shrinks each (measurement_id, role) rho toward the
    cross-component mean, providing partial pooling.  Parameters are fit only
    on normal one-year transitions; the 2019->2021 gap is excluded.
    """
    normal_sources = {t.source_season for t in policy.normal_transitions}
    training_before = {
        s: df
        for s, df in training_terminal_states.items()
        if s < target_season and s not in policy.forbidden_seasons
    }
    x_rows: list[float] = []
    y_rows: list[float] = []
    component_role_idx: list[tuple[str, str]] = []
    for source_s in sorted(training_before):
        if source_s not in normal_sources:
            continue
        target_s = source_s + 1
        if target_s not in training_before:
            continue
        src_df = training_before[source_s]
        tgt_df = training_before[target_s]
        for src_row in src_df.itertuples(index=False):
            tgt_match = tgt_df[
                (tgt_df["team"].astype(str) == str(src_row.team))
                & (tgt_df["measurement_id"].astype(str) == str(src_row.measurement_id))
                & (tgt_df["unit_role"].astype(str) == str(src_row.unit_role))
            ]
            if tgt_match.empty:
                continue
            x_rows.append(float(src_row.posterior_mean))
            y_rows.append(float(tgt_match["posterior_mean"].iloc[0]))
            component_role_idx.append(
                (str(src_row.measurement_id), str(src_row.unit_role))
            )

    component_rhos: dict[tuple[str, str], float] = {}
    if len(x_rows) >= 4 and all_measurements:
        x_arr = np.array(x_rows)
        y_arr = np.array(y_rows)
        shared_rho = float(
            np.clip(np.dot(x_arr, y_arr) / (np.dot(x_arr, x_arr) + 1e-8), 0.0, 1.0)
        )
        for measurement_id, unit_role in sorted(all_measurements):
            mask = np.array(
                [cr == (measurement_id, unit_role) for cr in component_role_idx]
            )
            x_sub = x_arr[mask]
            y_sub = y_arr[mask]
            if len(x_sub) < 2:
                component_rhos[(measurement_id, unit_role)] = shared_rho
                continue
            lambda_val = 1.0
            y_centered = y_sub - shared_rho * x_sub
            residual_slope = float(
                np.dot(x_sub, y_centered) / (np.dot(x_sub, x_sub) + lambda_val)
            )
            rho = float(np.clip(shared_rho + residual_slope, 0.0, 1.0))
            component_rhos[(measurement_id, unit_role)] = rho
    else:
        for measurement_id, unit_role in sorted(all_measurements):
            component_rhos[(measurement_id, unit_role)] = 0.60

    terminal_lookup = _extract_terminal(terminal_states, source_season=source_season)
    rows: list[dict[str, Any]] = []
    for team in sorted(all_teams):
        for measurement_id, unit_role in sorted(all_measurements):
            rho = component_rhos.get((measurement_id, unit_role), 0.60)
            key = (team, measurement_id, unit_role)
            entry = terminal_lookup.get(key)
            if entry is not None:
                mean, variance = _apply_decay(
                    entry.posterior_mean,
                    entry.posterior_variance,
                    rho=rho,
                    annual_decay_steps=annual_decay_steps,
                )
                flag = None
            else:
                mean, variance = neutral_mean, neutral_variance
                flag = "neutral_preseason_prior"
            rows.append(
                {
                    "team": team,
                    "measurement_id": measurement_id,
                    "unit_role": unit_role,
                    "prior_mean": mean,
                    "prior_variance": variance,
                    "candidate_id": "partially_pooled_components",
                    "prior_source_season": source_season,
                    "annual_decay_steps": annual_decay_steps,
                    "quality_flags": flag,
                }
            )
    return pd.DataFrame(rows, columns=PRIOR_COLUMNS)


def _ewma(
    *,
    candidate_id: str,
    training_terminal_states: dict[int, pd.DataFrame],
    source_season: int,
    annual_decay_steps: int,
    policy: SeasonLineagePolicy,
    target_season: int,
    half_life: int,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidates 4-6: EWMA over all preceding terminal states.

    Weight for a season ``age`` years before source_season is
    ``0.5 ** (age / half_life)``.  The 2019->2021 gap counts as 2 years.
    """
    available_seasons = sorted(
        s
        for s in training_terminal_states
        if s <= source_season and s not in policy.forbidden_seasons
    )
    if not available_seasons:
        rows: list[dict[str, Any]] = []
        for team in sorted(all_teams):
            for measurement_id, unit_role in sorted(all_measurements):
                rows.append(
                    {
                        "team": team,
                        "measurement_id": measurement_id,
                        "unit_role": unit_role,
                        "prior_mean": neutral_mean,
                        "prior_variance": neutral_variance,
                        "candidate_id": candidate_id,
                        "prior_source_season": None,
                        "annual_decay_steps": annual_decay_steps,
                        "quality_flags": "neutral_preseason_prior",
                    }
                )
        return pd.DataFrame(rows, columns=PRIOR_COLUMNS)

    def _age_years(s: int, target: int) -> float:
        raw = target - s
        if s <= 2019 < target:
            raw += 1
        return float(max(raw, 0))

    weighted_sum: dict[tuple[str, str, str], float] = {}
    weight_total: dict[tuple[str, str, str], float] = {}
    for season in available_seasons:
        age = _age_years(season, source_season + 1)
        weight = 0.5 ** (age / half_life)
        season_df = training_terminal_states[season]
        for row in season_df.itertuples(index=False):
            key = (str(row.team), str(row.measurement_id), str(row.unit_role))
            weighted_sum[key] = weighted_sum.get(key, 0.0) + weight * float(
                row.posterior_mean
            )
            weight_total[key] = weight_total.get(key, 0.0) + weight

    rows = []
    base_var = neutral_variance * (0.5 ** (1.0 / half_life)) + (
        1.0 - 0.5 ** (1.0 / half_life)
    )
    for team in sorted(all_teams):
        for measurement_id, unit_role in sorted(all_measurements):
            key = (team, measurement_id, unit_role)
            w = weight_total.get(key, 0.0)
            if w > 0:
                mean = weighted_sum[key] / w
                variance = base_var
                flag = None
            else:
                mean, variance = neutral_mean, neutral_variance
                flag = "neutral_preseason_prior"
            rows.append(
                {
                    "team": team,
                    "measurement_id": measurement_id,
                    "unit_role": unit_role,
                    "prior_mean": mean,
                    "prior_variance": variance,
                    "candidate_id": candidate_id,
                    "prior_source_season": source_season,
                    "annual_decay_steps": annual_decay_steps,
                    "quality_flags": flag,
                }
            )
    return pd.DataFrame(rows, columns=PRIOR_COLUMNS)


def _continuity_ridge(
    *,
    candidate_id: str,
    terminal_states: pd.DataFrame,
    training_terminal_states: dict[int, pd.DataFrame],
    admitted_context: pd.DataFrame,
    source_season: int,
    target_season: int,
    annual_decay_steps: int,
    policy: SeasonLineagePolicy,
    alpha: float,
    all_teams: set[str],
    all_measurements: set[tuple[str, str]],
    neutral_mean: float,
    neutral_variance: float,
) -> pd.DataFrame:
    """Candidates 7-10: Ridge regression on admitted preseason football context.

    Only available when an immutable context admission report passes.
    Parameters are fit within each training fold only (never on target_season).
    """
    if "team" not in admitted_context.columns:
        raise PriorError("admitted_context must contain a 'team' column")
    market_keywords = {"spread", "total", "line", "odds", "juice", "market"}
    context_cols = {c.lower() for c in admitted_context.columns}
    if market_keywords & context_cols:
        raise PriorError("admitted_context must not contain market-derived columns")

    baseline = _fixed_rho(
        candidate_id=candidate_id,
        terminal_states=terminal_states,
        source_season=source_season,
        annual_decay_steps=annual_decay_steps,
        rho=0.60,
        all_teams=all_teams,
        all_measurements=all_measurements,
        neutral_mean=neutral_mean,
        neutral_variance=neutral_variance,
    )

    normal_sources = {t.source_season for t in policy.normal_transitions}
    training_before = {
        s: df
        for s, df in training_terminal_states.items()
        if s < target_season and s not in policy.forbidden_seasons
    }
    target_context = admitted_context[
        pd.to_numeric(
            admitted_context.get("season", pd.Series(dtype=float)), errors="coerce"
        )
        == target_season
    ]
    if target_context.empty:
        return baseline

    feature_cols = [
        c
        for c in target_context.columns
        if c not in {"team", "season"} and target_context[c].dtype.kind in ("f", "i")
    ]
    if not feature_cols:
        return baseline

    x_train: list[np.ndarray] = []
    y_train: list[float] = []
    for source_s in sorted(training_before):
        if source_s not in normal_sources:
            continue
        next_s = source_s + 1
        if next_s not in training_before:
            continue
        ctx = admitted_context[
            pd.to_numeric(
                admitted_context.get("season", pd.Series(dtype=float)), errors="coerce"
            )
            == next_s
        ]
        if ctx.empty:
            continue
        ctx_indexed = ctx.set_index("team")
        src_df = training_before[source_s]
        tgt_df = training_before[next_s]
        for tgt_row in tgt_df.itertuples(index=False):
            if str(tgt_row.team) not in ctx_indexed.index:
                continue
            src_match = src_df[
                (src_df["team"].astype(str) == str(tgt_row.team))
                & (src_df["measurement_id"].astype(str) == str(tgt_row.measurement_id))
                & (src_df["unit_role"].astype(str) == str(tgt_row.unit_role))
            ]
            if src_match.empty:
                continue
            src_mean = float(src_match["posterior_mean"].iloc[0])
            decay = 0.60**1
            residual = float(tgt_row.posterior_mean) - decay * src_mean
            ctx_feats = ctx_indexed.loc[str(tgt_row.team), feature_cols].to_numpy(float)
            if not np.isfinite(ctx_feats).all():
                continue
            x_train.append(ctx_feats)
            y_train.append(residual)

    if len(x_train) < 4:
        return baseline

    ridge = Ridge(alpha=alpha, fit_intercept=True)
    ridge.fit(np.array(x_train), np.array(y_train))

    result = baseline.copy()
    ctx_target_indexed = target_context.set_index("team")
    for i, row in result.iterrows():
        team = str(row["team"])
        if team not in ctx_target_indexed.index:
            continue
        ctx_feats = ctx_target_indexed.loc[team, feature_cols].to_numpy(float)
        if not np.isfinite(ctx_feats).all():
            continue
        correction = float(ridge.predict(ctx_feats.reshape(1, -1))[0])
        result.at[i, "prior_mean"] = float(row["prior_mean"]) + correction
        result.at[i, "candidate_id"] = candidate_id
    return result
