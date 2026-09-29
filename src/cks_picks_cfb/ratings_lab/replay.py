"""Chronological replay with distinct event and cumulative evidence semantics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from .contracts import Game, Observation, Rating, RatingState, utc


class RatingDesign(Protocol):
    candidate_id: str
    mode: str

    def initialize(self, previous: Rating | None, *, gap: int) -> Rating: ...

    def estimate(
        self, prior: Rating, evidence: Sequence[Observation]
    ) -> tuple[Rating, dict[str, object]]: ...


@dataclass(frozen=True)
class CarryoverOnly:
    """Infrastructure reference: rho=0.60 carryover, no current-season update."""

    candidate_id: str = "carryover_only_rho_0_60_v1"
    mode: str = "incremental"

    def initialize(self, previous: Rating | None, *, gap: int) -> Rating:
        if previous is None:
            return Rating(0.0, 1.0)
        factor = 0.60**gap
        variance = previous.variance if previous.variance is not None else 1.0
        return Rating(
            factor * previous.mean, factor * factor * variance + 1 - factor * factor
        )

    def estimate(
        self, prior: Rating, evidence: Sequence[Observation]
    ) -> tuple[Rating, dict[str, object]]:
        return prior, {
            "method": "carryover_only",
            "prior_weight": 1.0,
            "consumed_evidence": [],
        }


REGISTRY: dict[str, RatingDesign] = {CarryoverOnly().candidate_id: CarryoverOnly()}


def register(design: RatingDesign) -> None:
    if design.mode not in {"incremental", "cumulative"} or not design.candidate_id:
        raise ValueError("invalid rating design registration")
    if design.candidate_id in REGISTRY:
        raise ValueError("rating design already registered")
    REGISTRY[design.candidate_id] = design


def _eligible(
    game: Game,
    observation: Observation,
    *,
    measurement_id: str,
    mode: str,
    require_earlier_week: bool = True,
) -> bool:
    if (
        observation.season != game.season
        or observation.measurement_id != measurement_id
    ):
        return False
    if (require_earlier_week and observation.week >= game.week) or utc(
        observation.available_utc
    ) > utc(game.kickoff_utc):
        return False
    if observation.kind != ("individual" if mode == "incremental" else "cumulative"):
        return False
    return observation.value is not None and observation.exposure > 0


def replay(
    games: Iterable[Game],
    observations: Iterable[Observation],
    *,
    design: RatingDesign,
    measurement_id: str,
    timing_class: str = "historically_reconstructed",
    external_terminals: dict[tuple[int, str, str], Rating] | None = None,
    fixed_priors: dict[tuple[int, str, str], Rating] | None = None,
    neutral_fallback_keys: set[tuple[int, str, str]] | None = None,
    cutoff_evidence: Callable[
        [Game, str, str, Sequence[Observation]], Sequence[Observation]
    ]
    | None = None,
    require_earlier_week: bool = True,
) -> list[RatingState]:
    """Emit only pregame states; never present same-game or future evidence."""
    if design.mode not in {"incremental", "cumulative"}:
        raise ValueError("unknown updater mode")
    schedule = sorted(games, key=lambda g: (g.season, utc(g.kickoff_utc), g.game_id))
    if not schedule or len({(g.season, g.game_id) for g in schedule}) != len(schedule):
        raise ValueError("empty or duplicate replay schedule")
    observations = list(observations)
    game_lookup = {(g.season, g.game_id): g for g in schedule}
    seen: set[tuple[int, int, str, str, str]] = set()
    for obs in observations:
        key = (obs.season, obs.game_id, obs.team, obs.role, obs.kind)
        if key in seen:
            raise ValueError("duplicate team/game/role observation")
        seen.add(key)
        source = game_lookup.get((obs.season, obs.game_id))
        if (
            source is None
            or obs.team not in (source.home_team, source.away_team)
            or obs.week != source.week
        ):
            raise ValueError("observation has no matching source game")
        if obs.timing_class != timing_class:
            raise ValueError("observation timing class differs from replay")
        if utc(obs.available_utc) < utc(source.kickoff_utc) + timedelta(hours=6):
            raise ValueError("observation predates availability buffer")
    by_season: dict[int, list[Game]] = defaultdict(list)
    for game in schedule:
        by_season[game.season].append(game)
    observation_index: dict[tuple[int, str, str], list[Observation]] = defaultdict(list)
    for observation in observations:
        observation_index[
            (observation.season, observation.team, observation.role)
        ].append(observation)
    previous_terminal: dict[tuple[str, str], tuple[int, Rating]] = {}
    seeds = external_terminals or {}
    seed_index: dict[tuple[str, str], list[int]] = defaultdict(list)
    for source_season, seed_team, seed_role in seeds:
        seed_index[(seed_team, seed_role)].append(source_season)
    result: list[RatingState] = []
    for season, season_games in sorted(by_season.items()):
        teams = {name for g in season_games for name in (g.home_team, g.away_team)}
        for team in teams:
            for role in ("offense", "defense"):
                older = [
                    source_season
                    for source_season in seed_index[(team, role)]
                    if source_season < season
                ]
                if older:
                    source_season = max(older)
                    if (team, role) not in previous_terminal or previous_terminal[
                        (team, role)
                    ][0] < source_season:
                        previous_terminal[(team, role)] = (
                            source_season,
                            seeds[(source_season, team, role)],
                        )
        priors = {}
        for team in teams:
            for role in ("offense", "defense"):
                key = (season, team, role)
                if fixed_priors is not None:
                    # The certified materializer supplies a neutral fallback for
                    # teams (usually FCS) outside its per-season prior table.
                    if key in fixed_priors:
                        priors[(team, role)] = fixed_priors[key]
                    elif (
                        neutral_fallback_keys is not None
                        and key in neutral_fallback_keys
                    ):
                        priors[(team, role)] = Rating(0.0, 1.0)
                    else:
                        raise ValueError(f"missing certified research prior: {key}")
                else:
                    previous = previous_terminal.get((team, role))
                    priors[(team, role)] = design.initialize(
                        previous[1] if previous else None,
                        gap=season - previous[0] if previous else 1,
                    )
        for game in season_games:
            if not game.forecast_eligible:
                continue
            for team in (game.home_team, game.away_team):
                for role in ("offense", "defense"):
                    team_obs = observation_index[(season, team, role)]
                    source = (
                        cutoff_evidence(game, team, role, team_obs)
                        if cutoff_evidence
                        else team_obs
                    )
                    if cutoff_evidence:
                        for item in source:
                            origin = game_lookup.get((item.season, item.game_id))
                            if (
                                origin is None
                                or item.team != team
                                or item.role != role
                                or item.team not in (origin.home_team, origin.away_team)
                                or item.week != origin.week
                                or utc(item.available_utc)
                                < utc(origin.kickoff_utc) + timedelta(hours=6)
                            ):
                                raise ValueError(
                                    "cutoff evidence has invalid source provenance"
                                )
                            if (
                                item.season != game.season
                                or item.week >= game.week
                                or utc(item.available_utc) > utc(game.kickoff_utc)
                                or item.measurement_id != measurement_id
                                or item.timing_class != timing_class
                                or item.kind
                                != (
                                    "individual"
                                    if design.mode == "incremental"
                                    else "cumulative"
                                )
                            ):
                                raise ValueError(
                                    "cutoff evidence violates target chronology or type"
                                )
                        if len({item.game_id for item in source}) != len(source):
                            raise ValueError("cutoff evidence duplicates a source game")
                    available = [
                        o
                        for o in source
                        if _eligible(
                            game,
                            o,
                            measurement_id=measurement_id,
                            mode=design.mode,
                            require_earlier_week=require_earlier_week,
                        )
                    ]
                    available.sort(key=lambda o: (utc(o.available_utc), o.game_id))
                    if design.mode == "cumulative":
                        # A cumulative estimate represents its entire contributor set.
                        # It is a replacement, never another additive observation.
                        available = available[-1:]
                        if available:
                            contributors = set(available[0].contributors)
                            source_games = {
                                o.game_id
                                for o in team_obs
                                if o.kind == "individual"
                                and _eligible(
                                    game,
                                    o,
                                    measurement_id=o.measurement_id,
                                    mode="incremental",
                                )
                            }
                            if not contributors.issubset(source_games):
                                raise ValueError(
                                    "cumulative evidence includes inadmissible source games"
                                )
                            if cutoff_evidence and contributors != source_games:
                                raise ValueError(
                                    "cutoff cumulative evidence omits admissible source games"
                                )
                    prior = priors[(team, role)]
                    rating, explanation = design.estimate(prior, available)
                    ids = (
                        tuple(sorted(available[0].contributors))
                        if design.mode == "cumulative" and available
                        else tuple(o.game_id for o in available)
                    )
                    explanation = {
                        **explanation,
                        "measurement_id": measurement_id,
                        "timing_class": timing_class,
                        "certified_fixed_prior": fixed_priors is not None,
                        "prior_source_season": previous_terminal[(team, role)][0]
                        if (team, role) in previous_terminal
                        else None,
                        "calendar_gap": season - previous_terminal[(team, role)][0]
                        if (team, role) in previous_terminal
                        else None,
                        "evidence_game_ids": ids,
                    }
                    result.append(
                        RatingState(
                            design.candidate_id,
                            season,
                            game.week,
                            game.game_id,
                            game.kickoff_utc,
                            team,
                            role,
                            rating,
                            prior,
                            float(sum(o.exposure for o in available)),
                            ids,
                            explanation,
                        )
                    )
        # Terminal states use every admissible season observation after its final
        # game. They are a prior source only for a later eligible season.
        for team in teams:
            for role in ("offense", "defense"):
                evidence = [
                    o
                    for o in observation_index[(season, team, role)]
                    if o.measurement_id == measurement_id
                    and o.value is not None
                    and o.exposure > 0
                    and o.kind
                    == ("individual" if design.mode == "incremental" else "cumulative")
                ]
                evidence.sort(key=lambda o: (utc(o.available_utc), o.game_id))
                if design.mode == "cumulative":
                    evidence = evidence[-1:]
                terminal, _ = design.estimate(priors[(team, role)], evidence)
                previous_terminal[(team, role)] = (
                    season,
                    seeds.get((season, team, role), terminal),
                )
    return result
