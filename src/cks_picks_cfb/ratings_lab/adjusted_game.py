"""Cutoff-specific, one-game-one-observation possession evidence for research."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from cks_picks_cfb.ratings.possession_rating_materializer import (
    build_boundary_table,
    build_terminal_tables,
)
from cks_picks_cfb.ratings.possession_ratings import standardization

from .contracts import Game, Observation, utc
from .corpus import Corpus


@dataclass(frozen=True)
class AdjustmentGraph:
    raw: dict[tuple[str, str], float]
    adjusted: dict[tuple[str, str], float]
    opponent_values: dict[tuple[str, str], float]
    opponent_centers: dict[str, float]
    source_ids: frozenset[int]


def four_pass_graph(rows: Sequence[object]) -> AdjustmentGraph:
    """Match V5's four passes and retain pass-three context for game values."""
    numerators: dict[tuple[str, str], float] = defaultdict(float)
    denominators: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows:
        key = str(row.team), str(row.unit_role)
        numerators[key] += float(row.numerator)
        denominators[key] += float(row.denominator)
    raw = {
        key: numerators[key] / exposure
        for key, exposure in denominators.items()
        if exposure > 0
    }
    adjusted = dict(raw)
    opponent_values: dict[tuple[str, str], float] = {}
    opponent_centers: dict[str, float] = {}
    for _ in range(4):
        centers_num: dict[str, float] = defaultdict(float)
        centers_den: dict[str, float] = defaultdict(float)
        for row in rows:
            key = str(row.team), str(row.unit_role)
            role = str(row.unit_role)
            if key in adjusted:
                centers_num[role] += adjusted[key] * float(row.denominator)
                centers_den[role] += float(row.denominator)
        centers = {
            role: centers_num[role] / exposure
            for role, exposure in centers_den.items()
            if exposure > 0
        }
        opponent_values = adjusted
        opponent_centers = centers
        deltas: dict[tuple[str, str], float] = defaultdict(float)
        delta_exposures: dict[tuple[str, str], float] = defaultdict(float)
        for row in rows:
            role = str(row.unit_role)
            opponent_role = "defense" if role == "offense" else "offense"
            opponent = adjusted.get((str(row.opponent), opponent_role))
            center = centers.get(opponent_role)
            if opponent is not None and center is not None:
                key = str(row.team), role
                exposure = float(row.denominator)
                deltas[key] += (opponent - center) * exposure
                delta_exposures[key] += exposure
        adjusted = {
            key: value - deltas[key] / delta_exposures[key]
            if delta_exposures[key] > 0
            else value
            for key, value in raw.items()
        }
    return AdjustmentGraph(
        raw,
        adjusted,
        opponent_values,
        opponent_centers,
        frozenset(int(row.game_id) for row in rows),
    )


class CutoffAdjustment:
    """A local-only provider whose values change as admissible opponents change."""

    def __init__(
        self,
        corpus: Corpus,
        snapshots: pd.DataFrame | None = None,
        *,
        extra_scale_seasons: tuple[int, ...] = (),
    ) -> None:
        self.corpus = corpus
        self.scales = build_terminal_tables(corpus.terminal)
        for season in extra_scale_seasons:
            if season == 2020 or season <= 2025:
                raise ValueError("extra scale season must follow the sealed history")
            for role in ("offense", "defense"):
                center, scale = standardization(
                    corpus.terminal, season=season, definition="ppp", role=role
                )
                self.scales[("ppp", role, season)] = {
                    "center": center,
                    "scale": scale,
                    "sign": -1.0 if role == "defense" else 1.0,
                }
        source = corpus.observations
        source = source[
            source.measurement_id.eq("ppp")
            & source.coverage_status.eq("observed")
            & pd.to_numeric(source.denominator, errors="coerce").gt(0)
        ].copy()
        source["available_utc"] = pd.to_datetime(
            source.kickoff_utc, utc=True
        ) + pd.Timedelta(hours=6)
        self.by_season = {
            int(season): list(frame.itertuples(index=False))
            for season, frame in source.groupby("season", sort=True)
        }
        self.opponents = {
            (int(row.season), int(row.game_id), str(row.team), str(row.unit_role)): str(
                row.opponent
            )
            for rows in self.by_season.values()
            for row in rows
        }
        self.source_sha = corpus.parents["measurement"]["sha256"]
        self.certified_snapshots = {}
        if snapshots is not None:
            selected = snapshots[
                snapshots.measurement_id.eq("ppp")
                & snapshots.adjustment_iteration.eq(4)
            ]
            self.certified_snapshots = {
                (
                    int(row.season),
                    int(row.as_of_game_id),
                    str(row.team),
                    str(row.unit_role),
                ): (float(row.adjusted_value), float(row.primary_exposure))
                for row in selected.itertuples(index=False)
                if pd.notna(row.adjusted_value)
            }

    @lru_cache(maxsize=16)
    def graph(self, game: Game) -> AdjustmentGraph:
        cutoff = utc(game.kickoff_utc)
        rows = [
            row
            for row in self.by_season.get(game.season, ())
            if int(row.week) < game.week
            and row.available_utc.to_pydatetime() <= cutoff
            and int(row.game_id) != game.game_id
        ]
        return four_pass_graph(rows)

    def _adjusted(
        self, source: Observation, graph: AdjustmentGraph
    ) -> tuple[float | None, str | None]:
        if source.value is None or source.exposure <= 0:
            return None, source.missing_reason or "missing_source_measurement"
        opponent = self.opponents.get(
            (source.season, source.game_id, source.team, source.role)
        )
        opponent_role = "defense" if source.role == "offense" else "offense"
        opponent_value = graph.opponent_values.get((opponent, opponent_role))
        center = graph.opponent_centers.get(opponent_role)
        if opponent_value is None or center is None:
            return source.value, "missing_opponent_context_raw_ppp"
        return source.value - (opponent_value - center), None

    def game_evidence(
        self, game: Game, team: str, role: str, raw_observations: Sequence[Observation]
    ) -> list[Observation]:
        graph = self.graph(game)
        result = []
        scale = self.scales[("ppp", role, game.season)]
        for source in raw_observations:
            if (
                source.season != game.season
                or source.team != team
                or source.role != role
                or source.week >= game.week
                or utc(source.available_utc) > utc(game.kickoff_utc)
                or source.game_id not in graph.source_ids
            ):
                continue
            native, reason = self._adjusted(source, graph)
            value = (
                None
                if native is None
                else scale["sign"] * (native - scale["center"]) / scale["scale"]
            )
            result.append(
                Observation(
                    source.season,
                    source.week,
                    source.game_id,
                    team,
                    role,
                    "ppp_adj_game_at_cutoff_v1",
                    value,
                    source.exposure,
                    source.available_utc,
                    source.timing_class,
                    missing_reason=reason,
                    source_sha256=self.source_sha,
                )
            )
        return result

    def single_cumulative(
        self, game: Game, team: str, role: str, raw_observations: Sequence[Observation]
    ) -> list[Observation]:
        graph = self.graph(game)
        sources = [
            source
            for source in raw_observations
            if source.game_id in graph.source_ids
            and source.week < game.week
            and utc(source.available_utc) <= utc(game.kickoff_utc)
            and source.value is not None
            and source.exposure > 0
        ]
        native = graph.adjusted.get((team, role))
        if not sources or native is None:
            return []
        certified = self.certified_snapshots.get(
            (game.season, game.game_id, team, role)
        )
        if self.certified_snapshots:
            if (
                certified is None
                or abs(certified[0] - native) > 1e-9
                or abs(certified[1] - sum(source.exposure for source in sources)) > 1e-9
            ):
                raise ValueError(
                    "cutoff cumulative value differs from certified snapshot"
                )
            native = certified[0]
        scale = self.scales[("ppp", role, game.season)]
        latest = max(sources, key=lambda item: (utc(item.available_utc), item.game_id))
        return [
            Observation(
                game.season,
                latest.week,
                latest.game_id,
                team,
                role,
                "ppp_adj_single_cumulative_v1",
                scale["sign"] * (native - scale["center"]) / scale["scale"],
                sum(source.exposure for source in sources),
                latest.available_utc,
                latest.timing_class,
                kind="cumulative",
                contributors=tuple(sorted(source.game_id for source in sources)),
                source_sha256=self.source_sha,
            )
        ]

    def first_boundary_stream(
        self, raw_observations: Sequence[Observation]
    ) -> list[Observation]:
        """Freeze each game's own adjusted value at first admissible boundary."""
        boundaries = build_boundary_table(self.corpus.population)
        games = {(game.season, game.game_id): game for game in self.corpus.games()}
        boundary_by_source = {
            (int(row.season), int(row.game_id)): games[
                (int(row.season), int(row.boundary_game_id))
            ]
            for row in boundaries.itertuples(index=False)
        }
        result = []
        ordered = sorted(
            raw_observations,
            key=lambda source: utc(
                boundary_by_source[(source.season, source.game_id)].kickoff_utc
            )
            if (source.season, source.game_id) in boundary_by_source
            else utc(source.available_utc),
        )
        for source in ordered:
            boundary = boundary_by_source.get((source.season, source.game_id))
            if boundary is None:
                continue
            evidence = self.game_evidence(boundary, source.team, source.role, [source])
            if evidence:
                item = evidence[0]
                result.append(
                    Observation(
                        item.season,
                        item.week,
                        item.game_id,
                        item.team,
                        item.role,
                        "ppp_adj_game_first_boundary_v1",
                        item.value,
                        item.exposure,
                        boundary.kickoff_utc,
                        item.timing_class,
                        missing_reason=item.missing_reason,
                        source_sha256=self.source_sha,
                    )
                )
        return result
