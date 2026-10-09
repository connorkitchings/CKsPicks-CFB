"""The ``play_identity`` plan policy across the 6A stages (contract 2026-10-09/01, Task 4.6)."""

from __future__ import annotations

import hashlib
import io
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.ratings import admission as adm
from cks_picks_cfb.rebuild import (
    baseline,
    common,
    comparison,
    eligibility,
    gold,
    stages,
)
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.silver import identity_of
from tests.test_possession_v2 import GAME, SEASON, p, v2_frame


def context(policy=None, **extra):
    policies = {} if policy is None else {"play_identity": policy}
    return SimpleNamespace(
        plan=SimpleNamespace(run_id="t", policies=policies, seasons=[SEASON], **extra),
        stage=SimpleNamespace(name="x"),
    )


# --- the staged Silver must match the plan's identity ----------------------------------


def test_staged_silver_built_with_another_identity_is_refused():
    def reader(built):
        summary = {"config": {"play_identity": built}} if built else {"config": {}}
        return lambda stage, key: json.dumps(summary).encode()

    v2_plan = context("byplay_v2")
    v2_plan.read_artifact = reader("byplay_v2")
    assert common.silver_summary(v2_plan)["config"]["play_identity"] == "byplay_v2"
    v2_plan.read_artifact = reader(None)  # a v1 build records no play identity
    with pytest.raises(GateError, match="built with play identity byplay_v1"):
        common.silver_summary(v2_plan)
    v1_plan = context()
    v1_plan.read_artifact = reader("byplay_v2")
    with pytest.raises(GateError, match="plan policy is byplay_v1"):
        common.silver_summary(v1_plan)
    v1_plan.read_artifact = reader(None)
    assert common.silver_summary(v1_plan)  # the default plan is unchanged


def test_an_unknown_policy_value_is_refused():
    with pytest.raises(GateError):
        identity_of(context("byplay_v3"))


# --- stages pinned to the superseded identity -------------------------------------------


V1_ONLY = sorted(stages.V1_PINNED_STAGES)


@pytest.mark.parametrize("name", V1_ONLY)
def test_pinned_stages_refuse_a_v2_plan_and_name_the_stage(name):
    build, verify = stages.STAGE_BUILDERS[name]
    for function in (build, verify):
        with pytest.raises(GateError, match=f"stage {name} is pinned to byplay_v1"):
            function(context("byplay_v2"))


def test_stages_that_support_v2_are_not_wrapped():
    for name in (
        "silver",
        "eligibility",
        "step5_comparison",
        "gold",
        "measurements_ratings",
    ):
        assert name not in stages.V1_PINNED_STAGES
    assert stages.STAGE_BUILDERS["silver"][0].__name__ == "build"
    assert stages.STAGE_BUILDERS["step5_comparison"][0] is comparison.build
    assert stages.STAGE_BUILDERS["gold"][0] is gold.build


def test_every_registered_stage_is_classified():
    assert set(stages.V1_PINNED_STAGES) <= set(stages.STAGE_BUILDERS)


# --- gold selects its schema versions by identity ----------------------------------------


def test_gold_versions_follow_the_identity_and_v1_is_all_v1():
    config, versions = gold.settings_for("byplay_v1")
    assert config is gold.GOLD_CONFIG and all(
        v.endswith("_v1") for v in versions.values()
    )
    config2, versions2 = gold.settings_for("byplay_v2")
    changed = {k for k in versions if versions[k] != versions2[k]}
    assert changed == {
        "football_possessions",
        "football_scoring_ledger",
        "scoring_attribution_evidence",
    }
    assert (
        versions2["team_game_metrics"] == "team_game_metrics_v1"
    )  # carries no play identity
    assert gold.config_sha(config2) != gold.config_sha(config)
    assert gold.config_sha() == gold.config_sha(gold.GOLD_CONFIG)
    with pytest.raises(GateError):
        gold.settings_for("byplay_v3")


# --- the comparison stage dispatches and runs end to end under v2 ------------------------


def test_comparison_dispatches_on_the_policy(monkeypatch):
    monkeypatch.setattr(comparison, "_build_v1", lambda c: "v1")
    monkeypatch.setattr(comparison, "_build_v2", lambda c: "v2")
    monkeypatch.setattr(comparison, "_verify_v1", lambda c: ["v1"])
    monkeypatch.setattr(comparison, "_verify_v2", lambda c: ["v2"])
    assert (
        comparison.build(context()) == "v1"
        and comparison.build(context("byplay_v1")) == "v1"
    )
    assert comparison.build(context("byplay_v2")) == "v2"
    assert comparison.verify(context()) == ["v1"] and comparison.verify(
        context("byplay_v2")
    ) == ["v2"]


def glitch_rows():
    """A scores 7, 14, a spurious 21, reverts to 14, then 21, 28, 34: R1 changes the ledger."""
    return [
        p(1, 1, 11, 0, 0),
        p(1, 2, 12, 7, 0, kind="Rushing Touchdown", scoring=1),
        p(1, 3, 13, 14, 0, kind="Rushing Touchdown", scoring=1),
        p(1, 4, 14, 21, 0, kind="Rushing Touchdown"),
        p(1, 5, 15, 14, 0),
        p(1, 6, 16, 21, 0, kind="Rushing Touchdown", scoring=1),
        p(1, 7, 17, 28, 0, kind="Rushing Touchdown", scoring=1),
        p(1, 8, 18, 34, 0, kind="Rushing Touchdown", scoring=1),
    ]


def population_frame():
    return pd.DataFrame(
        [
            dict(
                season=SEASON,
                week=6,
                game_id=GAME,
                kickoff_utc="2025-10-04T18:00:00Z",
                home_team="A",
                away_team="B",
                home_points=34.0,
                away_points=0.0,
                outcome_valid=True,
                schedule_completed=True,
                forecast_eligible=True,
                measurement_usable=True,
            )
        ]
    )


def parquet(frame):
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


@pytest.fixture
def staged(monkeypatch):
    """A faked context for the v2 comparison stage with in-memory inputs and storage."""
    from cks_picks_cfb.data import data_first_possession_v1, lake
    from cks_picks_cfb.rebuild import legacy

    byplay = v2_frame(glitch_rows())
    population = population_frame()
    outcomes = population[["season", "game_id", "home_points", "away_points"]]
    finals = {(GAME, "A"): 34.0, (GAME, "B"): 0.0}
    _, _, _, groups, members = comparison.ledgers_for(
        "byplay_v2", byplay, population, outcomes, finals
    )
    assert len(groups) >= 1
    status = groups[
        [
            "group_id",
            "season",
            "game_id",
            "team",
            "channel",
            "primary_cause",
            "net_points",
        ]
    ].assign(status="corroborated")
    decisions_csv = adm.build_decisions(status, members).to_csv(index=False).encode()
    sha = hashlib.sha256(decisions_csv).hexdigest()
    ref = {
        "dataset": "x",
        "version_id": "v",
        "schema_version": "s",
        "content_sha": "c",
        "uri": "u",
    }
    inputs = {
        "phase2c_silver_parents": json.dumps(
            {
                "seasons": {
                    str(SEASON): {"game_outcomes": {**ref, "dataset": "outcomes"}}
                }
            }
        ).encode(),
        "corroboration_group_status_v2": status.to_csv(index=False).encode(),
        "admission_rekey_report": json.dumps(
            {"passed": True, "outputs": {"admission_decisions_v2_sha256": sha}}
        ).encode(),
    }
    artifacts = {
        (
            "eligibility",
            eligibility.PREFIX.format(run_id="t") + eligibility.POPULATION,
        ): parquet(population)
    }
    ctx = SimpleNamespace(
        plan=SimpleNamespace(
            run_id="t",
            seasons=[SEASON],
            policies={"play_identity": "byplay_v2"},
            inputs=[SimpleNamespace(name="repair_v2_manifest", uri="repair")],
            decisions={"admission_decisions_v2_csv": sha},
        ),
        stage=SimpleNamespace(name="step5_comparison"),
        read_input=lambda name: inputs[name],
        read_artifact=lambda stage, key: artifacts[(stage, key)],
    )
    monkeypatch.setattr(common, "preview_storage", lambda c: object())
    monkeypatch.setattr(common, "staged_silver", lambda c, name: byplay)
    monkeypatch.setattr(
        data_first_possession_v1, "build_population", lambda frame, scope: frame
    )
    monkeypatch.setattr(
        lake,
        "read_dataset",
        lambda storage, r: outcomes if r.dataset == "outcomes" else population,
    )
    monkeypatch.setattr(
        legacy,
        "_repair",
        lambda storage, uri, scope: ({"output_refs": {"population": ref}}, None),
    )
    return ctx, sha


def run_build(ctx):
    output = comparison.build(ctx)
    files = dict(output.artifacts)
    return files, json.loads(
        files[comparison.PREFIX.format(run_id="t") + comparison.RECEIPT]
    )


def test_the_v2_comparison_stage_checks_the_pinned_groups_the_verifier_and_the_report(
    staged, monkeypatch
):
    ctx, sha = staged
    files, receipt = run_build(ctx)
    checks = receipt["checks"]
    assert receipt["play_identity"] == "byplay_v2"
    assert checks["group_ids_match_v2_status"] and checks["decisions_csv_bytes"]
    assert checks["rekey_report_passed"] and checks["population_parity"]
    assert checks["independent_verifier"]
    # the synthetic slate does not have the real 1,416 / 28 / 1,749 decisions
    assert (
        checks["admitted_and_contradicted_unchanged"] is False
        and receipt["passed"] is False
    )
    assert set(receipt["skipped"]) == {
        "admitted_equals_stage1",
        "punt_flag_change_bounded",
    }
    admitted = pd.read_parquet(
        io.BytesIO(
            files[
                comparison.PREFIX.format(run_id="t")
                + comparison.FILES["admitted_events"]
            ]
        )
    )
    assert "source_play_id" in admitted.columns

    monkeypatch.setattr(
        baseline,
        "EXPECTED",
        {
            **baseline.EXPECTED,
            "decisions": {
                "admitted": 1,
                "reverted_contradicted": 0,
                "reverted_unverified": 0,
            },
        },
    )
    files, receipt = run_build(ctx)
    assert receipt["passed"] is True

    ctx.stage = SimpleNamespace(name="step5_comparison")
    ctx.read_artifact = lambda stage, key: files[key]
    assert comparison.verify(ctx) == []
    tampered = dict(files)
    tampered[comparison.PREFIX.format(run_id="t") + comparison.FILES["decisions"]] = (
        b"group_id\n"
    )
    ctx.read_artifact = lambda stage, key: tampered[key]
    assert any("decisions differ" in problem for problem in comparison.verify(ctx))


def test_the_v2_stage_fails_closed_when_the_pinned_groups_do_not_match(staged):
    ctx, _ = staged
    original = ctx.read_input
    status = pd.read_csv(io.BytesIO(original("corroboration_group_status_v2"))).iloc[
        0:0
    ]
    ctx.read_input = lambda name: (
        status.to_csv(index=False).encode()
        if name == "corroboration_group_status_v2"
        else original(name)
    )
    with pytest.raises(GateError, match="differ from the pinned v2 groups"):
        comparison.build(ctx)
