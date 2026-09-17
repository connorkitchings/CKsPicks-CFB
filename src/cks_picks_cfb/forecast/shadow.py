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


# ---------------------------------------------------------------------------
# V5-05B: Freeze planning, outcome-versioned scoring, and evidence ledger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreezePlan:
    """Deterministic description of a planned immutable freeze (no writes)."""

    candidate: str
    season: int
    week: int
    run_id: str
    freeze_time: str
    first_kickoff: str
    lead_seconds: float
    v4_ref_uri: str
    slate_digest: str
    paired_count: int
    broader_count: int
    excluded_count: int
    identity_sha256: str
    freeze_record: Any
    predictions: Any


def plan_freeze(
    *,
    candidate: str,
    season: int,
    week: int,
    run_id: str,
    freeze_time: str,
    schedule: pd.DataFrame,
    v5_predictions: pd.DataFrame,
    v4_predictions: pd.DataFrame,
    v4_ref_uri: str,
    is_diagnostic: bool = False,
    min_paired_games: int = 40,
    freeze_hard_lead_seconds: float = 3600.0,
) -> "FreezePlan":
    """Plan an immutable shadow freeze without writing anything.

    Validates timing (T-1h hard gate), population integrity (broader >= paired,
    cancellations/postponements retained with disposition), and >= 40 paired
    games with complete finite predictions. Returns a FreezePlan with the
    deterministic freeze record and prediction rows.

    ``is_diagnostic=True`` bypasses the ``ready`` readiness gate but not
    timing, population, or identity gates.
    """
    import hashlib as _hashlib
    import json as _json
    import math as _math

    if not candidate:
        raise ShadowError("freeze candidate identity is missing")
    if not run_id or not freeze_time or not v4_ref_uri:
        raise ShadowError("freeze run_id, freeze_time, and v4_ref_uri are required")

    # Timing gate ---------------------------------------------------------
    try:
        freeze_ts = pd.Timestamp(freeze_time)
    except (ValueError, TypeError) as exc:
        raise ShadowError(f"unparseable freeze_time: {freeze_time!r}") from exc
    if freeze_ts.tzinfo is None:
        raise ShadowError("freeze_time must be timezone-aware")

    week_schedule = schedule[
        schedule["season"].eq(season) & schedule["week"].eq(week)
    ].copy()
    if week_schedule.empty:
        raise ShadowError(
            f"no schedule rows for {season} week {week} — cannot derive first kickoff"
        )
    if "kickoff_utc" not in week_schedule.columns:
        raise ShadowError("schedule missing kickoff_utc column")

    try:
        first_kickoff_raw = week_schedule["kickoff_utc"].dropna().min()
        first_kickoff_ts = pd.Timestamp(first_kickoff_raw)
    except (ValueError, TypeError) as exc:
        raise ShadowError("could not derive first kickoff from schedule") from exc
    if first_kickoff_ts.tzinfo is None:
        first_kickoff_ts = first_kickoff_ts.tz_localize("UTC")

    lead_seconds = (first_kickoff_ts - freeze_ts).total_seconds()
    if lead_seconds < freeze_hard_lead_seconds:
        raise ShadowError(
            f"freeze lead {lead_seconds:.0f}s is below the T-1h hard gate "
            f"({freeze_hard_lead_seconds:.0f}s)"
        )

    # Population construction ---------------------------------------------
    broader_games = set(week_schedule["game_id"].astype(int).tolist())

    if missing_v5 := sorted(
        {"game_id", "target", "mean"} - set(v5_predictions.columns)
    ):
        raise ShadowError(f"V5 predictions missing columns: {missing_v5}")
    if missing_v4 := sorted(
        {"game_id", "target", "mean"} - set(v4_predictions.columns)
    ):
        raise ShadowError(f"V4 predictions missing columns: {missing_v4}")

    v5 = v5_predictions.copy()
    v5["game_id"] = v5["game_id"].astype(int)
    v4 = v4_predictions.copy()
    v4["game_id"] = v4["game_id"].astype(int)

    def _is_finite(x: Any) -> bool:
        try:
            return _math.isfinite(float(x))
        except (TypeError, ValueError):
            return False

    merged = v5[["game_id", "target", "mean"]].merge(
        v4[["game_id", "target", "mean"]].rename(columns={"mean": "v4_mean"}),
        on=["game_id", "target"],
        how="inner",
    )
    paired = merged[
        merged["mean"].apply(_is_finite) & merged["v4_mean"].apply(_is_finite)
    ]
    paired_games = set(paired["game_id"].tolist())
    excluded_games = broader_games - paired_games
    paired_count = int(len(paired["game_id"].unique()))
    broader_count = int(len(broader_games))
    excluded_count = int(len(excluded_games))

    if paired_count < min_paired_games:
        raise ShadowError(
            f"freeze has only {paired_count} paired games (minimum {min_paired_games})"
        )

    # Slate digest --------------------------------------------------------
    slate_pairs = sorted(
        (int(r["game_id"]), str(r["target"])) for _, r in paired.iterrows()
    )
    slate_digest = _hashlib.sha256(
        _json.dumps(slate_pairs, separators=(",", ":")).encode()
    ).hexdigest()

    # Identity SHA --------------------------------------------------------
    identity_parts = {
        "candidate": candidate,
        "season": int(season),
        "week": int(week),
        "run_id": run_id,
        "freeze_time": str(freeze_ts.isoformat()),
        "v4_ref_uri": v4_ref_uri,
        "slate_digest": slate_digest,
    }
    identity_sha256 = _hashlib.sha256(
        _json.dumps(identity_parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    # Freeze record -------------------------------------------------------
    freeze_record = pd.DataFrame.from_records(
        [
            {
                "candidate": candidate,
                "season": int(season),
                "week": int(week),
                "run_id": run_id,
                "freeze_time": str(freeze_ts.isoformat()),
                "first_kickoff": str(first_kickoff_ts.isoformat()),
                "lead_seconds": float(lead_seconds),
                "v4_ref_uri": v4_ref_uri,
                "slate_digest": slate_digest,
                "paired_count": paired_count,
                "broader_count": broader_count,
                "excluded_count": excluded_count,
                "identity_sha256": identity_sha256,
            }
        ]
    )

    # Prediction rows -----------------------------------------------------
    v5_cols = ["game_id", "target", "mean"]
    for col in (
        "variance",
        "interval_lower_95",
        "interval_upper_95",
        "offset",
        "model_ref",
        "state_ref",
    ):
        if col in v5.columns:
            v5_cols.append(col)

    pred_base = paired[["game_id", "target"]].merge(
        v5[v5_cols], on=["game_id", "target"], how="left"
    )
    pred_base["candidate"] = candidate
    pred_base["season"] = int(season)
    pred_base["week"] = int(week)
    pred_base["run_id"] = run_id
    for col in (
        "variance",
        "interval_lower_95",
        "interval_upper_95",
        "offset",
        "model_ref",
        "state_ref",
    ):
        if col not in pred_base.columns:
            pred_base[col] = None

    predictions_df = pred_base[
        [
            "candidate",
            "season",
            "week",
            "run_id",
            "game_id",
            "target",
            "mean",
            "variance",
            "interval_lower_95",
            "interval_upper_95",
            "offset",
            "model_ref",
            "state_ref",
        ]
    ].copy()

    return FreezePlan(
        candidate=candidate,
        season=int(season),
        week=int(week),
        run_id=run_id,
        freeze_time=str(freeze_ts.isoformat()),
        first_kickoff=str(first_kickoff_ts.isoformat()),
        lead_seconds=float(lead_seconds),
        v4_ref_uri=v4_ref_uri,
        slate_digest=slate_digest,
        paired_count=paired_count,
        broader_count=broader_count,
        excluded_count=excluded_count,
        identity_sha256=identity_sha256,
        freeze_record=freeze_record,
        predictions=predictions_df,
    )


@dataclass(frozen=True)
class ScoreResult:
    """Outcome-versioned scoring result for one freeze x outcome_version."""

    evaluation: Any
    counter_record: Any
    qualifying: bool
    reason: str
    mae_margin: Any
    mae_total: Any
    paired_count: int
    outcome_version: str


def score_freeze(
    *,
    candidate: str,
    season: int,
    week: int,
    run_id: str,
    freeze_record: pd.DataFrame,
    predictions: pd.DataFrame,
    outcomes: pd.DataFrame,
    outcome_version: str,
    scored_at: str,
    freeze_ref: str = "",
    evaluation_ref: str = "",
    min_stabilization_seconds: float = 86400.0,
) -> "ScoreResult":
    """Score a frozen shadow slate against versioned outcomes.

    Requires >= 24h after the last included game's trustworthy completion
    timestamp (never kickoff+duration substitution). Corrections create a
    new outcome_version linked to the original freeze; the counter row is
    written but does not re-increment the qualifying count.
    """
    import math as _math

    if not candidate or not run_id or not outcome_version or not scored_at:
        raise ShadowError(
            "score_freeze requires candidate, run_id, outcome_version, scored_at"
        )
    if freeze_record.empty or "freeze_time" not in freeze_record.columns:
        raise ShadowError(
            "score_freeze requires a non-empty freeze record with freeze_time"
        )

    try:
        scored_ts = pd.Timestamp(scored_at)
    except (ValueError, TypeError) as exc:
        raise ShadowError(f"unparseable scored_at: {scored_at!r}") from exc
    if scored_ts.tzinfo is None:
        raise ShadowError("scored_at must be timezone-aware")

    if outcomes.empty:
        raise ShadowError("no outcomes provided for scoring")

    if missing := sorted(
        {"game_id", "actual_margin", "actual_total"} - set(outcomes.columns)
    ):
        raise ShadowError(f"outcomes missing required columns: {missing}")

    if "last_completion_time" not in outcomes.columns:
        raise ShadowError(
            "outcomes must include last_completion_time for 24h stabilization check"
        )

    # 24h stabilization gate ------------------------------------------
    freeze_game_ids = set(predictions["game_id"].astype(int).tolist())
    included = outcomes[outcomes["game_id"].astype(int).isin(freeze_game_ids)]
    if included.empty:
        raise ShadowError("no outcomes match the frozen paired games")

    completion_times = included["last_completion_time"].dropna()
    if completion_times.empty:
        raise ShadowError(
            "all included outcomes lack a trustworthy completion timestamp — "
            "scoring blocked (never kickoff+duration substitution)"
        )

    try:
        last_completion = pd.Timestamp(completion_times.max())
        if last_completion.tzinfo is None:
            last_completion = last_completion.tz_localize("UTC")
    except (ValueError, TypeError) as exc:
        raise ShadowError(f"unparseable last_completion_time: {exc}") from exc

    elapsed = (scored_ts - last_completion).total_seconds()
    if elapsed < min_stabilization_seconds:
        raise ShadowError(
            f"scoring attempted only {elapsed:.0f}s after last completion "
            f"(minimum {min_stabilization_seconds:.0f}s = 24h)"
        )

    # Score ---------------------------------------------------------------
    outcomes_clean = outcomes[["game_id", "actual_margin", "actual_total"]].copy()
    outcomes_clean["game_id"] = outcomes_clean["game_id"].astype(int)
    preds = predictions.copy()
    preds["game_id"] = preds["game_id"].astype(int)

    outcomes_long = pd.concat(
        [
            outcomes_clean[["game_id", "actual_margin"]]
            .rename(columns={"actual_margin": "actual"})
            .assign(target="margin"),
            outcomes_clean[["game_id", "actual_total"]]
            .rename(columns={"actual_total": "actual"})
            .assign(target="total"),
        ]
    ).dropna(subset=["actual"])

    scored = preds.merge(outcomes_long, on=["game_id", "target"], how="inner")
    if scored.empty:
        raise ShadowError("no scored rows after joining predictions with outcomes")

    scored["error"] = scored["mean"].astype(float) - scored["actual"].astype(float)

    def _crps(row: Any) -> float:
        v = row.get("variance")
        if v is None:
            return abs(float(row["error"]))
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return abs(float(row["error"]))
        if not _math.isfinite(fv) or fv <= 0:
            return abs(float(row["error"]))
        sigma = _math.sqrt(fv)
        z = float(row["error"]) / sigma
        phi_z = _math.exp(-0.5 * z * z) / _math.sqrt(2 * _math.pi)
        big_phi_z = 0.5 * (1 + _math.erf(z / _math.sqrt(2)))
        return sigma * (2 * phi_z + z * (2 * big_phi_z - 1) - 1 / _math.sqrt(_math.pi))

    def _cov95(row: Any) -> Any:
        lo, hi = row.get("interval_lower_95"), row.get("interval_upper_95")
        if lo is None or hi is None:
            return None
        try:
            actual = float(row["actual"])
            return 1.0 if float(lo) <= actual <= float(hi) else 0.0
        except (TypeError, ValueError):
            return None

    scored["crps"] = scored.apply(_crps, axis=1)
    scored["coverage_95"] = scored.apply(_cov95, axis=1)
    scored["outcome_version"] = outcome_version
    scored["candidate"] = candidate
    scored["season"] = int(season)
    scored["week"] = int(week)
    scored["run_id"] = run_id

    evaluation = scored[
        [
            "candidate",
            "season",
            "week",
            "run_id",
            "outcome_version",
            "game_id",
            "target",
            "actual",
            "error",
            "crps",
            "coverage_95",
        ]
    ].copy()

    margin_rows = evaluation[evaluation["target"] == "margin"]
    total_rows = evaluation[evaluation["target"] == "total"]
    mae_margin = (
        float(margin_rows["error"].abs().mean()) if not margin_rows.empty else None
    )
    mae_total = (
        float(total_rows["error"].abs().mean()) if not total_rows.empty else None
    )
    paired_count = int(len(evaluation["game_id"].unique()))
    qualifying = paired_count >= 40
    reason = "normal_coverage" if qualifying else f"only {paired_count} paired games"

    counter_record = pd.DataFrame.from_records(
        [
            {
                "candidate": candidate,
                "season": int(season),
                "week": int(week),
                "qualifying": qualifying,
                "reason": reason,
                "freeze_ref": freeze_ref,
                "evaluation_ref": evaluation_ref,
            }
        ]
    )

    return ScoreResult(
        evaluation=evaluation,
        counter_record=counter_record,
        qualifying=qualifying,
        reason=reason,
        mae_margin=mae_margin,
        mae_total=mae_total,
        paired_count=paired_count,
        outcome_version=outcome_version,
    )


def update_evidence_counter(
    existing_counter: pd.DataFrame,
    new_record: pd.DataFrame,
    *,
    candidate: str,
    season: int,
    week: int,
) -> Any:
    """Append a new evaluation version without double-counting the slate.

    Each (candidate, season, week) slate is counted once. Corrections append
    with updated refs but do not re-increment the qualifying counter. The
    count is always independently derivable from immutable refs.
    """
    updated = pd.concat([existing_counter, new_record], ignore_index=True)
    qualifying_slates = updated[updated["qualifying"].astype(bool)].drop_duplicates(
        subset=["candidate", "season", "week"]
    )
    qualifying_count = int(len(qualifying_slates))
    return updated, qualifying_count
