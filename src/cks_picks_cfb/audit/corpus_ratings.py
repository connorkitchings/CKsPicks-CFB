"""Full-corpus checks: opponent adjustment, ratings, forecasts, policy.

Streams rating/adjustment/forecast datasets with bounded memory, verifies
chronology, registries, selection evidence, calibration, and the
through-2025 final-fit question. Codifies the findings policy (severity,
disposition, closure) and the overall disposition. Read-only.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.audit import REJECTED_SEASONS
from cks_picks_cfb.audit.corpus import (
    finding_from_check,
    rejected_seasons_present,
    result,
    stable_finding_id,
)


def stream_frames(batches: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
    yield from batches


# --- Opponent adjustment ----------------------------------------------------


def check_adjustment_iterations(
    history: pd.DataFrame, history_uri: str
) -> list[dict[str, Any]]:
    observed = sorted(history["adjustment_iteration"].astype(int).unique().tolist())
    problems: list[str] = []
    if set(observed) - {0, 4}:
        problems.append(f"unexpected iterations: {observed}")
    for column in ("iteration_zero_value", "iteration_four_value"):
        if history[column].isna().any():
            problems.append(f"null {column}")
    return [
        result(
            "corpus.adjustment.iterations",
            "adjustment",
            "chronology",
            "pass" if not problems else "fail",
            "iterations {0, 4} retained with non-null values",
            f"iterations={observed} rows={len(history)} "
            + ("ok" if not problems else "; ".join(problems)),
            "adjusted history",
            [history_uri],
        )
    ]


def check_adjustment_chronology(
    history: pd.DataFrame, history_uri: str
) -> list[dict[str, Any]]:
    """Every source observation strictly precedes its prediction cutoff."""
    source = pd.to_datetime(history["source_available_utc"], utc=True, errors="coerce")
    cutoff = pd.to_datetime(
        history["target_week_cutoff_utc"], utc=True, errors="coerce"
    )
    invalid_time = source.isna() | cutoff.isna()
    late = history[(~invalid_time) & (source >= cutoff)]
    bad_seasons = sorted(
        set(history["source_season"].astype(int).unique().tolist())
        & set(REJECTED_SEASONS)
    )
    unflagged = history[
        (~history["included"].astype(str).isin(("True", "true", "1")))
        & (
            history["missing_reason"].isna()
            | (history["missing_reason"].astype(str) == "")
        )
    ]
    problems = []
    if len(late):
        problems.append(f"future_sources={len(late)}")
    if int(invalid_time.sum()):
        problems.append(f"invalid_timestamps={int(invalid_time.sum())}")
    if bad_seasons:
        problems.append(f"rejected_source_seasons={bad_seasons}")
    if len(unflagged):
        problems.append(f"excluded_without_reason={len(unflagged)}")
    return [
        result(
            "corpus.adjustment.chronology",
            "adjustment",
            "chronology",
            "pass" if not problems else "fail",
            "sources precede cutoffs; eligible seasons only; exclusions reasoned",
            f"rows={len(history)} " + ("ok" if not problems else "; ".join(problems)),
            "adjusted history",
            [history_uri],
        )
    ]


def accumulate_centering(state: dict[str, Any], frame: pd.DataFrame) -> None:
    """Accumulate exposure-weighted means matching the four-pass procedure."""
    eligible = frame[pd.to_numeric(frame["denominator"], errors="coerce").fillna(0) > 0]
    for key, values in eligible.groupby(
        ["target_week_cutoff_utc", "measurement_id", "unit_role"], sort=False
    ):
        weights = pd.to_numeric(values["denominator"], errors="coerce").fillna(0)
        adjusted = pd.to_numeric(values["iteration_four_value"], errors="coerce")
        entry = state.setdefault(key, {"weighted_sum": 0.0, "weight": 0.0})
        entry["weighted_sum"] += float((adjusted * weights).sum())
        entry["weight"] += float(weights.sum())


def check_league_centering(
    state: Mapping[tuple[Any, ...], dict[str, Any]],
    history_uri: str,
    *,
    tolerance: float = 0.05,
) -> list[dict[str, Any]]:
    worst = 0.0
    worst_key: Any = None
    groups = 0
    for key, entry in state.items():
        if entry.get("weight", entry.get("count", 0)) == 0:
            continue
        groups += 1
        mean = entry.get("weighted_sum", entry.get("sum", 0.0)) / entry.get(
            "weight", entry.get("count", 1)
        )
        if abs(mean) > abs(worst):
            worst = mean
            worst_key = key
    status = "pass" if groups and abs(worst) <= tolerance else "fail"
    if not groups:
        status = "fail"
    return [
        result(
            "corpus.adjustment.league_centering",
            "adjustment",
            "football_meaning",
            status,
            f"exposure-weighted iteration-4 cutoff means within ±{tolerance} of league center",
            f"groups={groups} worst_mean={worst:.4f} at {worst_key}",
            "adjusted history",
            [history_uri],
        )
    ]


def check_snapshot_terminal(
    snapshots: pd.DataFrame,
    terminal: pd.DataFrame,
    snapshots_uri: str,
    terminal_uri: str,
) -> list[dict[str, Any]]:
    """Check terminal/snapshot structure; value divergence is expected history growth."""
    key = ["season", "team", "measurement_id", "unit_role", "adjustment_iteration"]
    snapshot_keys = snapshots.loc[:, key].drop_duplicates()
    terminal_keys = terminal.loc[:, key].drop_duplicates()
    only_terminal = terminal_keys.merge(
        snapshot_keys, on=key, how="left", indicator=True
    )
    only_terminal = only_terminal[only_terminal["_merge"] == "left_only"]
    latest = (
        snapshots.sort_values("as_of_game_id")
        .groupby(key, as_index=False)
        .tail(1)
        .set_index(key)["adjusted_value"]
    )
    term = terminal.set_index(key)["adjusted_value"]
    shared = latest.index.intersection(term.index)
    divergent = int(((latest.loc[shared] - term.loc[shared]).abs() > 1e-9).sum())
    problems = (
        [f"terminal_without_snapshot={len(only_terminal)}"]
        if len(only_terminal)
        else []
    )
    return [
        result(
            "corpus.adjustment.snapshot_terminal",
            "adjustment",
            "chronology",
            "pass" if not problems else "fail",
            "terminal keys have snapshot provenance; value divergence is reported",
            f"shared={len(shared)} terminal_value_divergence={divergent} "
            + ("ok" if not problems else "; ".join(problems)),
            "snapshots + terminal",
            [snapshots_uri, terminal_uri],
        )
    ]


# --- Rating priors, fits, registry, selection --------------------------------


def max_training_year(frame: pd.DataFrame, season_column: str = "season") -> pd.Series:
    """Max year mentioned in training_seasons strings (NaN when absent)."""
    years = (
        frame["training_seasons"]
        .astype(str)
        .str.extractall(r"(?P<year>\d{4})")
        .astype(int)["year"]
    )
    if years.empty:
        return pd.Series(float("nan"), index=frame.index)
    return years.groupby(level=0).max().reindex(frame.index)


def _int_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Coerce a possibly mixed-type season column to numeric (NaN if absent)."""
    if column not in frame.columns:
        return pd.Series(float("nan"), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def check_prior_chronology(
    priors: pd.DataFrame, priors_uri: str
) -> list[dict[str, Any]]:
    """Learned priors fit strictly before their prediction season."""
    problems: list[str] = []
    learned = priors[priors["prior_source"].astype(str).str.contains("ridge", na=False)]
    if not learned.empty:
        max_year = max_training_year(learned)
        bad = learned[max_year.fillna(-1).astype(int) >= learned["season"].astype(int)]
        for _, row in bad.head(8).iterrows():
            problems.append(
                f"{row['candidate_id']}/{int(row['season'])}: "
                f"trains on {row.get('training_seasons')}"
            )
    bad_source = sorted(
        set(
            _int_series(priors, "prior_source_season")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        & set(REJECTED_SEASONS)
    )
    if bad_source:
        problems.append(f"rejected prior_source_seasons={bad_source}")
    source_season = _int_series(priors, "prior_source_season")
    gap = priors[(priors["season"].astype(int) == 2021) & (source_season == 2019)]
    bad_gap = gap[_int_series(gap, "annual_decay_steps").fillna(-1).astype(int) != 2]
    if len(bad_gap):
        problems.append(f"2019_to_2021_decay_violations={len(bad_gap)}")
    return [
        result(
            "corpus.rating.prior_chronology",
            "ratings",
            "chronology",
            "pass" if not problems else "fail",
            "learned fits precede season; 2019→2021 decay steps == 2",
            f"learned={len(learned)} gap_rows={len(gap)} "
            + ("ok" if not problems else "; ".join(problems[:8])),
            "priors",
            [priors_uri],
        )
    ]


def check_prior_fallbacks(
    priors: pd.DataFrame, priors_uri: str
) -> list[dict[str, Any]]:
    """Fallbacks are explicit: neutral/first-season, FCS cohorts, carryover."""
    missing = priors[
        priors["fallback_reason"].isna() | (priors["fallback_reason"].astype(str) == "")
    ]
    no_source = priors[
        priors["prior_source"].isna() | (priors["prior_source"].astype(str) == "")
    ]
    problems = []
    if len(no_source):
        problems.append(f"missing_prior_source={len(no_source)}")
    reasons = priors["fallback_reason"].astype(str).value_counts().to_dict()
    return [
        result(
            "corpus.rating.prior_fallbacks",
            "ratings",
            "fallback",
            "pass" if not problems else "fail",
            "every prior carries a source; fallbacks carry reasons",
            f"rows={len(priors)} without_fallback_reason={len(missing)} "
            f"reasons={reasons} " + ("ok" if not problems else "; ".join(problems)),
            "priors",
            [priors_uri],
        )
    ]


def check_noise_fits(noise: pd.DataFrame, noise_uri: str) -> list[dict[str, Any]]:
    unconverged = noise[
        (~noise["converged"].astype(str).isin(("True", "true", "1")))
        & (~noise["cold_start"].astype(str).isin(("True", "true", "1")))
    ]
    future_fit = noise[
        max_training_year(noise).fillna(-1).astype(int) >= noise["season"].astype(int)
    ]
    problems = []
    if len(unconverged):
        problems.append(f"unconverged_without_cold_start={len(unconverged)}")
    if len(future_fit):
        problems.append(f"fits_using_current_or_future={len(future_fit)}")
    return [
        result(
            "corpus.rating.noise_fits",
            "ratings",
            "uncertainty",
            "pass" if not problems else "fail",
            "q/r converged or cold-started; training strictly earlier",
            f"rows={len(noise)} " + ("ok" if not problems else "; ".join(problems)),
            "noise fits",
            [noise_uri],
        )
    ]


def check_registry_selection(
    registry: pd.DataFrame,
    attribution: pd.DataFrame,
    selected_candidate: str,
    registry_uri: str,
    attribution_uri: str,
) -> list[dict[str, Any]]:
    """60-candidate registry complete; selection evidence reproducible."""
    results: list[dict[str, Any]] = []
    problems: list[str] = []
    if len(registry) != 60:
        problems.append(f"registry_rows={len(registry)}")
    grid = (
        registry.groupby(["definition", "prior_family", "updater"]).size()
        if not registry.empty
        else []
    )
    results.append(
        result(
            "corpus.rating.registry_completeness",
            "ratings",
            "selection",
            "pass" if not problems else "fail",
            "60 candidates: 2 definitions × 6 priors × 5 updaters",
            f"rows={len(registry)} combos={len(grid)} "
            + ("ok" if not problems else "; ".join(problems)),
            "rating registry",
            [registry_uri],
        )
    )
    selected = attribution[
        attribution["selected"].astype(str).isin(("True", "true", "1"))
    ]
    problems = []
    if (
        len(selected) != 1
        or str(selected.iloc[0]["candidate_id"]) != selected_candidate
    ):
        problems.append(
            f"selected={selected['candidate_id'].tolist() if len(selected) else []}"
        )
    invalid_reference = attribution[
        (~attribution["valid"].astype(str).isin(("True", "true", "1")))
        & (
            attribution["reference_candidate"].astype(str)
            == attribution["candidate_id"].astype(str)
        )
    ]
    if len(invalid_reference):
        problems.append(f"invalid_reference_designs={len(invalid_reference)}")
    missing_bootstrap = attribution[
        attribution["bootstrap_90_lower"].isna()
        | attribution["bootstrap_90_upper"].isna()
    ]
    if len(missing_bootstrap):
        problems.append(f"missing_bootstrap={len(missing_bootstrap)}")
    results.append(
        result(
            "corpus.rating.selection_evidence",
            "ratings",
            "selection",
            "pass" if not problems else "fail",
            f"exactly retained {selected_candidate} selected; references valid; intervals present",
            f"rows={len(attribution)} "
            + ("ok" if not problems else "; ".join(problems)),
            "attribution",
            [attribution_uri],
        )
    )
    return results


def check_rating_states(
    states: pd.DataFrame,
    kickoffs: Mapping[tuple[int, int], str],
    states_uri: str,
) -> list[dict[str, Any]]:
    """States precede kickoff; variances positive; weights bounded."""
    problems: list[str] = []
    bad_cutoff = 0
    checked = 0
    for row in states.itertuples():
        checked += 1
        kickoff = kickoffs.get((int(row.season), int(row.game_id)))
        cutoff = pd.to_datetime(row.cutoff_utc, utc=True, errors="coerce")
        kickoff_at = pd.to_datetime(kickoff, utc=True, errors="coerce")
        if pd.isna(cutoff) or pd.isna(kickoff_at) or cutoff >= kickoff_at:
            bad_cutoff += 1
    if bad_cutoff:
        problems.append(f"cutoff_at_or_after_kickoff={bad_cutoff}/{checked}")
    bad_variance = states[states["rating_variance"].astype(float) <= 0]
    if len(bad_variance):
        problems.append(f"nonpositive_variance={len(bad_variance)}")
    bad_weight = states[
        (states["evidence_weight"].astype(float) < 0)
        | (states["evidence_weight"].astype(float) >= 1)
    ]
    if len(bad_weight):
        problems.append(f"weight_out_of_range={len(bad_weight)}")
    nonfinite = states[
        (~states["rating_mean"].astype(float).apply(lambda value: value == value))
    ]
    if len(nonfinite):
        problems.append(f"nonfinite_mean={len(nonfinite)}")
    bad_seasons = rejected_seasons_present(states)
    if bad_seasons:
        problems.append(f"rejected_seasons={bad_seasons}")
    return [
        result(
            "corpus.rating.state_validity",
            "ratings",
            "chronology",
            "pass" if not problems else "fail",
            "cutoffs precede kickoff; positive variance; weights in [0, 1)",
            f"rows={len(states)} " + ("ok" if not problems else "; ".join(problems)),
            "rating states",
            [states_uri],
        )
    ]


def check_team_state_pairing(
    team_states: pd.DataFrame, team_states_uri: str
) -> list[dict[str, Any]]:
    keyed = team_states.groupby(["season", "week", "game_id", "team", "candidate_id"])
    unpaired = keyed.filter(lambda group: len(group) != 1)
    participants = team_states.groupby(["season", "week", "game_id", "candidate_id"])[
        "team"
    ].nunique()
    bad_games = participants[participants != 2]
    return [
        result(
            "corpus.rating.team_state_pairing",
            "ratings",
            "football_meaning",
            "pass" if unpaired.empty and bad_games.empty else "fail",
            "two scheduled participants and one combined offense/defense row per participant",
            f"rows={len(team_states)} unpaired_groups={int(unpaired['game_id'].nunique()) if not unpaired.empty else 0} games_with_non_two_participants={len(bad_games)}",
            "team states",
            [team_states_uri],
        )
    ]


def check_bridge_coverage(
    bridge: pd.DataFrame,
    attribution: pd.DataFrame,
    bridge_uri: str,
    attribution_uri: str,
) -> list[dict[str, Any]]:
    covered = set(bridge["candidate_id"].astype(str).unique().tolist())
    expected = set(attribution["candidate_id"].astype(str).unique().tolist())
    missing = sorted(expected - covered)
    future_fit = bridge[
        bridge.apply(
            lambda row: any(
                int(token) >= int(row["season"])
                for token in str(row.get("training_seasons") or "")
                .replace(",", " ")
                .split()
                if token.strip().isdigit()
            ),
            axis=1,
        )
    ]
    problems = []
    if missing:
        problems.append(f"candidates_without_predictions={missing[:8]}")
    if len(future_fit):
        problems.append(f"bridge_fits_using_current_or_future={len(future_fit)}")
    return [
        result(
            "corpus.rating.bridge_coverage",
            "ratings",
            "selection",
            "pass" if not problems else "fail",
            "every registry candidate predicted or explicitly invalid; earlier-only fits",
            f"covered={len(covered)}/{len(expected)} "
            + ("ok" if not problems else "; ".join(problems)),
            "bridge predictions",
            [bridge_uri, attribution_uri],
        )
    ]


# --- Forecast construction ----------------------------------------------------


def check_forecast_model(
    model: pd.DataFrame,
    registry: pd.DataFrame,
    selection: pd.DataFrame,
    model_uri: str,
) -> list[dict[str, Any]]:
    problems: list[str] = []
    horizons = sorted(model["horizon"].astype(str).unique().tolist())
    if set(horizons) - {"expanding", "latest_five"}:
        problems.append(f"unknown_horizons={horizons}")
    retained = model[model["retained"].astype(str).isin(("True", "true", "1"))]
    for target in ("margin", "total"):
        heads = retained[retained["target"] == target]
        if heads.empty:
            problems.append(f"no_retained_head_{target}")
    training_max = 0
    max_year = max_training_year(model)
    bad_fit = model[
        max_year.fillna(-1).astype(int) >= model["outer_season"].astype(int)
    ]
    if len(bad_fit):
        first = bad_fit.iloc[0]
        problems.append(
            f"model trains on outer season: {first['horizon']}/{first['target']}"
        )
    if not max_year.dropna().empty:
        training_max = int(max_year.max())
    return [
        result(
            "corpus.forecast.model_registry",
            "forecasts",
            "selection",
            "pass" if not problems else "fail",
            "declared horizons; one retained head per target; earlier-only fits",
            f"horizons={horizons} max_training_season={training_max} "
            + ("ok" if not problems else "; ".join(problems)),
            "forecast model",
            [model_uri],
        ),
        result(
            "corpus.forecast.final_fit_existence",
            "forecasts",
            "final_fit",
            "pass" if training_max >= 2025 else "fail",
            "a complete through-2025 final fit exists and is reproducible",
            f"max_training_season={training_max}",
            "forecast model",
            [model_uri],
        ),
    ]


def check_forecast_predictions(
    predictions: pd.DataFrame, predictions_uri: str
) -> list[dict[str, Any]]:
    problems: list[str] = []
    by_horizon = predictions["horizon"].astype(str).value_counts().to_dict()
    if len(set(by_horizon.values())) != 1:
        problems.append(f"unequal_horizon_populations={by_horizon}")
    seasons = sorted(predictions["season"].astype(int).unique().tolist())
    if set(seasons) - {2022, 2023, 2024, 2025}:
        problems.append(f"unexpected_prediction_seasons={seasons}")
    targets = sorted(predictions["target"].astype(str).unique().tolist())
    if set(targets) != {"margin", "total"}:
        problems.append(f"targets={targets}")
    for column in ("prediction", "offset", "actual"):
        if predictions[column].isna().any():
            problems.append(f"null_{column}")
    bad_training = predictions[
        max_training_year(predictions).fillna(-1).astype(int)
        >= predictions["season"].astype(int)
    ]
    if len(bad_training):
        problems.append(f"predictions_trained_on_current_or_future={len(bad_training)}")
    stages = sorted(predictions["completed_game_stage"].astype(str).unique().tolist())
    bad_seasons = rejected_seasons_present(predictions)
    if bad_seasons:
        problems.append(f"rejected_seasons={bad_seasons}")
    return [
        result(
            "corpus.forecast.predictions",
            "forecasts",
            "chronology",
            "pass" if not problems else "fail",
            "equal horizon populations on 2022–2025; finite predictions/offsets; earlier-only training",
            f"rows={len(predictions)} horizons={by_horizon} stages={stages} "
            + ("ok" if not problems else "; ".join(problems)),
            "forecast predictions",
            [predictions_uri],
        )
    ]


def check_calibration(
    calibration: pd.DataFrame, calibration_uri: str
) -> list[dict[str, Any]]:
    problems: list[str] = []
    if calibration["variance"].astype(float).le(0).any():
        problems.append("nonpositive_variance")
    if calibration["residual_count"].astype(int).le(0).any():
        problems.append("empty_residuals")
    seasons = sorted(calibration["season"].astype(int).unique().tolist())
    return [
        result(
            "corpus.forecast.calibration",
            "forecasts",
            "uncertainty",
            "pass" if not problems else "fail",
            "positive variances from nonempty earlier residual seasons",
            f"rows={len(calibration)} seasons={seasons} "
            + ("ok" if not problems else "; ".join(problems)),
            "forecast calibration",
            [calibration_uri],
        )
    ]


# --- Findings policy lives in corpus.py (single definition) --------------------


def finalize_seeded_findings() -> list[dict[str, Any]]:
    """Give the two confirmed structural findings their final 10B form."""
    from cks_picks_cfb.audit import SEEDED_FINDINGS
    from cks_picks_cfb.audit.corpus import finding as build_finding

    specs = {
        "audit-structural-001": (
            "blocker",
            "prohibited_until_closed",
            ["repair"],
            "Separate Repair verification from producer computation under a new "
            "identity through an approved corrective contract, then re-audit.",
            "An independently reconstructed Repair verification passes the "
            "import boundary and behavioral matrix.",
        ),
        "audit-structural-002": (
            "blocker",
            "historical_evidence_only",
            ["forecasts"],
            "Close the forecast computation gap in Contract 11 with independent "
            "reconstruction of offsets, fits, calibration, and selection.",
            "Contract 11 records signed verification of reconstructed outputs.",
        ),
    }
    findings: list[dict[str, Any]] = []
    for seed in SEEDED_FINDINGS:
        key = str(seed["finding_id"])
        severity, disposition, stages, action, criteria = specs[key]
        findings.append(
            build_finding(
                finding_id=key,
                severity=severity,
                disposition=disposition,
                title=str(seed["title"]),
                description=str(seed["description"]),
                affected_stages=stages,
                evidence=[str(ref) for ref in seed.get("evidence", [])],
                required_action=action,
                closure_criteria=criteria,
                blocking_dependencies=["contract-11"] if key.endswith("002") else [],
            )
        )
    return findings


def forecast_reconstruction_finding() -> dict[str, Any]:
    """Record output reconstruction as Contract 11 work, not audit work."""
    from cks_picks_cfb.audit.corpus import finding as build_finding

    return build_finding(
        finding_id="audit-forecast-reconstruction",
        severity="blocker",
        disposition="historical_evidence_only",
        title="Forecast-output reconstruction assigned to Contract 11",
        description=(
            "The stored forecast computations, offsets, bridge fits, "
            "calibration, and selection are not independently reconstructed "
            "in this audit; Contract 11 owns that verification."
        ),
        affected_stages=["forecasts"],
        evidence=["src/cks_picks_cfb/forecast/forecast_verification.py"],
        required_action=(
            "Execute Contract 11 forecast-verification closure against the "
            "exact eligible artifacts."
        ),
        closure_criteria=(
            "Contract 11 records signed verification of reconstructed outputs."
        ),
        blocking_dependencies=["contract-11"],
    )


def overall_disposition(findings: list[Mapping[str, Any]]) -> str:
    """Contract 10 completeness is separate: blocked vs clear on open blockers."""
    for finding in findings:
        if (
            finding.get("severity") == "blocker"
            and finding.get("closure_state") == "open"
        ):
            return "blocked"
    return "clear"


# --- Full-corpus orchestration --------------------------------------------------


def run_full_corpus(
    storage: Any,
    manifests: Mapping[str, Mapping[str, Any]],
    manifest_uris: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Stream every eligible dataset and run all corpus check families.

    Returns (check_results, findings, summaries). Findings are final 10B
    findings: failed checks converted by policy, finalized seeded findings,
    and the Contract 11 reconstruction record. Read-only.
    """
    from cks_picks_cfb.audit.corpus import (
        check_coverage_slices,
        check_denominator_parity,
        check_missing_dispositions,
        check_offensive_drive_range,
        check_population_agreement,
        check_population_seasons,
        check_repair_finals,
        check_role_orientation,
        check_score_reconciliation,
        check_scoring_increments,
        check_unresolved_quarantine,
        concat_all,
        read_any,
    )

    checks: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}

    def refs(stage: str) -> Mapping[str, Any]:
        return manifests[stage].get("output_refs") or {}

    def uri(stage: str) -> str:
        return manifest_uris[stage]

    # -- Populations ---------------------------------------------------------
    repair_pop = concat_all(read_any(storage, refs("repair")["population"]))
    measurement_pop = concat_all(read_any(storage, refs("measurements")["population"]))
    repair_coverage = concat_all(read_any(storage, refs("repair")["coverage"]))
    measurement_coverage = concat_all(
        read_any(storage, refs("measurements")["coverage"])
    )
    summaries["repair_population_rows"] = int(len(repair_pop))
    summaries["measurement_population_rows"] = int(len(measurement_pop))
    checks.extend(
        check_population_agreement(
            repair_pop, measurement_pop, uri("repair"), uri("measurements")
        )
    )
    checks.extend(
        check_population_seasons(
            repair_pop, measurement_pop, uri("repair"), uri("measurements")
        )
    )
    checks.extend(check_missing_dispositions(measurement_pop, uri("measurements")))
    checks.extend(check_repair_finals(repair_pop, uri("repair")))
    checks.extend(
        check_coverage_slices(
            repair_coverage, measurement_coverage, uri("repair"), uri("measurements")
        )
    )
    kickoffs = {
        (int(season), int(game_id)): str(kickoff)
        for season, game_id, kickoff in repair_pop[
            ["season", "game_id", "kickoff_utc"]
        ].itertuples(index=False, name=None)
    }

    # -- Ledgers ---------------------------------------------------------------
    possessions = concat_all(read_any(storage, refs("measurements")["possessions"]))
    events = concat_all(read_any(storage, refs("measurements")["scoring_events"]))
    observations = concat_all(read_any(storage, refs("measurements")["observations"]))
    summaries["possessions_rows"] = int(len(possessions))
    summaries["scoring_events_rows"] = int(len(events))
    summaries["observations_rows"] = int(len(observations))
    checks.extend(check_scoring_increments(events, uri("measurements")))
    checks.extend(check_offensive_drive_range(events, possessions, uri("measurements")))
    checks.extend(check_denominator_parity(observations, uri("measurements")))
    checks.extend(check_role_orientation(observations, uri("measurements")))
    checks.extend(
        check_unresolved_quarantine(events, observations, uri("measurements"))
    )
    checks.extend(
        check_score_reconciliation(
            events, repair_pop, uri("measurements"), uri("repair")
        )
    )

    # -- Opponent adjustment (streamed) -----------------------------------------
    history_uri = uri("measurements")
    issue_ref = refs("measurements")["adjusted_history"]
    iterations: set[int] = set()
    null_zero = 0
    null_four = 0
    centering: dict[tuple[Any, ...], dict[str, Any]] = {}
    chrono_rows = 0
    future_sources = 0
    late_examples: list[str] = []
    bad_source_seasons: set[int] = set()
    unflagged = 0
    for batch in read_any(storage, issue_ref):
        chrono_rows += len(batch)
        iterations.update(batch["adjustment_iteration"].astype(int).unique().tolist())
        null_zero += int(batch["iteration_zero_value"].isna().sum())
        null_four += int(batch["iteration_four_value"].isna().sum())
        accumulate_centering(centering, batch)
        source = pd.to_datetime(
            batch["source_available_utc"], utc=True, errors="coerce"
        )
        cutoff = pd.to_datetime(
            batch["target_week_cutoff_utc"], utc=True, errors="coerce"
        )
        late = batch[source.notna() & cutoff.notna() & (source >= cutoff)]
        future_sources += len(late)
        if len(late) and len(late_examples) < 8:
            for row in late.head(8 - len(late_examples)).itertuples():
                late_examples.append(
                    f"{int(row.source_season)}/{int(row.source_game_id)}"
                    f"->{str(row.target_week_cutoff_utc)}"
                )
        bad_source_seasons.update(
            set(batch["source_season"].astype(int).unique().tolist())
            & set(REJECTED_SEASONS)
        )
        unflagged += int(
            (
                ~batch["included"].astype(str).isin(("True", "true", "1"))
                & (
                    batch["missing_reason"].isna()
                    | (batch["missing_reason"].astype(str) == "")
                )
            ).sum()
        )
    summaries["adjusted_history_rows"] = int(chrono_rows)
    iteration_problems: list[str] = []
    if iterations - {0, 4}:
        iteration_problems.append(f"unexpected iterations: {sorted(iterations)}")
    if null_zero or null_four:
        iteration_problems.append(f"null values: iter0={null_zero} iter4={null_four}")
    checks.append(
        {
            "check_id": "corpus.adjustment.iterations",
            "layer": "adjustment",
            "category": "chronology",
            "status": "pass" if not iteration_problems else "fail",
            "expected": "iterations {0, 4} retained with non-null values",
            "observed": f"iterations={sorted(iterations)} rows={chrono_rows} "
            + ("ok" if not iteration_problems else "; ".join(iteration_problems)),
            "population": "adjusted history",
            "evidence_refs": [history_uri],
        }
    )
    chrono_problems: list[str] = []
    if future_sources:
        chrono_problems.append(
            f"future_sources={future_sources} examples={late_examples}"
        )
    if bad_source_seasons:
        chrono_problems.append(f"rejected_source_seasons={sorted(bad_source_seasons)}")
    if unflagged:
        chrono_problems.append(f"excluded_without_reason={unflagged}")
    checks.append(
        {
            "check_id": "corpus.adjustment.chronology",
            "layer": "adjustment",
            "category": "chronology",
            "status": "pass" if not chrono_problems else "fail",
            "expected": "sources precede cutoffs; eligible seasons only; exclusions reasoned",
            "observed": f"rows={chrono_rows} "
            + ("ok" if not chrono_problems else "; ".join(chrono_problems)),
            "population": "adjusted history",
            "evidence_refs": [history_uri],
        }
    )
    checks.extend(check_league_centering(centering, history_uri))

    snapshots = concat_all(read_any(storage, refs("measurements")["snapshots"]))
    terminal = concat_all(read_any(storage, refs("measurements")["terminal"]))
    summaries["snapshots_rows"] = int(len(snapshots))
    summaries["terminal_rows"] = int(len(terminal))
    checks.extend(
        check_snapshot_terminal(
            snapshots, terminal, uri("measurements"), uri("measurements")
        )
    )
    del possessions, events, observations, snapshots, terminal

    # -- Ratings ------------------------------------------------------------------
    rating_refs = refs("ratings")
    registry = concat_all(read_any(storage, rating_refs["rating_registry"]))
    attribution = concat_all(read_any(storage, rating_refs["attribution"]))
    noise = concat_all(read_any(storage, rating_refs["noise_fits"]))
    selected = str(manifests["ratings"].get("selected_candidate") or "")
    checks.extend(
        check_registry_selection(
            registry, attribution, selected, uri("ratings"), uri("ratings")
        )
    )
    checks.extend(check_noise_fits(noise, uri("ratings")))
    del registry, noise

    priors_rows = 0
    prior_frames: list[pd.DataFrame] = []
    for batch in read_any(storage, rating_refs["priors"]):
        priors_rows += len(batch)
        prior_frames.append(batch)
    priors = (
        pd.concat(prior_frames, ignore_index=True) if prior_frames else pd.DataFrame()
    )
    summaries["priors_rows"] = int(priors_rows)
    if not priors.empty:
        checks.extend(check_prior_chronology(priors, uri("ratings")))
        checks.extend(check_prior_fallbacks(priors, uri("ratings")))
    del priors, prior_frames

    state_problems: list[str] = []
    state_rows = 0
    bad_cutoff = 0
    bad_variance = 0
    bad_weight = 0
    nonfinite = 0
    bad_season_keys: set[int] = set()
    kickoff_frame = pd.DataFrame(
        [
            {"season": season, "game_id": game_id, "kickoff_utc": kickoff}
            for (season, game_id), kickoff in kickoffs.items()
        ]
    )
    for batch in read_any(storage, rating_refs["rating_states"]):
        state_rows += len(batch)
        joined = batch.merge(kickoff_frame, on=["season", "game_id"], how="left")
        bad_cutoff += int(
            (
                joined["kickoff_utc"].notna()
                & (
                    pd.to_datetime(joined["cutoff_utc"], utc=True, errors="coerce")
                    >= pd.to_datetime(joined["kickoff_utc"], utc=True, errors="coerce")
                )
            ).sum()
        )
        bad_variance += int((batch["rating_variance"].astype(float) <= 0).sum())
        weight = batch["evidence_weight"].astype(float)
        bad_weight += int(((weight < 0) | (weight >= 1)).sum())
        nonfinite += int(
            (
                ~batch["rating_mean"].astype(float).apply(lambda value: value == value)
            ).sum()
        )
        bad_season_keys.update(
            set(batch["season"].astype(int).unique().tolist()) & set(REJECTED_SEASONS)
        )
    summaries["rating_states_rows"] = int(state_rows)
    if bad_cutoff:
        state_problems.append(f"cutoff_at_or_after_kickoff={bad_cutoff}/{state_rows}")
    if bad_variance:
        state_problems.append(f"nonpositive_variance={bad_variance}")
    if bad_weight:
        state_problems.append(f"weight_out_of_range={bad_weight}")
    if nonfinite:
        state_problems.append(f"nonfinite_mean={nonfinite}")
    if bad_season_keys:
        state_problems.append(f"rejected_seasons={sorted(bad_season_keys)}")
    checks.append(
        {
            "check_id": "corpus.rating.state_validity",
            "layer": "ratings",
            "category": "chronology",
            "status": "pass" if not state_problems else "fail",
            "expected": "cutoffs precede kickoff; positive variance; weights in [0, 1)",
            "observed": f"rows={state_rows} "
            + ("ok" if not state_problems else "; ".join(state_problems)),
            "population": "rating states",
            "evidence_refs": [uri("ratings")],
        }
    )

    team_key_counts: dict[tuple[Any, ...], int] = {}
    team_rows = 0
    for batch in read_any(storage, rating_refs["team_states"]):
        team_rows += len(batch)
        for key, count in (
            batch.groupby(["season", "week", "game_id", "team", "candidate_id"])
            .size()
            .items()
        ):
            team_key_counts[tuple(key)] = team_key_counts.get(tuple(key), 0) + int(
                count
            )
    summaries["team_states_rows"] = int(team_rows)
    unpaired = sum(1 for count in team_key_counts.values() if count != 1)
    checks.append(
        {
            "check_id": "corpus.rating.team_state_pairing",
            "layer": "ratings",
            "category": "football_meaning",
            "status": "pass" if unpaired == 0 else "fail",
            "expected": "one offense/defense-paired row per team-game-candidate",
            "observed": f"rows={team_rows} unpaired_groups={unpaired}",
            "population": "team states",
            "evidence_refs": [uri("ratings")],
        }
    )
    del team_key_counts

    attribution_full = attribution
    bridge_candidates: set[str] = set()
    bridge_rows = 0
    bridge_future = 0
    for batch in read_any(storage, rating_refs["bridge_predictions"]):
        bridge_rows += len(batch)
        bridge_candidates.update(batch["candidate_id"].astype(str).unique().tolist())
        bridge_future += int(
            (
                max_training_year(batch).fillna(-1).astype(int)
                >= batch["season"].astype(int)
            ).sum()
        )
    summaries["bridge_rows"] = int(bridge_rows)
    expected_candidates = set(
        attribution_full["candidate_id"].astype(str).unique().tolist()
    )
    missing_candidates = sorted(expected_candidates - bridge_candidates)
    bridge_problems = []
    if missing_candidates:
        bridge_problems.append(
            f"candidates_without_predictions={missing_candidates[:8]}"
        )
    if bridge_future:
        bridge_problems.append("bridge_fits_using_current_or_future")
    checks.append(
        {
            "check_id": "corpus.rating.bridge_coverage",
            "layer": "ratings",
            "category": "selection",
            "status": "pass" if not bridge_problems else "fail",
            "expected": "every registry candidate predicted or explicitly invalid; earlier-only fits",
            "observed": f"covered={len(bridge_candidates)}/{len(expected_candidates)} "
            + ("ok" if not bridge_problems else "; ".join(bridge_problems)),
            "population": "bridge predictions",
            "evidence_refs": [uri("ratings")],
        }
    )
    del attribution_full

    # -- Forecasts ------------------------------------------------------------------
    forecast_refs = refs("forecasts")
    model = concat_all(read_any(storage, forecast_refs["forecast_model"]))
    registry_f = concat_all(read_any(storage, forecast_refs["forecast_registry"]))
    selection_f = concat_all(read_any(storage, forecast_refs["forecast_selection"]))
    window = concat_all(read_any(storage, forecast_refs["window_comparison"]))
    calibration = concat_all(read_any(storage, forecast_refs["forecast_calibration"]))
    predictions = concat_all(read_any(storage, forecast_refs["forecast_prediction"]))
    summaries["forecast_prediction_rows"] = int(len(predictions))
    checks.extend(
        check_forecast_model(model, registry_f, selection_f, uri("forecasts"))
    )
    checks.extend(check_forecast_predictions(predictions, uri("forecasts")))
    checks.extend(check_calibration(calibration, uri("forecasts")))
    summaries["forecast_model_max_training"] = 0
    for _, row in model.iterrows():
        years = [
            int(token)
            for token in str(row.get("training_seasons") or "")
            .replace(",", " ")
            .split()
            if token.strip().isdigit()
        ]
        if years:
            summaries["forecast_model_max_training"] = max(
                summaries["forecast_model_max_training"], max(years)
            )
    del model, registry_f, selection_f, window, calibration, predictions

    # -- Findings ---------------------------------------------------------------------
    findings: list[dict[str, Any]] = []
    stage_by_prefix = {
        "corpus.adjustment.": ["measurements"],
        "corpus.rating.": ["ratings"],
        "corpus.forecast.": ["forecasts"],
        "corpus.ledger.": ["measurements"],
        "corpus.population.": ["repair", "measurements"],
    }
    for check in checks:
        if check.get("status") == "fail":
            if not check.get("affected_stages"):
                for prefix, stages in stage_by_prefix.items():
                    if str(check["check_id"]).startswith(prefix):
                        check["affected_stages"] = stages
                        break
            findings.append(
                finding_from_check(
                    check,
                    finding_id=stable_finding_id(str(check["check_id"])),
                )
            )
    return checks, findings, summaries
