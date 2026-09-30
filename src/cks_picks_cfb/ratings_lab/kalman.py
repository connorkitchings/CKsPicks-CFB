"""Dynamic State Space (Exposure-Weighted Kalman Filter) for V6 Multi-Factor Ratings."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from .contracts import Observation, Rating
from .priors import FAMILY_MAP

# Default fixed constants per family
DEFAULT_Q_BY_FAMILY: dict[str, float] = {
    "SR": 0.02,
    "Expl": 0.05,
    "Finish": 0.03,
}

DEFAULT_SIGMA2_BY_FAMILY: dict[str, float] = {
    "SR": 0.25,
    "Expl": 4.00,
    "Finish": 1.00,
}

FCS_COMPOSITE_NAME: str = "FCS_COMPOSITE"
FCS_PINNED_PRIOR = Rating(mean=-2.0, variance=0.5)


@dataclass(frozen=True)
class KalmanExposureDesign:
    """Exposure-weighted dynamic state-space (Kalman Filter) rating design.

    Maintains independent 1D state filters for each factor.
    Scales measurement noise inversely with factor exposure:
      R_t = sigma2_noise / max(n_t, 1)  (or with 0.25 down-weight for FCS opponents)
    Time update applies process drift q per game-step:
      sigma2_{t|t-1} = sigma2_{t-1} + q
    Missing observations skip the measurement update (variance expands by q).
    FCS games apply both a 25% exposure down-weight in R_t and a 1.5 innovation cap.
    """

    candidate_id: str
    mode: str = "incremental"
    q: float | Mapping[str, float] = 0.03
    sigma2_noise: float | Mapping[str, float] = 1.0
    rho: float = 0.60
    fcs_exposure_weight: float = 0.25
    fcs_innovation_cap: float = 1.5
    fcs_game_ids: frozenset[int] | None = None
    fcs_teams: frozenset[str] | None = None
    measurement_id: str | None = None
    variance_floor: float = 1e-6

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if self.mode not in {"incremental", "cumulative"}:
            raise ValueError("mode must be 'incremental' or 'cumulative'")
        if not (0.0 < self.rho <= 1.0):
            raise ValueError("rho must be in (0, 1]")
        if self.fcs_exposure_weight <= 0.0:
            raise ValueError("fcs_exposure_weight must be strictly positive")
        if self.fcs_innovation_cap <= 0.0:
            raise ValueError("fcs_innovation_cap must be strictly positive")
        if self.variance_floor <= 0.0:
            raise ValueError("variance_floor must be strictly positive")

        valid_keys = set(FAMILY_MAP.keys()) | set(DEFAULT_Q_BY_FAMILY.keys())

        # Validate process drift q
        if isinstance(self.q, (int, float)):
            q_val = float(self.q)
            if not isfinite(q_val) or q_val <= 0.0:
                raise ValueError(f"q must be positive and finite, got {self.q}")
        elif isinstance(self.q, Mapping):
            if not self.q:
                raise ValueError("q mapping cannot be empty")
            for k, v in self.q.items():
                if k not in valid_keys:
                    raise ValueError(f"Unknown key in q mapping: {k!r}")
                try:
                    vf = float(v)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"q mapping value for {k!r} must be numeric, got {v!r}"
                    ) from exc
                if not isfinite(vf) or vf <= 0.0:
                    raise ValueError(
                        f"q mapping value for {k!r} must be positive and finite, got {v}"
                    )
        else:
            raise TypeError(f"q must be float or Mapping, got {type(self.q).__name__}")

        # Validate observation noise variance sigma2_noise
        if isinstance(self.sigma2_noise, (int, float)):
            s2_val = float(self.sigma2_noise)
            if not isfinite(s2_val) or s2_val <= 0.0:
                raise ValueError(
                    f"sigma2_noise must be positive and finite, got {self.sigma2_noise}"
                )
        elif isinstance(self.sigma2_noise, Mapping):
            if not self.sigma2_noise:
                raise ValueError("sigma2_noise mapping cannot be empty")
            for k, v in self.sigma2_noise.items():
                if k not in valid_keys:
                    raise ValueError(f"Unknown key in sigma2_noise mapping: {k!r}")
                try:
                    vf = float(v)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"sigma2_noise value for {k!r} must be numeric, got {v!r}"
                    ) from exc
                if not isfinite(vf) or vf <= 0.0:
                    raise ValueError(
                        f"sigma2_noise value for {k!r} must be positive and finite, got {v}"
                    )
        else:
            raise TypeError(
                f"sigma2_noise must be float or Mapping, got {type(self.sigma2_noise).__name__}"
            )

    def resolve_q(self, measurement_id: str | None) -> float:
        """Resolve process drift q for the given measurement ID."""
        if isinstance(self.q, (int, float)):
            return float(self.q)

        mid = measurement_id or self.measurement_id or "rush_success_rate"
        if mid in self.q:
            return float(self.q[mid])
        fam = FAMILY_MAP.get(mid)
        if fam and fam in self.q:
            return float(self.q[fam])
        if fam and fam in DEFAULT_Q_BY_FAMILY:
            return DEFAULT_Q_BY_FAMILY[fam]
        return 0.03

    def resolve_sigma2(self, measurement_id: str | None) -> float:
        """Resolve observation noise variance sigma2_noise for the given measurement ID."""
        if isinstance(self.sigma2_noise, (int, float)):
            return float(self.sigma2_noise)

        mid = measurement_id or self.measurement_id or "rush_success_rate"
        if mid in self.sigma2_noise:
            return float(self.sigma2_noise[mid])
        fam = FAMILY_MAP.get(mid)
        if fam and fam in self.sigma2_noise:
            return float(self.sigma2_noise[fam])
        if fam and fam in DEFAULT_SIGMA2_BY_FAMILY:
            return DEFAULT_SIGMA2_BY_FAMILY[fam]
        return 1.00

    def initialize(self, previous: Rating | None, *, gap: int) -> Rating:
        """Initialize preseason prior state with inter-season carryover decay."""
        if previous is None:
            return Rating(0.0, 1.0)
        if previous.variance is None or gap < 1:
            raise ValueError("carryover needs positive variance and calendar gap")
        decay = self.rho**gap
        return Rating(
            decay * previous.mean,
            decay * decay * previous.variance + 1.0 - decay * decay,
        )

    def estimate(
        self, prior: Rating, evidence: Sequence[Observation]
    ) -> tuple[Rating, dict[str, object]]:
        """Run batch Kalman filter from prior over evidence sequence."""
        if prior.variance is None or prior.variance <= 0:
            raise ValueError("Kalman update needs positive prior variance")

        m = float(prior.mean)
        v = float(prior.variance)

        if not evidence:
            return Rating(m, v), {
                "method": "kalman_exposure",
                "candidate_id": self.candidate_id,
                "steps_count": 0,
                "usable_exposure": 0.0,
                "evidence_contributions": [],
            }

        # Check if team itself is the pinned FCS composite
        first_team = evidence[0].team
        if first_team == FCS_COMPOSITE_NAME:
            return FCS_PINNED_PRIOR, {
                "method": "kalman_exposure",
                "candidate_id": self.candidate_id,
                "is_fcs_composite": True,
                "steps_count": len(evidence),
                "usable_exposure": sum(o.exposure for o in evidence),
            }

        mid = evidence[0].measurement_id if evidence else self.measurement_id
        q_val = self.resolve_q(mid)
        sigma2_val = self.resolve_sigma2(mid)

        steps: list[dict[str, Any]] = []
        usable_exposure = 0.0

        for obs in evidence:
            # 1. Time update (drift per game-step)
            m_pred = m
            v_pred = v + q_val

            # 2. Missing observation check (skip measurement update, keep expanded variance)
            if obs.value is None or obs.exposure <= 0 or not isfinite(obs.value):
                m = m_pred
                v = v_pred
                steps.append(
                    {
                        "game_id": obs.game_id,
                        "skipped": True,
                        "missing_reason": obs.missing_reason or "zero_exposure_or_none",
                        "posterior_mean": m,
                        "posterior_variance": v,
                    }
                )
                continue

            n_t = float(obs.exposure)
            usable_exposure += n_t

            # 3. Check for FCS game (via fcs_game_ids, missing_reason flag, or unmapped FCS team)
            is_fcs = False
            if self.fcs_game_ids and obs.game_id in self.fcs_game_ids:
                is_fcs = True
            elif obs.missing_reason == "fcs_opponent":
                is_fcs = True
            elif self.fcs_teams and obs.team in self.fcs_teams:
                # Direct check if the team under estimation is an unmapped FCS program
                is_fcs = True

            # 4. Measurement noise scaling
            if is_fcs:
                r_t = sigma2_val / (self.fcs_exposure_weight * max(n_t, 1.0))
            else:
                r_t = sigma2_val / max(n_t, 1.0)

            # 5. Innovation & Capping
            y_t = float(obs.value)
            nu_t = y_t - m_pred
            if is_fcs:
                nu_star = max(
                    -self.fcs_innovation_cap, min(self.fcs_innovation_cap, nu_t)
                )
                capped = nu_star != nu_t
            else:
                nu_star = nu_t
                capped = False

            # 6. Kalman Gain & Posterior
            denom = v_pred + r_t
            k_t = v_pred / denom if denom > 0 else 0.0
            k_t = max(0.0, min(1.0, k_t))

            m = m_pred + k_t * nu_star
            v = max((1.0 - k_t) * v_pred, self.variance_floor)

            steps.append(
                {
                    "game_id": obs.game_id,
                    "exposure": n_t,
                    "is_fcs": is_fcs,
                    "observed": y_t,
                    "predicted": m_pred,
                    "innovation": nu_t,
                    "capped_innovation": nu_star,
                    "was_capped": capped,
                    "measurement_noise": r_t,
                    "kalman_gain": k_t,
                    "posterior_mean": m,
                    "posterior_variance": v,
                }
            )

        return Rating(float(m), float(v)), {
            "method": "kalman_exposure",
            "candidate_id": self.candidate_id,
            "q": q_val,
            "sigma2_noise": sigma2_val,
            "usable_exposure": usable_exposure,
            "steps_count": len(steps),
            "evidence_contributions": steps,
            "input_kind": self.mode,
        }
