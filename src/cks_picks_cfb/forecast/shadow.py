"""V5 shadow readiness, frozen replay, and prospective operations.

Producer module for Contract 05. Implements source-availability validation,
readiness reporting, and frozen-algorithm replay proof for the certified V5
forecast candidate. Freeze/score/ledger entry points land in Phase 05B; the
independent verifier lands in Phase 05C and must not import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from cks_picks_cfb.forecast.heads import evaluate_heads


class ShadowError(ValueError):
    """Raised when shadow inputs leave the sealed V5-05 boundary."""


REQUIRED_SOURCES = (
    "candidate",
    "schedule",
    "completed_games",
    "scoring",
    "priors",
    "team_states",
)
MANDATORY_SOURCES = (
    "candidate",
    "schedule",
    "completed_games",
    "scoring",
    "team_states",
)
NEUTRAL_PRIOR_FALLBACK = "neutral"


@dataclass(frozen=True)
class SourceStatus:
    source: str
    status: str
    timing_class: str
    fallback: str
    blocked_reason: str


def _timing(as_of: str, cutoff: str) -> str:
    """Classify a source manifest timestamp against the assessment cutoff."""
    try:
        source_time = pd.Timestamp(as_of)
        cutoff_time = pd.Timestamp(cutoff)
    except (ValueError, TypeError) as exc:
        raise ShadowError(f"unparseable source timestamp: {as_of!r}") from exc
    if source_time.tzinfo is None or cutoff_time.tzinfo is None:
        raise ShadowError("source and cutoff timestamps must be timezone-aware")
    return (
        "pre_cutoff"
        if source_time.astimezone(cutoff_time.tzinfo) <= cutoff_time
        else "post_cutoff"
    )


def check_source_availability(
    *,
    candidate: str,
    season: int,
    week: int,
    cutoff: str,
    forecast: dict[str, Any],
    rating_states: pd.DataFrame,
    schedule: pd.DataFrame,
    outcomes: pd.DataFrame,
    scoring_events: pd.DataFrame,
    priors: pd.DataFrame,
    measurement_as_of: str,
    rating_as_of: str,
) -> list[SourceStatus]:
    """Validate every candidate input for one prospective slate.

    Each source resolves to available/unavailable with a timing class,
    an applied fallback (if any declared one exists), and a named blocked
    reason when a mandatory input cannot support a freeze. Never reinterprets,
    backdates, or recaptures: missing evidence stays missing.
    """
    if not candidate:
        raise ShadowError("shadow candidate identity is missing")
    forecast_as_of = ((forecast.get("identity") or {}).get("as_of")) or ""
    if not forecast_as_of:
        raise ShadowError("forecast manifest as-of is missing")
    statuses: list[SourceStatus] = []
    statuses.append(
        SourceStatus(
            source="candidate",
            status="available",
            timing_class=_timing(forecast_as_of, cutoff),
            fallback="",
            blocked_reason="",
        )
    )
    if schedule.empty or not set(("season", "week", "game_id")) <= set(schedule):
        statuses.append(
            SourceStatus(
                source="schedule",
                status="unavailable",
                timing_class="missing",
                fallback="",
                blocked_reason=f"no schedule rows for {season} week {week}",
            )
        )
    elif schedule[schedule["season"].eq(season) & schedule["week"].eq(week)].empty:
        statuses.append(
            SourceStatus(
                source="schedule",
                status="unavailable",
                timing_class="missing",
                fallback="",
                blocked_reason=f"no schedule rows for {season} week {week}",
            )
        )
    else:
        statuses.append(
            SourceStatus(
                source="schedule",
                status="available",
                timing_class=_timing(measurement_as_of, cutoff),
                fallback="",
                blocked_reason="",
            )
        )
    if outcomes.empty or "season" not in outcomes:
        statuses.append(
            SourceStatus(
                source="completed_games",
                status="unavailable",
                timing_class="missing",
                fallback="",
                blocked_reason="no finalized outcomes precede the slate",
            )
        )
    else:
        prior = outcomes[outcomes["season"].lt(season)]
        if "week" in outcomes:
            prior = pd.concat(
                [
                    prior,
                    outcomes[outcomes["season"].eq(season) & outcomes["week"].lt(week)],
                ]
            )
        if prior.empty:
            statuses.append(
                SourceStatus(
                    source="completed_games",
                    status="unavailable",
                    timing_class="missing",
                    fallback="",
                    blocked_reason="no finalized outcomes precede the slate",
                )
            )
        else:
            statuses.append(
                SourceStatus(
                    source="completed_games",
                    status="available",
                    timing_class=_timing(measurement_as_of, cutoff),
                    fallback="",
                    blocked_reason="",
                )
            )
    if scoring_events.empty:
        statuses.append(
            SourceStatus(
                source="scoring",
                status="unavailable",
                timing_class="missing",
                fallback="",
                blocked_reason="scoring ledger is empty",
            )
        )
    else:
        statuses.append(
            SourceStatus(
                source="scoring",
                status="available",
                timing_class=_timing(measurement_as_of, cutoff),
                fallback="",
                blocked_reason="",
            )
        )
    if priors.empty:
        statuses.append(
            SourceStatus(
                source="priors",
                status="unavailable",
                timing_class="missing",
                fallback=NEUTRAL_PRIOR_FALLBACK,
                blocked_reason="",
            )
        )
    else:
        statuses.append(
            SourceStatus(
                source="priors",
                status="available",
                timing_class=_timing(rating_as_of, cutoff),
                fallback="",
                blocked_reason="",
            )
        )
    if (
        rating_states.empty
        or "season" not in rating_states
        or rating_states[rating_states["season"].eq(season)].empty
    ):
        statuses.append(
            SourceStatus(
                source="team_states",
                status="unavailable",
                timing_class="missing",
                fallback="",
                blocked_reason=f"no team states for {season}",
            )
        )
    else:
        statuses.append(
            SourceStatus(
                source="team_states",
                status="available",
                timing_class=_timing(rating_as_of, cutoff),
                fallback="",
                blocked_reason="",
            )
        )
    if {status.source for status in statuses} != set(REQUIRED_SOURCES):
        raise ShadowError("source availability is incomplete")
    return statuses


def readiness_overall(statuses: list[SourceStatus]) -> str:
    """Derive the slate verdict: ready only when every mandatory input holds."""
    by_source = {status.source: status for status in statuses}
    if set(by_source) != set(REQUIRED_SOURCES):
        raise ShadowError("readiness verdict lacks required sources")
    for source in MANDATORY_SOURCES:
        status = by_source[source]
        if status.status != "available" or status.timing_class != "pre_cutoff":
            return "blocked"
    return "ready"


def build_readiness_report(
    *,
    candidate: str,
    season: int,
    week: int,
    run_id: str,
    statuses: list[SourceStatus],
) -> tuple[pd.DataFrame, str]:
    """Persist one row per source with the derived overall verdict."""
    overall = readiness_overall(statuses)
    records = [
        {
            "candidate": candidate,
            "season": int(season),
            "week": int(week),
            "run_id": run_id,
            "source": status.source,
            "status": status.status,
            "timing_class": status.timing_class,
            "fallback": status.fallback,
            "blocked_reason": status.blocked_reason,
            "overall": overall,
        }
        for status in sorted(statuses, key=lambda item: item.source)
    ]
    return pd.DataFrame.from_records(records), overall


@dataclass(frozen=True)
class ReplayResult:
    predictions: pd.DataFrame
    predictions_sha: str
    identical: bool


def replay_frozen_forecast(
    *,
    features: pd.DataFrame,
    horizon: str,
    development_seasons: tuple[int, ...],
    replay_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    cutoff_season: int,
    bootstrap_seed: int,
    bootstrap_samples: int,
    reference_sha: str | None = None,
) -> ReplayResult:
    """Replay the frozen bridge on earlier-only history and prove identity.

    Fits use only seasons strictly before each replayed season; any feature
    row beyond ``cutoff_season`` fails closed so prospective outcomes can
    never enter a frozen replay. When ``reference_sha`` is given, the replayed
    retained-head predictions must digest-match it exactly.
    """
    required = {
        "season",
        "week",
        "game_id",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        "completed_game_stage",
    }
    if missing := sorted(required - set(features)):
        raise ShadowError(f"replay frame lacks columns: {missing}")
    if features["season"].gt(cutoff_season).any():
        raise ShadowError(
            "replay frame contains seasons beyond the frozen cutoff season"
        )
    if not replay_seasons or any(season > cutoff_season for season in replay_seasons):
        raise ShadowError("replay seasons must not exceed the frozen cutoff season")
    computation = evaluate_heads(
        features,
        horizon=horizon,
        development_seasons=tuple(development_seasons),
        outer_seasons=tuple(replay_seasons),
        alpha_grid=tuple(alpha_grid),
        floor=float(floor),
        bootstrap_seed=int(bootstrap_seed),
        bootstrap_samples=int(bootstrap_samples),
    )
    retained = computation.predictions.merge(
        pd.DataFrame(
            [
                {"target": target, "head": head}
                for target, head in computation.retained.items()
            ]
        ),
        on=["target", "head"],
        how="inner",
        validate="many_to_one",
    )
    digest = _canonical_digest(retained)
    identical = True if reference_sha is None else digest == reference_sha
    if reference_sha is not None and not identical:
        raise ShadowError("frozen replay differs from the reference predictions")
    return ReplayResult(
        predictions=retained, predictions_sha=digest, identical=identical
    )


def _canonical_digest(frame: pd.DataFrame) -> str:
    import hashlib
    import json

    ordered = frame.sort_values(list(frame.columns), kind="mergesort")
    payload = ordered.to_json(orient="records", date_format="iso", double_precision=15)
    return hashlib.sha256(
        json.dumps(json.loads(payload), sort_keys=True).encode()
    ).hexdigest()


def perturbation_invariance_proof(
    *,
    features: pd.DataFrame,
    perturb_season: int,
    **replay_kwargs: Any,
) -> bool:
    """Prove later-season outcome changes cannot alter earlier replay rows."""
    base = replay_frozen_forecast(features=features, **replay_kwargs)
    perturbed = features.copy()
    mask = perturbed["season"].ge(perturb_season)
    perturbed.loc[mask, "actual_margin"] = perturbed.loc[mask, "actual_margin"] + 25.0
    changed = replay_frozen_forecast(features=perturbed, **replay_kwargs)
    base_early = base.predictions[
        base.predictions["season"].lt(perturb_season)
    ].reset_index(drop=True)
    changed_early = changed.predictions[
        changed.predictions["season"].lt(perturb_season)
    ].reset_index(drop=True)
    if base_early.empty:
        raise ShadowError("perturbation proof lacks earlier replay rows")
    key_columns = ["season", "week", "game_id", "target", "head"]
    pd.testing.assert_frame_equal(
        base_early[key_columns],
        changed_early[key_columns],
        check_dtype=False,
    )
    return True
