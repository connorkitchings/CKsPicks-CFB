"""Small, versioned data contracts shared by laboratory candidates and evaluators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Literal

DEVELOPMENT_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
HEADLINE_SEASONS = (2022, 2023, 2024, 2025)
ROLES = ("offense", "defense")


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("evidence timestamp must have a timezone")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Game:
    season: int
    week: int
    game_id: int
    kickoff_utc: str
    home_team: str
    away_team: str
    forecast_eligible: bool = True
    home_points: float | None = None
    away_points: float | None = None

    def __post_init__(self) -> None:
        if self.season == 2020 or self.week < 0 or self.game_id <= 0:
            raise ValueError("game escapes research chronology")
        if not self.home_team or not self.away_team or self.home_team == self.away_team:
            raise ValueError("invalid game teams")
        utc(self.kickoff_utc)


@dataclass(frozen=True)
class Observation:
    season: int
    week: int
    game_id: int
    team: str
    role: Literal["offense", "defense"]
    measurement_id: str
    value: float | None
    exposure: float
    available_utc: str
    timing_class: Literal["historically_reconstructed", "live"]
    kind: Literal["individual", "cumulative"] = "individual"
    contributors: tuple[int, ...] = ()
    missing_reason: str | None = None
    source_sha256: str = ""

    def __post_init__(self) -> None:
        if self.season == 2020 or self.role not in ROLES or self.exposure < 0:
            raise ValueError("invalid rating observation")
        utc(self.available_utc)
        if self.value is not None and not isfinite(self.value):
            raise ValueError("nonfinite observation")
        if (self.value is None or self.exposure == 0) and not self.missing_reason:
            raise ValueError("missing observation needs a reason")
        if self.kind == "individual" and self.contributors:
            raise ValueError(
                "individual observation cannot claim a cumulative evidence set"
            )
        if self.kind == "cumulative" and (
            not self.contributors
            or len(set(self.contributors)) != len(self.contributors)
        ):
            raise ValueError("cumulative observation needs unique contributors")


@dataclass(frozen=True)
class Rating:
    mean: float
    variance: float | None
    units: str = "standardized_quality"

    def __post_init__(self) -> None:
        if not isfinite(self.mean) or (
            self.variance is not None
            and (not isfinite(self.variance) or self.variance < 0)
        ):
            raise ValueError("invalid rating")


@dataclass(frozen=True)
class RatingState:
    candidate_id: str
    season: int
    week: int
    game_id: int
    cutoff_utc: str
    team: str
    role: str
    rating: Rating
    prior: Rating
    usable_exposure: float
    evidence_game_ids: tuple[int, ...]
    explanation: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentSpec:
    candidate_id: str
    measurement_id: str
    updater: str
    availability_policy: str = "v5_later_week_6h_v1"
    seasons: tuple[int, ...] = DEVELOPMENT_SEASONS

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.measurement_id or not self.updater:
            raise ValueError("experiment identity is incomplete")
        if self.availability_policy != "v5_later_week_6h_v1":
            raise ValueError("unregistered information policy")
        if (
            not self.seasons
            or 2020 in self.seasons
            or tuple(sorted(set(self.seasons))) != self.seasons
        ):
            raise ValueError("invalid experiment season sequence")
