"""Preseason Continuity Prior Engine for V6 multi-factor ratings.

Replaces scalar carryover decay with a multi-signal preseason prior blending:
1. Prior-season terminal rating (signed for defense, decayed by rho^gap)
2. Returning production percentage (standardized per season, beta_ret = 0.25)
3. Multi-year recruiting composite (standardized per season, beta_rec = 0.20)
4. Staff continuity flag (new coach penalty, beta_coach = -0.15)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from cks_picks_cfb.preseason_features import canonical_team

from .contracts import ROLES, Game, Observation, Rating, utc

# ---------------------------------------------------------------------------
# Constants & Mappings
# ---------------------------------------------------------------------------

FOUR_FACTOR_IDS: tuple[str, ...] = (
    "rush_success_rate",
    "rush_explosiveness",
    "pass_success_rate",
    "pass_explosiveness",
    "rush_explosiveness_margin",
    "pass_explosiveness_margin",
)

FIVE_FACTOR_IDS: tuple[str, ...] = (
    *FOUR_FACTOR_IDS,
    "finish_points_per_opp",
)

FAMILY_MAP: dict[str, str] = {
    "rush_success_rate": "SR",
    "pass_success_rate": "SR",
    "rush_explosiveness": "Expl",
    "pass_explosiveness": "Expl",
    "rush_explosiveness_margin": "Expl",
    "pass_explosiveness_margin": "Expl",
    "finish_points_per_opp": "Finish",
}

VALID_RHO_FAMILIES: set[str] = {"SR", "Expl", "Finish"}
VALID_RHO_KEYS: set[str] = VALID_RHO_FAMILIES | set(FIVE_FACTOR_IDS)

DEFAULT_RHO: float = 0.60
DEFAULT_BETA_RET: float = 0.25
DEFAULT_BETA_REC: float = 0.20
DEFAULT_BETA_COACH: float = -0.15
DEFAULT_PRIOR_VARIANCE: float = 1.0


# ---------------------------------------------------------------------------
# Task 1: Terminal Seed Generalization with Defensive Polarity
# ---------------------------------------------------------------------------


def compute_terminal_seeds(
    observations: Sequence[Observation],
    measurement_id: str | None = None,
    *,
    signed_defense: bool = True,
) -> dict[Any, Rating]:
    """Compute per-(season, role, measurement_id) standardized seeds from observations.

    Parameters
    ----------
    observations:
        Game-level or cumulative observations. Only observations with finite
        value and exposure > 0 are included.
    measurement_id:
        If specified, filter observations to this measurement_id and return a dict
        keyed by (season, team, role).
        If None, return a dict keyed by (season, team, role, measurement_id).
    signed_defense:
        When True, defensive observations are negated (value_signed = -value)
        prior to standardization so that higher standardized ratings consistently
        indicate better performance for both offense and defense.
    """
    valid_obs: list[Observation] = []
    for obs in observations:
        if obs.value is None or not isfinite(obs.value) or obs.exposure <= 0:
            continue
        if measurement_id is not None and obs.measurement_id != measurement_id:
            continue
        valid_obs.append(obs)

    if not valid_obs:
        return {}

    # Aggregate exposure-weighted mean per (season, team, role, measurement_id)
    grouped: dict[tuple[int, str, str, str], list[Observation]] = defaultdict(list)
    for obs in valid_obs:
        grouped[(obs.season, obs.team, obs.role, obs.measurement_id)].append(obs)

    # Compute team values with defensive negation
    team_values: dict[tuple[int, str, str, str], float] = {}
    by_group: dict[tuple[int, str, str], dict[str, float]] = defaultdict(dict)

    for (season, team, role, mid), rows in grouped.items():
        total_exposure = sum(r.exposure for r in rows)
        raw_mean = (
            sum(r.value * r.exposure for r in rows if r.value is not None)
            / total_exposure
        )
        signed_mean = -raw_mean if (signed_defense and role == "defense") else raw_mean
        team_values[(season, team, role, mid)] = signed_mean
        by_group[(season, role, mid)][team] = signed_mean

    # Center and scale within each (season, role, measurement_id) cohort
    unique_mids = {obs.measurement_id for obs in valid_obs}
    emit_single_key = (measurement_id is not None) or (len(unique_mids) == 1)

    seeds: dict[Any, Rating] = {}
    for (season, role, mid), teams_dict in by_group.items():
        vals = np.array(list(teams_dict.values()), dtype=float)
        center = float(vals.mean())
        scale = max(float(vals.std()), 1e-6)
        for team, signed_val in teams_dict.items():
            std_rating = Rating(float((signed_val - center) / scale), 1.0)
            if emit_single_key:
                seeds[(season, team, role)] = std_rating
            else:
                seeds[(season, team, role, mid)] = std_rating

    return seeds


def compute_cohort_stats(
    observations: Sequence[Observation],
) -> dict[tuple[str, str], tuple[float, float]]:
    """Compute overall (mean, std) per (role, measurement_id) across team-season terminal observations.

    Stats are in raw observation space (positive allowed values for defense).
    """
    valid_obs = [
        o
        for o in observations
        if o.value is not None and isfinite(o.value) and o.exposure > 0
    ]
    grouped: dict[tuple[int, str, str, str], list[Observation]] = defaultdict(list)
    for obs in valid_obs:
        grouped[(obs.season, obs.team, obs.role, obs.measurement_id)].append(obs)

    team_raw_means: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (_s, _team, role, mid), rows in grouped.items():
        total_exp = sum(r.exposure for r in rows)
        if total_exp > 0:
            raw_m = (
                sum(r.value * r.exposure for r in rows if r.value is not None)
                / total_exp
            )
            team_raw_means[(role, mid)].append(raw_m)

    stats: dict[tuple[str, str], tuple[float, float]] = {}
    for (role, mid), vals in team_raw_means.items():
        arr = np.array(vals, dtype=float)
        stats[(role, mid)] = (float(arr.mean()), max(float(arr.std()), 1e-6))
    return stats


# ---------------------------------------------------------------------------
# Task 2: Continuity Ingestion & Fail-Closed Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamContinuity:
    """Preseason continuity features for a single team-season."""

    season: int
    team: str
    return_std: float = 0.0
    rec_std: float = 0.0
    new_coach: float = 0.0
    effective_at: datetime | None = None
    missing_reason: str | None = None


class ContinuityTable:
    """Container for per-season standardized continuity features."""

    def __init__(self, records: dict[tuple[int, str], TeamContinuity]):
        self._records = dict(records)

    def get(self, season: int, team: str) -> TeamContinuity | None:
        canonical = canonical_team(team) or team
        return self._records.get((season, canonical))

    def __contains__(self, key: tuple[int, str]) -> bool:
        season, team = key
        canonical = canonical_team(team) or team
        return (season, canonical) in self._records

    def __len__(self) -> int:
        return len(self._records)

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        games: Sequence[Game] | None = None,
        earliest_kickoffs: dict[int, datetime] | None = None,
    ) -> ContinuityTable:
        """Parse, validate, and standardize continuity inputs from a DataFrame.

        Asserts:
        - Season 2020 is strictly excluded (raises ValueError).
        - If timestamps are present and kickoffs are provided, effective_at <= kickoff
          for the season (raises ValueError if violated).
        - Returns, recruiting, and coaching are standardized per season.
        """
        if df.empty:
            return cls({})

        # 1. 2020 exclusion assertion
        seasons = pd.to_numeric(
            df.get("season", pd.Series(dtype=float)), errors="coerce"
        )
        if (seasons == 2020).any():
            raise ValueError(
                "2020 season data is strictly excluded from research chronology"
            )

        # 2. Build earliest kickoff lookup if games are provided
        kickoff_lookup: dict[int, datetime] = {}
        if earliest_kickoffs:
            kickoff_lookup.update(earliest_kickoffs)
        if games:
            for g in games:
                dt = utc(g.kickoff_utc)
                if g.season not in kickoff_lookup or dt < kickoff_lookup[g.season]:
                    kickoff_lookup[g.season] = dt

        # 3. Preseason timestamp verification
        has_effective = (
            "effective_at" in df.columns and df["effective_at"].notna().any()
        )
        if has_effective:
            if not kickoff_lookup:
                raise ValueError(
                    "effective_at timestamps are present in continuity input, but neither games nor earliest_kickoffs were supplied for kickoff validation"
                )
            for _, row in df.iterrows():
                s = int(row["season"])
                if s in kickoff_lookup and pd.notna(row["effective_at"]):
                    eff_dt = utc(str(row["effective_at"]))
                    if eff_dt > kickoff_lookup[s]:
                        raise ValueError(
                            f"Preseason continuity input for season {s} dated after kickoff: "
                            f"{eff_dt.isoformat()} > {kickoff_lookup[s].isoformat()}"
                        )

        # 4. Standardize features per season
        df_clean = df.copy()
        df_clean["season"] = seasons.astype(int)
        df_clean["team"] = df_clean["team"].map(canonical_team)

        # Identify source columns for returning production, recruiting, and coaching
        ret_col = next(
            (
                c
                for c in (
                    "return_percent_ppa",
                    "return_percent",
                    "percent_ppa",
                    "returning_production",
                )
                if c in df_clean
            ),
            None,
        )
        rec_col = next(
            (
                c
                for c in (
                    "recruiting_4yr",
                    "recruiting_current",
                    "recruiting_composite",
                    "talent_composite",
                    "points",
                )
                if c in df_clean
            ),
            None,
        )
        coach_col = next((c for c in ("coach_new", "new_coach") if c in df_clean), None)

        records: dict[tuple[int, str], TeamContinuity] = {}

        for season, s_df in df_clean.groupby("season"):
            s_int = int(season)

            # Standardize returning production using population std (ddof=0)
            ret_std_map: dict[str, float] = {}
            if ret_col:
                ret_vals = pd.to_numeric(s_df[ret_col], errors="coerce").dropna()
                if not ret_vals.empty:
                    arr = ret_vals.to_numpy(dtype=float)
                    mean_val = float(np.mean(arr))
                    scale_val = max(float(np.std(arr, ddof=0)), 1e-6)
                    for _, row in s_df.iterrows():
                        v = row[ret_col]
                        if pd.notna(v) and isfinite(float(v)) and row["team"]:
                            ret_std_map[row["team"]] = (float(v) - mean_val) / scale_val

            # Standardize recruiting using population std (ddof=0)
            rec_std_map: dict[str, float] = {}
            if rec_col:
                rec_vals = pd.to_numeric(s_df[rec_col], errors="coerce").dropna()
                if not rec_vals.empty:
                    arr = rec_vals.to_numpy(dtype=float)
                    mean_val = float(np.mean(arr))
                    scale_val = max(float(np.std(arr, ddof=0)), 1e-6)
                    for _, row in s_df.iterrows():
                        v = row[rec_col]
                        if pd.notna(v) and isfinite(float(v)) and row["team"]:
                            rec_std_map[row["team"]] = (float(v) - mean_val) / scale_val

            # Extract coaching flag
            coach_map: dict[str, float] = {}
            if coach_col:
                for _, row in s_df.iterrows():
                    v = row[coach_col]
                    if pd.notna(v) and row["team"]:
                        coach_map[row["team"]] = 1.0 if float(v) == 1.0 else 0.0

            for _, row in s_df.iterrows():
                team_name = row["team"]
                if not team_name:
                    continue
                eff_dt = (
                    utc(str(row["effective_at"]))
                    if (has_effective and pd.notna(row["effective_at"]))
                    else None
                )
                records[(s_int, team_name)] = TeamContinuity(
                    season=s_int,
                    team=team_name,
                    return_std=ret_std_map.get(team_name, 0.0),
                    rec_std=rec_std_map.get(team_name, 0.0),
                    new_coach=coach_map.get(team_name, 0.0),
                    effective_at=eff_dt,
                )

        return cls(records)


# ---------------------------------------------------------------------------
# Task 3: PreseasonPrior Engine
# ---------------------------------------------------------------------------


class PreseasonPrior:
    """Multi-signal Preseason Continuity Prior Engine.

    Computes initialized pregame team ratings prior = Rating(mean, variance=1.0)
    for any of the six 4-factor measurement IDs.

    Formula:
      prior_mean = rho_f^gap * terminal_signed + beta_ret * ret_std + beta_rec * rec_std + beta_coach * new_coach_flag
      prior_variance = 1.0

    Parameters
    ----------
    rho:
        Float broadcast to all IDs, or dict mapping family names {"SR", "Expl"}
        or exact measurement IDs to decay values in (0, 1].
    beta_ret:
        Fixed coefficient for standardized returning production (default: 0.25).
    beta_rec:
        Fixed coefficient for standardized recruiting composite (default: 0.20).
    beta_coach:
        Fixed coefficient for coaching change flag (default: -0.15).
    prior_variance:
        Prior variance (default: 1.0).
    continuity:
        Optional ContinuityTable providing standardized continuity features.
    terminal_seeds:
        Optional dictionary of pre-computed terminal standardized seeds.
    """

    def __init__(
        self,
        rho: float | dict[str, float] = DEFAULT_RHO,
        *,
        beta_ret: float = DEFAULT_BETA_RET,
        beta_rec: float = DEFAULT_BETA_REC,
        beta_coach: float = DEFAULT_BETA_COACH,
        prior_variance: float = DEFAULT_PRIOR_VARIANCE,
        continuity: ContinuityTable | None = None,
        terminal_seeds: dict[Any, Rating] | None = None,
        fallback_to_neutral: bool = True,
        cohort_stats: dict[tuple[str, str], tuple[float, float]] | None = None,
    ):
        self._validate_rho(rho)
        self.rho = rho if isinstance(rho, dict) else float(rho)

        for name, val in (
            ("beta_ret", beta_ret),
            ("beta_rec", beta_rec),
            ("beta_coach", beta_coach),
            ("prior_variance", prior_variance),
        ):
            if not isfinite(val):
                raise ValueError(f"{name} must be finite, got {val}")
        if prior_variance <= 0:
            raise ValueError("prior_variance must be strictly positive")

        self.beta_ret = float(beta_ret)
        self.beta_rec = float(beta_rec)
        self.beta_coach = float(beta_coach)
        self.prior_variance = float(prior_variance)
        self.continuity = continuity
        self.terminal_seeds = terminal_seeds or {}
        self.fallback_to_neutral = fallback_to_neutral
        self.cohort_stats = cohort_stats

    def _validate_rho(self, rho: float | dict[str, float]) -> None:
        if isinstance(rho, (int, float)):
            r = float(rho)
            if not isfinite(r) or not (0.0 < r <= 1.0):
                raise ValueError(f"rho must be in (0, 1], got {rho}")
            return

        if isinstance(rho, dict):
            for k, v in rho.items():
                if k not in VALID_RHO_KEYS:
                    raise ValueError(
                        f"Unknown rho key: '{k}'. Must be one of {sorted(VALID_RHO_KEYS)}"
                    )
                vf = float(v)
                if not isfinite(vf) or not (0.0 < vf <= 1.0):
                    raise ValueError(f"rho value for '{k}' must be in (0, 1], got {v}")

            # Verify that every 4-factor measurement ID can be resolved
            for mid in FOUR_FACTOR_IDS:
                fam = FAMILY_MAP[mid]
                if mid not in rho and fam not in rho:
                    raise ValueError(
                        f"rho dict incomplete: cannot resolve '{mid}' (needs '{mid}' or '{fam}')"
                    )
            return

        raise TypeError(
            f"rho must be float or dict[str, float], got {type(rho).__name__}"
        )

    def resolve_rho(self, measurement_id: str) -> float:
        """Resolve the effective rho decay for a given measurement ID."""
        if isinstance(self.rho, float):
            return self.rho
        if measurement_id in self.rho:
            return float(self.rho[measurement_id])
        fam = FAMILY_MAP.get(measurement_id)
        if fam and fam in self.rho:
            return float(self.rho[fam])
        if fam == "Finish":
            return 0.55
        raise ValueError(f"Cannot resolve rho for measurement_id: '{measurement_id}'")

    def build_prior(
        self,
        season: int,
        team: str,
        role: str,
        measurement_id: str,
        *,
        previous_terminal: Rating | None = None,
        previous_season: int | None = None,
    ) -> tuple[Rating, str | None]:
        """Compute the preseason prior Rating for (season, team, role, measurement_id).

        Returns (Rating, missing_reason). If missing_reason is not None, the prior
        is a neutral fallback Rating(m_c, s_c**2) in observation units, or (0.0, prior_variance).
        """
        if season == 2020:
            raise ValueError("2020 season excluded from research chronology")
        if role not in ROLES:
            raise ValueError(f"invalid role: '{role}'")

        canonical = canonical_team(team) or team

        # Resolve cohort moments (observation units vs z-score default)
        if self.cohort_stats is not None:
            m_c, s_c = self.cohort_stats.get((role, measurement_id), (0.0, 1.0))
            eff_variance = s_c**2
        else:
            m_c, s_c = 0.0, 1.0
            eff_variance = self.prior_variance

        # 1. Resolve prior terminal state if not provided directly
        if previous_terminal is None and self.terminal_seeds:
            # Look for most recent prior season strictly before target season (excluding 2020)
            eligible_seasons = sorted(
                {
                    k[0]
                    for k in self.terminal_seeds.keys()
                    if k[0] < season and k[0] != 2020
                },
                reverse=True,
            )
            for prev_s in eligible_seasons:
                key4 = (prev_s, canonical, role, measurement_id)
                key3 = (prev_s, canonical, role)
                if key4 in self.terminal_seeds:
                    previous_terminal = self.terminal_seeds[key4]
                    previous_season = prev_s
                    break
                elif key3 in self.terminal_seeds:
                    previous_terminal = self.terminal_seeds[key3]
                    previous_season = prev_s
                    break

        # If terminal state is still missing, fallback to neutral
        if previous_terminal is None:
            return Rating(float(m_c), float(eff_variance)), "missing_terminal_seed"

        # 2. Compute calendar gap & decay
        gap = (season - previous_season) if previous_season is not None else 1
        if gap < 1:
            raise ValueError(
                f"previous season {previous_season} does not precede target {season}"
            )

        rho_val = self.resolve_rho(measurement_id)
        decay = rho_val**gap
        z_decayed = decay * previous_terminal.mean

        # 3. Incorporate continuity features (in z-space)
        if self.continuity is not None:
            cont = self.continuity.get(season, canonical)
            if cont is not None:
                z_blend = (
                    z_decayed
                    + self.beta_ret * cont.return_std
                    + self.beta_rec * cont.rec_std
                    + self.beta_coach * cont.new_coach
                )
                reason = None
            elif self.fallback_to_neutral:
                return (
                    Rating(float(m_c), float(eff_variance)),
                    "missing_team_continuity",
                )
            else:
                z_blend = z_decayed
                reason = "terminal_only"
        elif self.fallback_to_neutral:
            return (
                Rating(float(m_c), float(eff_variance)),
                "missing_continuity_table",
            )
        else:
            z_blend = z_decayed
            reason = "terminal_only"

        # 4. Map z-space blend to observation units
        if self.cohort_stats is not None:
            if role == "defense":
                # For defense in observation space, higher quality z_blend means lower allowed production
                prior_mean = m_c - s_c * z_blend
            else:
                prior_mean = m_c + s_c * z_blend
        else:
            prior_mean = z_blend

        return Rating(float(prior_mean), float(eff_variance)), reason

    def build_fixed_priors(
        self,
        season: int,
        measurement_id: str,
        teams: Iterable[str],
    ) -> tuple[dict[tuple[int, str, str], Rating], set[tuple[int, str, str]]]:
        """Produce fixed_priors and neutral_fallback_keys ready for replay_ratings."""
        fixed: dict[tuple[int, str, str], Rating] = {}
        neutral_keys: set[tuple[int, str, str]] = set()

        for team in sorted(set(teams)):
            canonical = canonical_team(team) or team
            for role in ROLES:
                key = (season, canonical, role)
                rating, reason = self.build_prior(
                    season, canonical, role, measurement_id
                )
                if reason in {
                    "missing_terminal_seed",
                    "missing_team_continuity",
                    "missing_continuity_table",
                }:
                    neutral_keys.add(key)
                else:
                    fixed[key] = rating

        return fixed, neutral_keys
