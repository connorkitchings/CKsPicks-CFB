"""Stage: attribution of the corrected lineage to its individual inputs.

Five arms over the same population and design, changing one input at a time (contract 02,
Amendment 8). Baseline is the served r9 / r9cert lineage, read directly; combined is the
published output; the other arms are recomputed with the unchanged measurement, rating,
offset and refit code. The EPA-only arm must reproduce baseline exactly (the selected design
uses PPP only); anything else stops the run.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import attribution_math as am
from cks_picks_cfb.rebuild import measurements, parity
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun

PREFIX = "rebuild/6a/{run_id}/attribution/"
ARMS = ("baseline", "epa_only", "scoring_only", "offset_only", "combined")
SELECTED = "ppp__rho_0_60__exposure"
IDENTITY_FRAMES = (
    "priors",
    "rating_states",
    "team_states",
    "offsets",
    "features",
    "forecasts",
)


@dataclass
class Arm:
    name: str
    priors: pd.DataFrame
    rating_states: pd.DataFrame
    team_states: pd.DataFrame
    offsets: pd.DataFrame
    team_games: pd.DataFrame
    features: pd.DataFrame
    bundle: dict[str, Any]
    forecasts: pd.DataFrame
    observations: pd.DataFrame | None = None
    terminal: pd.DataFrame | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def measure(population, byplay, outcomes, possessions, events):
    """Observations, iteration-four terminal and the selected-design states for one arm."""
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings.possession_selected_design import compute_selected_design

    result = pm.build_measurements(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        possessions=possessions,
        scoring_events=events,
    )
    snapshots: list[pd.DataFrame] = []
    terminal: list[pd.DataFrame] = []

    def emit(name: str, partition: dict[str, Any], frame: pd.DataFrame) -> None:
        if name == "snapshots":
            snapshots.append(frame.copy())
        elif name == "terminal":
            terminal.append(frame.copy())

    pm.replay_partitions(
        population=population, observations=result.observations, emit=emit
    )
    snapshot_frame = pd.concat(snapshots, ignore_index=True)
    terminal_frame = pd.concat(terminal, ignore_index=True)
    design = compute_selected_design(
        population=population,
        observations=result.observations,
        snapshots=snapshot_frame,
        terminal=terminal_frame,
    )
    return result.observations, terminal_frame, design


def finish_arm(
    name: str,
    *,
    population,
    outcomes,
    states: Mapping[str, pd.DataFrame],
    offsets,
    team_games,
    observations=None,
    terminal=None,
) -> Arm:
    from cks_picks_cfb.forecast.historical_features import _feature_frame
    from cks_picks_cfb.forecast.intended_update_bundle import (
        assert_pre2026_frame,
        fit_bundle_from_frame,
    )

    features = _feature_frame(
        population=population,
        outcomes=outcomes,
        team_states=states["team_states"],
        offsets=offsets,
    )
    assert_pre2026_frame(features)
    bundle, _ = fit_bundle_from_frame(features)
    return Arm(
        name=name,
        priors=states["priors"],
        rating_states=states["rating_states"],
        team_states=states["team_states"],
        offsets=offsets,
        team_games=team_games,
        features=features,
        bundle=bundle,
        forecasts=am.predict(bundle, features),
        observations=observations,
        terminal=terminal,
    )


def frame_digests(frames: Mapping[str, Any]) -> dict[str, str]:
    """Canonical record hashes of one arm's frames and its bundle."""
    digests = {name: am.canonical_digest(frames[name]) for name in IDENTITY_FRAMES}
    digests["bundle"] = am.json_sha(frames["bundle"])
    return digests


def arm_digests(arm: Arm) -> dict[str, str]:
    return frame_digests(
        {**{n: getattr(arm, n) for n in IDENTITY_FRAMES}, "bundle": arm.bundle}
    )


def season_changes(base, other, keys, column) -> dict[str, int]:
    columns = list(
        dict.fromkeys([*keys, "season", column])
    )  # season may be a key already
    merged = base[columns].merge(
        other[[*keys, column]], on=list(keys), suffixes=("_b", "_o")
    )
    changed = (merged[f"{column}_o"] - merged[f"{column}_b"]).abs().gt(1e-12)
    return {str(k): int(v) for k, v in changed.groupby(merged["season"]).sum().items()}


def compare(base: Arm, arm: Arm) -> dict[str, Any]:
    """Every comparison of one arm against baseline, reported separately."""
    out: dict[str, Any] = {}
    if base.observations is not None and arm.observations is not None:
        out["raw_measurements"] = {
            str(mid): am.frame_delta(
                base.observations[base.observations["measurement_id"] == mid],
                arm.observations[arm.observations["measurement_id"] == mid],
                keys=["game_id", "team", "unit_role"],
                columns=["raw_value"],
            )["columns"]["raw_value"]
            for mid in sorted(base.observations["measurement_id"].unique())
        }
    if base.terminal is not None and arm.terminal is not None:
        out["adjusted_measurements"] = {
            str(mid): am.frame_delta(
                base.terminal[base.terminal["measurement_id"] == mid],
                arm.terminal[arm.terminal["measurement_id"] == mid],
                keys=["season", "team", "unit_role"],
                columns=["adjusted_value"],
            )["columns"]["adjusted_value"]
            for mid in sorted(base.terminal["measurement_id"].unique())
        }
    out["priors"] = am.frame_delta(
        base.priors,
        arm.priors,
        keys=["season", "team", "unit_role"],
        columns=["prior_mean", "prior_variance"],
    )
    out["team_states"] = am.frame_delta(
        base.team_states,
        arm.team_states,
        keys=["season", "game_id", "team"],
        columns=["offense_rating", "defense_rating", "overall_rating"],
    )
    out["team_states_by_season"] = season_changes(
        base.team_states,
        arm.team_states,
        ["season", "game_id", "team"],
        "overall_rating",
    )
    out["final_ranks"] = am.rank_moves(
        am.final_ranks(base.team_states), am.final_ranks(arm.team_states)
    )
    out["non_offense_points"] = am.frame_delta(
        base.team_games,
        arm.team_games,
        keys=["season", "game_id", "team"],
        columns=["non_offense_for", "non_offense_against"],
    )
    out["offsets"] = am.frame_delta(
        base.offsets,
        arm.offsets,
        keys=["season", "week", "game_id"],
        columns=["offset_margin", "offset_total"],
    )
    out["coefficients_and_calibration"] = am.bundle_delta(base.bundle, arm.bundle)
    out["forecasts"] = am.frame_delta(
        base.forecasts,
        arm.forecasts,
        keys=["season", "week", "game_id"],
        columns=["pred_margin", "pred_total"],
    )
    out["forecasts_by_season"] = season_changes(
        base.forecasts, arm.forecasts, ["season", "week", "game_id"], "pred_margin"
    )
    return out


def identity_gate(base: Arm, arm: Arm) -> dict[str, Any]:
    """The arm must reproduce baseline: equal record hashes AND zero changed values."""
    left, right = arm_digests(base), arm_digests(arm)
    values = {
        "priors": (
            ["season", "team", "unit_role"],
            ["prior_mean", "prior_variance"],
            base.priors,
            arm.priors,
        ),
        "rating_states": (
            ["season", "game_id", "team", "unit_role"],
            ["rating_mean", "rating_variance"],
            base.rating_states,
            arm.rating_states,
        ),
        "team_states": (
            ["season", "game_id", "team"],
            ["offense_rating", "defense_rating", "overall_rating"],
            base.team_states,
            arm.team_states,
        ),
    }
    value_identity = {}
    for name, (keys, columns, a, b) in values.items():
        delta = am.frame_delta(a, b, keys=keys, columns=columns)
        value_identity[name] = (
            delta["only_base"] == 0
            and delta["only_other"] == 0
            and all(c["changed"] == 0 for c in delta["columns"].values())
        )
    hashes = {name: left[name] == right[name] for name in left}
    return {
        "record_hashes_equal": hashes,
        "values_identical": value_identity,
        "passed": all(hashes.values()) and all(value_identity.values()),
    }


def residuals(
    decisions: pd.DataFrame, admitted, possessions, epa_missing: int
) -> dict[str, Any]:
    reverted = decisions[decisions["decision"] != "admitted"].copy()
    reverted["points_at_stake"] = reverted["net_points"].where(
        reverted["net_points"] > 0, 0.0
    )
    by_decision = {
        str(name): {
            "groups": int(len(group)),
            "points_at_stake": float(group["points_at_stake"].sum()),
            "net_points": float(group["net_points"].sum()),
        }
        for name, group in reverted.groupby("decision")
    }
    unresolved = admitted[admitted["scoring_category"] == "unresolved"]
    ambiguous = possessions[
        possessions["possession_eligible"].astype(bool)
        & possessions["quality_reason"].notna()
    ]
    return {
        "reverted_groups_kept_at_baseline": by_decision,
        "reverted_by_primary_cause": {
            str(k): int(v) for k, v in reverted["primary_cause"].value_counts().items()
        },
        "unresolved_team_games": int(
            unresolved[["season", "game_id", "team"]].drop_duplicates().shape[0]
        ),
        "ambiguous_period_possessions_counted": int(len(ambiguous)),
        "epa_withheld_team_game_roles_vs_baseline": int(epa_missing),
        "note": (
            "Reverted groups keep the baseline allocation; their points at stake are an upper "
            "bound on remaining attribution error, not a measured error."
        ),
    }


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
    from cks_picks_cfb.forecast.offsets import build_offsets
    from cks_picks_cfb.rebuild import legacy

    run = PublishedRun(context)
    storage = run.storage
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    pins = {pin.name: pin for pin in context.plan.inputs}
    population = build_population(
        run.frame("eligibility/population_raw.parquet"), scope="historical"
    )
    outcomes = measurements._outcomes(context, storage, pin_file)

    served_measure = json.loads(context.read_input("r9_measurement_manifest"))[
        "output_refs"
    ]
    served_rating = json.loads(context.read_input("r9cert_rating_manifest"))[
        "output_refs"
    ]
    only_selected = lambda frame: frame["candidate_id"].eq(SELECTED)  # noqa: E731
    r9_states = {
        name: parity.partitioned_frame(storage, served_rating[name], keep=only_selected)
        for name in ("priors", "rating_states", "team_states")
    }
    r9_obs = parity.partitioned_frame(storage, served_measure["observations"])
    r9_terminal = parity.partitioned_frame(storage, served_measure["terminal"])
    r9_possessions = parity.partitioned_frame(storage, served_measure["possessions"])
    r9_events = parity.partitioned_frame(storage, served_measure["scoring_events"])

    admitted = run.frame("comparison/admitted_events.parquet")
    s1_possessions = run.frame("comparison/possessions.parquet")
    s1_baseline_events = run.frame("comparison/baseline_events.parquet")
    byplay_s1 = pd.concat(
        [
            f
            for _, f in sorted(
                run.dataset_frames("byplay", season_scope="historical").items()
            )
        ],
        ignore_index=True,
    )
    repair, _ = legacy._repair(
        storage, pins["repair_v2_manifest"].uri, scope="historical"
    )
    sources = legacy._sources(storage, repair, scope="historical")
    from cks_picks_cfb.data.lake import read_dataset

    byplay_s0 = legacy._concat_source_frames(
        [read_dataset(storage, sources[s]["byplay"]) for s in sorted(sources)]
    )

    seasons = tuple(DEVELOPMENT_SEASONS)
    offsets0 = build_offsets(
        population, r9_events, development_seasons=seasons, equivalent_games=4
    )
    offsets1 = build_offsets(
        population, admitted, development_seasons=seasons, equivalent_games=4
    )
    published_offsets = run.frame("forecast/offsets.parquet")
    keys = ["season", "week", "game_id", "offset_margin", "offset_total"]
    if am.frame_digest(offsets1.offsets[keys]) != am.frame_digest(
        published_offsets[keys]
    ):
        raise GateError("recomputed admitted offsets differ from the published offsets")

    epa_obs, epa_terminal, epa_design = measure(
        population, byplay_s1, outcomes, s1_possessions, s1_baseline_events
    )
    score_obs, score_terminal, score_design = measure(
        population, byplay_s0, outcomes, r9_possessions, admitted
    )
    published_states = {
        "priors": run.frame("ratings/priors.parquet"),
        "rating_states": run.frame("ratings/rating_states.parquet"),
        "team_states": run.frame("ratings/team_states.parquet"),
    }
    common_args = {"population": population, "outcomes": outcomes}
    arms = {
        "baseline": finish_arm(
            "baseline",
            states=r9_states,
            offsets=offsets0.offsets,
            team_games=offsets0.team_games,
            observations=r9_obs,
            terminal=r9_terminal,
            **common_args,
        ),
        "epa_only": finish_arm(
            "epa_only",
            states={
                "priors": epa_design.priors,
                "rating_states": epa_design.rating_states,
                "team_states": epa_design.team_states,
            },
            offsets=offsets0.offsets,
            team_games=offsets0.team_games,
            observations=epa_obs,
            terminal=epa_terminal,
            **common_args,
        ),
        "scoring_only": finish_arm(
            "scoring_only",
            states={
                "priors": score_design.priors,
                "rating_states": score_design.rating_states,
                "team_states": score_design.team_states,
            },
            offsets=offsets0.offsets,
            team_games=offsets0.team_games,
            observations=score_obs,
            terminal=score_terminal,
            **common_args,
        ),
        "offset_only": finish_arm(
            "offset_only",
            states=r9_states,
            offsets=offsets1.offsets,
            team_games=offsets1.team_games,
            observations=r9_obs,
            terminal=r9_terminal,
            **common_args,
        ),
        "combined": finish_arm(
            "combined",
            states=published_states,
            offsets=offsets1.offsets,
            team_games=offsets1.team_games,
            observations=run.frame("ratings/observations.parquet"),
            terminal=run.frame("ratings/terminal.parquet"),
            **common_args,
        ),
    }
    baseline = arms["baseline"]
    comparisons = {
        name: compare(baseline, arm) for name, arm in arms.items() if name != "baseline"
    }
    gate = identity_gate(baseline, arms["epa_only"])
    epa_missing = int(
        (
            (arms["combined"].observations["measurement_id"] == "epa_per_possession")
            & (arms["combined"].observations["coverage_status"] == "missing")
        ).sum()
        - (
            (baseline.observations["measurement_id"] == "epa_per_possession")
            & (baseline.observations["coverage_status"] == "missing")
        ).sum()
    )
    decisions = pd.read_csv(io.BytesIO(context.read_input("admission_decisions")))
    report = {
        "arms": {
            name: {
                "digests": arm_digests(arm),
                "rows": {
                    "team_states": int(len(arm.team_states)),
                    "features": int(len(arm.features)),
                    "offsets": int(len(arm.offsets)),
                },
            }
            for name, arm in arms.items()
        },
        "comparisons_vs_baseline": comparisons,
        "interaction": am.interaction({n: a.forecasts for n, a in arms.items()}),
        "epa_only_identity_gate": gate,
        "residuals": residuals(decisions, admitted, s1_possessions, epa_missing),
        "thresholds": {"material_change": am.MATERIAL, "rank_move_over": 5},
        "published": {
            "combined_equals_published": {
                "team_states": am.canonical_digest(arms["combined"].team_states)
                == am.canonical_digest(published_states["team_states"]),
                "features": am.canonical_digest(arms["combined"].features)
                == am.canonical_digest(run.frame("forecast/feature_frame.parquet")),
                "bundle": arms["combined"].bundle == run.json("forecast/bundle.json"),
            }
        },
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def parquet(frame: pd.DataFrame) -> bytes:
        buffer = io.BytesIO()
        frame.to_parquet(buffer)
        return buffer.getvalue()

    def artifacts() -> Iterator[tuple[str, bytes]]:
        for name, arm in arms.items():
            for part in (
                "priors",
                "rating_states",
                "team_states",
                "offsets",
                "features",
                "forecasts",
            ):
                yield f"{prefix}arms/{name}/{part}.parquet", parquet(getattr(arm, part))
            yield (
                f"{prefix}arms/{name}/bundle.json",
                json.dumps(arm.bundle, sort_keys=True, default=str).encode(),
            )
        yield (
            f"{prefix}report.json",
            json.dumps(report, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics={"arms": len(arms)})


def _staged_arm(context: StageContext, name: str) -> dict[str, Any]:
    prefix = PREFIX.format(run_id=context.plan.run_id)
    stage = context.stage.name

    def read(part: str) -> pd.DataFrame:
        return pd.read_parquet(
            io.BytesIO(
                context.read_artifact(stage, f"{prefix}arms/{name}/{part}.parquet")
            )
        )

    frames = {
        part: read(part)
        for part in (
            "priors",
            "rating_states",
            "team_states",
            "offsets",
            "features",
            "forecasts",
        )
    }
    frames["bundle"] = json.loads(
        context.read_artifact(stage, f"{prefix}arms/{name}/bundle.json")
    )
    return frames


def verify(context: StageContext) -> list[str]:
    from cks_picks_cfb.forecast.intended_update_bundle import assert_pre2026_frame

    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    report = json.loads(context.read_artifact(stage, prefix + "report.json"))
    arms = {name: _staged_arm(context, name) for name in ARMS}
    problems: list[str] = []
    for name, frames in arms.items():
        assert_pre2026_frame(frames["features"])
        recomputed = am.predict(frames["bundle"], frames["features"])
        if am.canonical_digest(recomputed) != am.canonical_digest(frames["forecasts"]):
            problems.append(
                f"{name}: forecasts differ from the staged bundle and features"
            )
        if frame_digests(frames) != report["arms"][name]["digests"]:
            problems.append(f"{name}: staged frames differ from the report digests")
    base, epa = (
        report["arms"]["baseline"]["digests"],
        report["arms"]["epa_only"]["digests"],
    )
    if base != epa or not report["epa_only_identity_gate"]["passed"]:
        problems.append("the EPA-only arm does not reproduce baseline")
    published = report["published"]["combined_equals_published"]
    if not all(published.values()):
        problems.append(f"combined arm differs from the published outputs: {published}")
    for name in ("scoring_only", "offset_only", "combined"):
        recomputed = am.frame_delta(
            arms["baseline"]["forecasts"],
            arms[name]["forecasts"],
            keys=["season", "week", "game_id"],
            columns=["pred_margin", "pred_total"],
        )
        if recomputed != report["comparisons_vs_baseline"][name]["forecasts"]:
            problems.append(f"{name}: forecast comparison differs from the report")
    return problems
