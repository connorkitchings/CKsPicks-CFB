"""V5-exposure mathematics shared by isolated estimator experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contracts import Observation, Rating


@dataclass(frozen=True)
class ExposureDesign:
    candidate_id: str
    mode: str = "incremental"
    k: float = 8.0

    def __post_init__(self) -> None:
        if self.mode not in {"incremental", "cumulative"} or self.k <= 0:
            raise ValueError("invalid V5-exposure research design")

    def initialize(self, previous: Rating | None, *, gap: int) -> Rating:
        if previous is None:
            return Rating(0.0, 1.0)
        if previous.variance is None or gap < 1:
            raise ValueError("carryover needs positive variance and calendar gap")
        decay = 0.60**gap
        return Rating(
            decay * previous.mean, decay * decay * previous.variance + 1 - decay * decay
        )

    def estimate(
        self, prior: Rating, evidence: Sequence[Observation]
    ) -> tuple[Rating, dict[str, object]]:
        if prior.variance is None or prior.variance <= 0:
            raise ValueError("V5-exposure update needs positive prior variance")
        usable = [row for row in evidence if row.value is not None and row.exposure > 0]
        exposure = sum(row.exposure for row in usable)
        information = exposure / self.k
        variance = 1.0 / (1.0 / prior.variance + information)
        prior_weight = variance / prior.variance
        evidence_weight = 1.0 - prior_weight
        mean = variance * (
            prior.mean / prior.variance
            + sum(row.exposure * row.value for row in usable) / self.k
        )
        contributions = [
            {
                "game_id": row.game_id,
                "exposure": row.exposure,
                "adjusted_z": row.value,
                "contribution": variance * row.exposure * row.value / self.k,
                "missing_context_reason": row.missing_reason,
            }
            for row in usable
        ]
        return Rating(float(mean), float(variance)), {
            "method": "v5_exposure",
            "k": self.k,
            "usable_exposure": exposure,
            "prior_weight": prior_weight,
            "evidence_weight": evidence_weight,
            "prior_contribution": prior_weight * prior.mean,
            "evidence_contributions": contributions,
            "input_kind": self.mode,
        }


V5_SNAPSHOT_STREAM = ExposureDesign("v5_snapshot_stream_replica_v1")
V5_GAME_AT_CUTOFF = ExposureDesign("v5_game_adjusted_at_cutoff_v1")
V5_GAME_FIRST_BOUNDARY = ExposureDesign("v5_game_adjusted_first_boundary_v1")
V5_SINGLE_CUMULATIVE = ExposureDesign("v5_single_cumulative_v1", mode="cumulative")
