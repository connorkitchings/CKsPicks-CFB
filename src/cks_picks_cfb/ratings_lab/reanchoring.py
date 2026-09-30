"""Retrospective schedule graph re-anchoring across weekly prediction cutoffs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Mapping, Sequence

import numpy as np

from .contracts import Game, Observation, Rating, RatingState, utc
from .kalman import FCS_COMPOSITE_NAME, FCS_PINNED_PRIOR, KalmanExposureDesign


def filter_cutoff_games(
    games: Sequence[Game],
    cutoff_utc: str | datetime,
    *,
    availability_buffer_hours: float = 6.0,
) -> list[Game]:
    """Filter games strictly prior to cutoff adhering to the availability buffer.

    Zero games after cutoff are admitted (fail-closed causality).
    """
    cutoff_dt = utc(cutoff_utc) if isinstance(cutoff_utc, str) else cutoff_utc
    buffer = timedelta(hours=availability_buffer_hours)
    result = []
    for g in games:
        g_kickoff = utc(g.kickoff_utc)
        if g_kickoff + buffer <= cutoff_dt:
            result.append(g)
    return result


def reanchor_schedule_graph(
    games: Sequence[Game],
    observations: Sequence[Observation],
    priors: dict[tuple[int, str, str], Rating],
    *,
    week: int,
    num_passes: int = 4,
    shrinkage_k: float = 2.0,
    fcs_teams: set[str] | None = None,
) -> list[Observation]:
    """Run iterative 4-pass opponent adjustment on schedule graph for completed games 1..T.

    Applies early-season shrinkage for weeks 1-2:
      w_T = T / (T + shrinkage_k)  for T in {1, 2}; w_T = 1.0 for T >= 3
    FCS opponents are pinned to FCS_PINNED_PRIOR and excluded from league centers.
    """
    if not observations:
        return []

    # Map game opponents
    game_lookup = {g.game_id: g for g in games}
    fcs_set = set(fcs_teams or set()) | {FCS_COMPOSITE_NAME}

    # Group observations by measurement_id
    by_mid: dict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        if obs.value is not None and obs.exposure > 0:
            by_mid[obs.measurement_id].append(obs)

    reanchored_all: list[Observation] = []

    # Early-season shrinkage factor for weeks 1-2
    if week in {1, 2}:
        w_t = float(week) / (float(week) + shrinkage_k)
    else:
        w_t = 1.0

    for mid, mid_obs in by_mid.items():
        # Build initial ratings from priors
        season = mid_obs[0].season
        current_ratings: dict[tuple[str, str], float] = {}
        for k, r in priors.items():
            if len(k) == 4:
                s, team, role, p_mid = k
                if s == season and p_mid == mid:
                    current_ratings[(team, role)] = r.mean
            elif len(k) == 3:
                s, team, role = k
                if s == season and (team, role) not in current_ratings:
                    current_ratings[(team, role)] = r.mean

        def_vals = [
            v
            for (t, r), v in current_ratings.items()
            if t not in fcs_set and r == "defense"
        ]
        off_vals = [
            v
            for (t, r), v in current_ratings.items()
            if t not in fcs_set and r == "offense"
        ]
        mean_def = float(np.mean(def_vals)) if def_vals else 0.0
        mean_off = float(np.mean(off_vals)) if off_vals else 0.0
        std_def = float(np.std(def_vals)) if def_vals else 1.0
        std_off = float(np.std(off_vals)) if off_vals else 1.0

        # Determine whether priors are in observation space (rates/yards > 0.1) or z-space (mean ~ 0)
        is_observation_space = bool(current_ratings) and (mean_off > 0.1 or mean_def > 0.1)

        # Set pinned FCS rating
        if is_observation_space:
            current_ratings[(FCS_COMPOSITE_NAME, "offense")] = mean_off - 2.0 * std_off
            current_ratings[(FCS_COMPOSITE_NAME, "defense")] = mean_def + 2.0 * std_def
        else:
            current_ratings[(FCS_COMPOSITE_NAME, "offense")] = FCS_PINNED_PRIOR.mean
            current_ratings[(FCS_COMPOSITE_NAME, "defense")] = FCS_PINNED_PRIOR.mean

        # 4 iterative passes
        adj_values = {id(obs): float(obs.value) for obs in mid_obs}

        for pass_num in range(num_passes):
            # Compute cohort league means across FBS teams
            def_vals = [
                v
                for (t, r), v in current_ratings.items()
                if t not in fcs_set and r == "defense"
            ]
            off_vals = [
                v
                for (t, r), v in current_ratings.items()
                if t not in fcs_set and r == "offense"
            ]
            mean_def = float(np.mean(def_vals)) if def_vals else 0.0
            mean_off = float(np.mean(off_vals)) if off_vals else 0.0

            # Adjust each observation:
            # Offense adjusts against Opponent Defense; Defense adjusts against Opponent Offense
            for obs in mid_obs:
                g = game_lookup.get(obs.game_id)
                if not g:
                    continue
                opp = g.away_team if obs.team == g.home_team else g.home_team
                opp_canonical = FCS_COMPOSITE_NAME if opp in fcs_set else opp

                if obs.role == "offense":
                    opp_rating = current_ratings.get((opp_canonical, "defense"), mean_def)
                    if is_observation_space:
                        adj_val = float(obs.value) - (opp_rating - mean_def)
                    else:
                        adj_val = float(obs.value) + (opp_rating - mean_def)
                else:
                    opp_rating = current_ratings.get((opp_canonical, "offense"), mean_off)
                    adj_val = float(obs.value) - (opp_rating - mean_off)

                adj_values[id(obs)] = adj_val

            # Re-estimate team averages for next pass with damping and prior blending
            team_exposure: dict[tuple[str, str], float] = defaultdict(float)
            team_weighted_sum: dict[tuple[str, str], float] = defaultdict(float)
            for obs in mid_obs:
                if obs.team in fcs_set:
                    continue
                exp = float(obs.exposure)
                team_exposure[(obs.team, obs.role)] += exp
                team_weighted_sum[(obs.team, obs.role)] += exp * adj_values[id(obs)]

            damping = 0.5
            for (team, role), exp in team_exposure.items():
                if exp > 0:
                    avg_stat = team_weighted_sum[(team, role)] / exp
                    if is_observation_space:
                        perf_target = avg_stat
                    else:
                        perf_target = -avg_stat if role == "defense" else avg_stat

                    prior_r = priors.get((season, team, role, mid))
                    if prior_r is None:
                        prior_r = priors.get((season, team, role))
                    prior_val = prior_r.mean if prior_r is not None else 0.0
                    target = (1.0 - w_t) * prior_val + w_t * perf_target

                    current_ratings[(team, role)] = (
                        1.0 - damping
                    ) * current_ratings.get((team, role), prior_val) + damping * target

        # Apply early-season shrinkage
        for obs in mid_obs:
            raw_val = float(obs.value)
            adj_val = adj_values[id(obs)]
            shrunk_val = w_t * adj_val + (1.0 - w_t) * raw_val
            reanchored_all.append(
                replace(
                    obs,
                    value=shrunk_val,
                    missing_reason=f"reanchored_w{week}_pass{num_passes}"
                    if obs.missing_reason is None
                    else obs.missing_reason,
                )
            )

    return reanchored_all


def batch_refilter_states(
    games: Sequence[Game],
    reanchored_obs: Sequence[Observation],
    priors: Mapping[tuple[int, str, str] | tuple[int, str, str, str], Rating],
    design: KalmanExposureDesign,
    *,
    week: int,
    cutoff_utc: str,
    measurement_ids: Sequence[str] | None = None,
    fcs_teams: set[str] | None = None,
) -> list[RatingState]:
    """Batch re-filter from preseason priors standing at cutoff week T.

    Emits frozen pregame states theta_T for week T+1 predictions partitioned
    strictly per measurement ID.
    """
    # Infer FCS games from schedule and fcs_teams so design recognizes them
    fcs_set = set(fcs_teams or set()) | {FCS_COMPOSITE_NAME}
    fcs_gids = frozenset(
        g.game_id for g in games if g.home_team in fcs_set or g.away_team in fcs_set
    )
    if fcs_gids:
        active_fcs_gids = (
            frozenset(design.fcs_game_ids) | fcs_gids
            if design.fcs_game_ids
            else fcs_gids
        )
        design = replace(design, fcs_game_ids=active_fcs_gids)

    # Determine target measurement IDs
    if measurement_ids is not None:
        target_mids = list(measurement_ids)
    else:
        obs_mids = sorted({obs.measurement_id for obs in reanchored_obs})
        if obs_mids:
            target_mids = obs_mids
        else:
            prior_mids = sorted({k[3] for k in priors.keys() if len(k) == 4})
            if prior_mids:
                target_mids = prior_mids
            else:
                target_mids = [design.measurement_id or "rush_success_rate"]

    # Group evidence strictly by (team, role, measurement_id)
    by_trm: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    for obs in reanchored_obs:
        by_trm[(obs.team, obs.role, obs.measurement_id)].append(obs)

    # Sort each stream chronologically
    for trm in by_trm:
        by_trm[trm].sort(key=lambda o: (utc(o.available_utc), o.game_id))

    states: list[RatingState] = []
    seen_keys: set[tuple[int, int, str, str, str]] = set()

    for mid in target_mids:
        for game in games:
            for team in (game.home_team, game.away_team):
                for role in ("offense", "defense"):
                    key = (game.season, game.game_id, team, role, mid)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    prior = priors.get((game.season, team, role, mid))
                    if prior is None:
                        prior = priors.get((game.season, team, role), Rating(0.0, 1.0))

                    evidence = by_trm.get((team, role, mid), [])
                    batch_cutoff = utc(cutoff_utc)
                    valid_evidence = [
                        o for o in evidence if utc(o.available_utc) <= batch_cutoff
                    ]
                    rating, explanation = design.estimate(prior, valid_evidence)

                    ids = tuple(o.game_id for o in valid_evidence)
                    exp_sum = float(sum(o.exposure for o in valid_evidence))

                    state = RatingState(
                        candidate_id=design.candidate_id,
                        season=game.season,
                        week=game.week,
                        game_id=game.game_id,
                        cutoff_utc=cutoff_utc,
                        team=team,
                        role=role,
                        rating=rating,
                        prior=prior,
                        usable_exposure=exp_sum,
                        evidence_game_ids=ids,
                        explanation={
                            **explanation,
                            "measurement_id": mid,
                            "reanchored_week": week,
                            "cutoff_utc": cutoff_utc,
                        },
                    )
                    states.append(state)

    return states
