"""Checked V5 control inputs and a faithful historical snapshot-stream replica."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from cks_picks_cfb.audit.corpus import concat_all, read_any
from cks_picks_cfb.data.data_first_forecast_v1 import REQUIRED_RATING_CANDIDATE
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _fbs_universe,
    build_boundary_table,
    build_terminal_tables,
)

from .artifacts import ResearchStorage
from .contracts import Observation, Rating, RatingState
from .corpus import PINS, Corpus
from .replay import RatingDesign, replay


@dataclass
class V5Control:
    snapshots: pd.DataFrame
    priors: pd.DataFrame
    rating_states: pd.DataFrame

    def fixed_priors(self) -> dict[tuple[int, str, str], Rating]:
        result = {}
        for row in self.priors.itertuples(index=False):
            key = int(row.season), str(row.team), str(row.unit_role)
            if key in result:
                raise ValueError("duplicate certified V5 prior")
            result[key] = Rating(float(row.prior_mean), float(row.prior_variance))
        return result

    def fcs_fallbacks(
        self, corpus: Corpus
    ) -> tuple[set[tuple[int, str]], set[tuple[int, str, str]]]:
        fbs = _fbs_universe(corpus.population)
        teams = {
            (int(row.season), str(team))
            for row in corpus.population.itertuples(index=False)
            for team in (row.home_team, row.away_team)
        }
        fcs = teams - fbs
        reason = {
            (int(row.season), str(row.team), str(row.unit_role)): str(
                row.fallback_reason
            )
            for row in self.priors.itertuples(index=False)
        }
        no_predecessor = {
            (season, team, role)
            for season, team in fcs
            for role in ("offense", "defense")
            if reason.get((season, team, role), "no_predecessor") == "no_predecessor"
        }
        return fcs, no_predecessor


def _selected_rows(source, ref: dict, candidate: str) -> pd.DataFrame:
    return concat_all(
        part[part.candidate_id.eq(candidate)] for part in read_any(source, ref)
    )


def load_v5_control(storage: ResearchStorage, corpus: Corpus) -> V5Control:
    for name in ("measurement", "rating"):
        if corpus.parents[name]["sha256"] != PINS[name][1]:
            raise ValueError("control parent differs from imported corpus")
    source = storage.source
    measurement = json.loads(
        storage.read_source(
            key=PINS["measurement"][0], expected_sha256=PINS["measurement"][1]
        )
    )
    rating = json.loads(
        storage.read_source(key=PINS["rating"][0], expected_sha256=PINS["rating"][1])
    )
    verify_signed_payload(measurement, label="lab measurement parent")
    verify_signed_payload(rating, label="lab rating parent")
    snapshots = concat_all(read_any(source, measurement["output_refs"]["snapshots"]))
    refs = rating["output_refs"]
    priors = _selected_rows(source, refs["priors"], REQUIRED_RATING_CANDIDATE)
    states = _selected_rows(source, refs["rating_states"], REQUIRED_RATING_CANDIDATE)
    if (
        snapshots.empty
        or priors.empty
        or len(states) != 4 * 8935
        or states.duplicated(["season", "game_id", "team", "unit_role"]).any()
    ):
        raise ValueError("certified V5 control population changed")
    return V5Control(snapshots, priors, states)


def snapshot_stream(corpus: Corpus, control: V5Control) -> list[Observation]:
    """One cumulative team snapshot assigned to each source game at its first boundary."""
    boundaries = build_boundary_table(corpus.population).set_index(
        ["season", "game_id"]
    )
    scales = build_terminal_tables(corpus.terminal)
    snapshots = control.snapshots[
        control.snapshots.measurement_id.eq("ppp")
        & control.snapshots.adjustment_iteration.eq(4)
    ]
    lookup = {
        (
            int(row.season),
            int(row.as_of_game_id),
            str(row.team),
            str(row.unit_role),
        ): row.adjusted_value
        for row in snapshots.itertuples(index=False)
    }
    result: list[Observation] = []
    selected = corpus.observations[
        corpus.observations.measurement_id.eq("ppp")
        & corpus.observations.coverage_status.eq("observed")
        & pd.to_numeric(corpus.observations.denominator, errors="coerce").gt(0)
    ]
    for row in selected.itertuples(index=False):
        key = int(row.season), int(row.game_id)
        if key not in boundaries.index:
            continue
        boundary = boundaries.loc[key]
        value = lookup.get(
            (key[0], int(boundary.boundary_game_id), str(row.team), str(row.unit_role))
        )
        if value is None or not np.isfinite(value):
            continue
        scale = scales[("ppp", str(row.unit_role), key[0])]
        z = scale["sign"] * (float(value) - scale["center"]) / scale["scale"]
        result.append(
            Observation(
                key[0],
                int(row.week),
                key[1],
                str(row.team),
                str(row.unit_role),
                "ppp_adj_stream_v1",
                float(z),
                float(row.denominator),
                pd.Timestamp(boundary.boundary_cutoff_utc).isoformat(),
                "historically_reconstructed",
                source_sha256=corpus.parents["measurement"]["sha256"],
            )
        )
    return result


def verify_replica(
    states: list[RatingState], control: V5Control, *, tolerance: float = 1e-9
) -> dict[str, float]:
    expected = control.rating_states.set_index(
        ["season", "game_id", "team", "unit_role"]
    )
    actual = pd.DataFrame(
        [
            {
                "season": row.season,
                "game_id": row.game_id,
                "team": row.team,
                "unit_role": row.role,
                "rating_mean": row.rating.mean,
                "rating_variance": row.rating.variance,
                "usable_exposure": row.usable_exposure,
            }
            for row in states
        ]
    ).set_index(["season", "game_id", "team", "unit_role"])
    if len(actual) != len(expected) or set(actual.index) != set(expected.index):
        raise ValueError("V5 replica state population differs from certified state")
    result = {}
    for column in ("rating_mean", "rating_variance", "usable_exposure"):
        delta = float((actual[column] - expected[column]).abs().max())
        result[f"max_abs_{column}"] = delta
        if delta > tolerance:
            raise ValueError(f"V5 replica fidelity failed for {column}: {delta}")
    return result


def replay_v5_control(
    corpus: Corpus, control: V5Control, design: RatingDesign
) -> tuple[list[RatingState], dict[str, float]]:
    fcs, no_predecessor = control.fcs_fallbacks(corpus)
    priors = control.fixed_priors()
    neutral_keys = {
        (season, team, role)
        for season, team in fcs
        for role in ("offense", "defense")
        if (season, team, role) not in priors
    }
    states = replay(
        corpus.games(),
        snapshot_stream(corpus, control),
        design=design,
        measurement_id="ppp_adj_stream_v1",
        fixed_priors=priors,
        neutral_fallback_keys=neutral_keys,
        require_earlier_week=False,
    )
    states = apply_fcs_pool(states, fcs=fcs, no_predecessor=no_predecessor)
    return states, verify_replica(states, control)


def apply_fcs_pool(
    states: list[RatingState],
    *,
    fcs: set[tuple[int, str]],
    no_predecessor: set[tuple[int, str, str]],
) -> list[RatingState]:
    """Reproduce the inherited alphabetical FCS cohort fallback, including its order."""
    by_team: dict[tuple[int, str, str], list[int]] = {}
    for index, state in enumerate(states):
        if (state.season, state.team) in fcs:
            by_team.setdefault((state.season, state.team, state.role), []).append(index)
    result = list(states)
    for season in sorted({key[0] for key in by_team}):
        for role in ("offense", "defense"):
            history: list[tuple[pd.Timestamp, float, float]] = []
            for team in sorted(name for yr, name in fcs if yr == season):
                indices = sorted(
                    by_team.get((season, team, role), []),
                    key=lambda i: (
                        pd.Timestamp(result[i].cutoff_utc),
                        result[i].game_id,
                    ),
                )
                for index in indices:
                    state = result[index]
                    cutoff = pd.Timestamp(state.cutoff_utc)
                    if (
                        season,
                        team,
                        role,
                    ) in no_predecessor and not state.evidence_game_ids:
                        earlier = [
                            (mean, variance)
                            for time, mean, variance in history
                            if time < cutoff
                        ]
                        if earlier:
                            variance = 1.0 / (1.0 + len(earlier) * 100.0)
                            mean = variance * float(
                                np.mean([value for value, _ in earlier])
                            )
                            conservative = max(
                                np.sqrt(variance),
                                *(np.sqrt(value) for _, value in earlier),
                            )
                            rating = Rating(mean, conservative**2)
                            reason = "preceding_fcs_partial_pool"
                        else:
                            rating = Rating(0.0, 1.0)
                            reason = "neutral_no_preceding_fcs_cohort"
                        state = replace(
                            state,
                            rating=rating,
                            explanation={**state.explanation, "fcs_fallback": reason},
                        )
                        result[index] = state
                    history.append(
                        (cutoff, state.rating.mean, float(state.rating.variance))
                    )
    return result
