"""V5-exposure mathematics and parameterized factory for isolated estimator experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from .contracts import Observation, Rating

# ---------------------------------------------------------------------------
# V5-compatible exposure-weighted Bayesian updater
# ---------------------------------------------------------------------------

_REGISTERED_TYPES: set[str] = {"parameterized_exposure"}
_REGISTERED_POLICIES: set[str] = {"v5_later_week_6h_v1"}


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

# ---------------------------------------------------------------------------
# Parameterized design: configurable k, rho, mode — suitable for YAML sweeps
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParameterizedDesign:
    """Exposure-weighted Bayesian updater with configurable k and rho.

    Drop-in replacement for ExposureDesign when you want to sweep
    hyperparameters via YAML rather than code.  Register via
    load_candidate_configs() or directly with replay.register().

    Parameters
    ----------
    candidate_id:
        Unique versioned identifier, e.g. ``exposure_k8_rho06_v1``.
    k:
        Equivalent prior exposure in possessions (k > 0).
    rho:
        Season-to-season carryover decay (0 < rho <= 1.0).
    mode:
        ``"incremental"`` (one obs per game) or ``"cumulative"`` (season snapshot).
    """

    candidate_id: str
    k: float = 8.0
    rho: float = 0.60
    mode: str = "incremental"

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if self.k <= 0:
            raise ValueError("k must be positive")
        if not (0 < self.rho <= 1.0):
            raise ValueError("rho must be in (0, 1]")
        if self.mode not in {"incremental", "cumulative"}:
            raise ValueError("mode must be 'incremental' or 'cumulative'")

    def initialize(self, previous: Rating | None, *, gap: int) -> Rating:
        if previous is None:
            return Rating(0.0, 1.0)
        if previous.variance is None or gap < 1:
            raise ValueError("carryover needs positive variance and calendar gap")
        decay = self.rho**gap
        return Rating(
            decay * previous.mean,
            decay * decay * previous.variance + 1 - decay * decay,
        )

    def estimate(
        self, prior: Rating, evidence: Sequence[Observation]
    ) -> tuple[Rating, dict[str, object]]:
        if prior.variance is None or prior.variance <= 0:
            raise ValueError("parameterized update needs positive prior variance")
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
            "method": "parameterized_exposure",
            "candidate_id": self.candidate_id,
            "k": self.k,
            "rho": self.rho,
            "usable_exposure": exposure,
            "prior_weight": prior_weight,
            "evidence_weight": evidence_weight,
            "prior_contribution": prior_weight * prior.mean,
            "evidence_contributions": contributions,
            "input_kind": self.mode,
        }


# ---------------------------------------------------------------------------
# YAML candidate loader
# ---------------------------------------------------------------------------

_ALLOWED_CANDIDATE_KEYS: set[str] = {
    "candidate_id",
    "type",
    "k",
    "rho",
    "mode",
    "description",
}


def _parse_candidate(raw: dict[str, Any], source: str) -> ParameterizedDesign:
    import math

    missing = {"candidate_id", "type", "k", "rho", "mode"} - raw.keys()
    if missing:
        raise ValueError(
            f"candidate config {source!r} missing fields: {sorted(missing)}"
        )
    extra = raw.keys() - _ALLOWED_CANDIDATE_KEYS
    if extra:
        raise ValueError(
            f"candidate config {source!r} has unexpected fields: {sorted(extra)}"
        )
    kind = raw["type"]
    if kind not in _REGISTERED_TYPES:
        raise ValueError(
            f"candidate config {source!r} has unregistered type {kind!r}; "
            f"known: {sorted(_REGISTERED_TYPES)}"
        )
    try:
        k_val = float(raw["k"])
        rho_val = float(raw["rho"])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"candidate config {source!r} has non-numeric k or rho"
        ) from exc
    if not (math.isfinite(k_val) and math.isfinite(rho_val)):
        raise ValueError(f"candidate config {source!r} has non-finite k or rho")
    return ParameterizedDesign(
        candidate_id=str(raw["candidate_id"]),
        k=k_val,
        rho=rho_val,
        mode=str(raw["mode"]),
    )


def load_candidate_configs(
    directory: Path,
    *,
    existing_ids: set[str] | None = None,
) -> dict[str, "ParameterizedDesign"]:
    """Load all ``*.yaml`` files in *directory* as ``ParameterizedDesign`` objects.

    Parameters
    ----------
    directory:
        Directory containing one YAML file per candidate.
    existing_ids:
        Candidate IDs already registered in code (e.g. from ``REGISTRY``).
        Any YAML that duplicates one of these raises ``ValueError``.

    Returns
    -------
    dict mapping ``candidate_id`` → ``ParameterizedDesign``, ready for
    ``replay.register()``.
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"candidate directory not found: {directory}")
    existing_ids = existing_ids or set()
    configs: dict[str, ParameterizedDesign] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError(f"candidate config {path.name!r} must be a YAML mapping")
        design = _parse_candidate(raw, path.name)
        if design.candidate_id in existing_ids:
            raise ValueError(
                f"candidate config {path.name!r} redefines code-registered id "
                f"{design.candidate_id!r}"
            )
        if design.candidate_id in configs:
            raise ValueError(
                f"duplicate candidate_id {design.candidate_id!r} across YAML files"
            )
        configs[design.candidate_id] = design
    return configs
