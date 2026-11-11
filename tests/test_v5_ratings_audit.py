import pandas as pd
import pytest

from cks_picks_cfb.audit.v5_ratings import audit_generation


def inputs():
    rows = []
    for game, week, a, b, off, defense, exposure in [
        (1, 0, "A", "B", 4.0, 4.0, 10),
        (2, 1, "A", "C", 2.0, 2.0, 20),
        (3, 1, "B", "C", 1.0, 1.0, 5),
    ]:
        for team, opponent, role, value in [
            (a, b, "offense", off),
            (b, a, "defense", defense),
        ]:
            rows.append(
                dict(
                    season=2026,
                    week=week,
                    game_id=game,
                    kickoff_utc="2026-09-01T00:00:00Z",
                    team=team,
                    opponent=opponent,
                    measurement_id="ppp",
                    unit_role=role,
                    raw_value=value,
                    numerator=value * exposure,
                    denominator=exposure,
                    coverage_status="observed",
                )
            )
    priors = pd.DataFrame(
        [
            dict(season=2026, team=t, unit_role=r, prior_mean=0.0, prior_variance=1.0)
            for t in "ABC"
            for r in ("offense", "defense")
        ]
    )
    terminal = pd.DataFrame(
        [
            dict(season=2025, measurement_id="ppp", unit_role=r, adjusted_value=v)
            for r in ("offense", "defense")
            for v in (1.0, 3.0)
        ]
    )
    return pd.DataFrame(rows), priors, terminal


def run(observations, priors, terminal, **kwargs):
    return audit_generation(
        observations, priors, terminal, week=2, cutoff="2026-09-03T00:00:00Z", **kwargs
    )


def test_posterior_unequal_exposure_and_defensive_sign():
    result = run(*inputs())
    state = next(
        s for s in result["states"] if s["team"] == "A" and s["unit_role"] == "offense"
    )
    assert state["usable_exposure"] == 30
    assert state["rating_variance"] == pytest.approx(1 / (1 + 30 / 8))
    assert state["rating_mean"] == pytest.approx(
        state["prior_contribution"]
        + sum(x["contribution"] for x in state["contributions"])
    )
    assert result["scales"]["defense"]["sign"] == -1
    assert result["component_check"]["status"] == "unavailable"
    assert result["adjusted_check"]["status"] == "unavailable"


def test_missing_context_and_asymmetric_quarantine():
    observations, priors, terminal = inputs()
    observations.loc[
        (observations.game_id == 1) & (observations.unit_role == "defense"),
        "coverage_status",
    ] = "missing"
    result = run(observations, priors, terminal, fbs_teams={"A", "B"})
    assert len(result["exclusions"]) == 1
    edge = next(
        e
        for e in result["edges"]
        if e["pass"] == 4 and e["game_id"] == 1 and e["team"] == "A"
    )
    assert edge["context_status"] == "missing_opponent_context_raw_ppp"
    assert edge["adjusted_ppp"] == edge["raw_ppp"]
    population = next(
        p
        for p in result["populations"]
        if p["team"] == "A" and p["role"] == "offense" and p["cohort"] == "fbs_vs_fbs"
    )
    assert population["games"] == 1


def test_future_and_duplicate_observations():
    observations, priors, terminal = inputs()
    result = audit_generation(
        observations, priors, terminal, week=1, cutoff="2026-09-03T00:00:00Z"
    )
    assert {e["game_id"] for e in result["edges"]} == {1}
    with pytest.raises(ValueError, match="duplicate"):
        run(pd.concat([observations, observations.iloc[[0]]]), priors, terminal)


def test_corrupt_stored_artifacts_are_reported():
    observations, priors, terminal = inputs()
    first = run(observations, priors, terminal)
    components = pd.DataFrame(first["states"]).drop(columns="contributions")
    components.loc[0, "rating_mean"] += 0.1
    result = run(observations, priors, terminal, components=components)
    assert result["component_check"]["status"] == "discrepancy"
    assert result["component_check"]["differences"][0]["field"] == "rating_mean"


def test_graph_sensitivity_preserves_opposite_scoring_pair():
    from cks_picks_cfb.audit.v5_ratings import audit_graph_sensitivity

    observations, priors, terminal = inputs()
    observations.loc[
        (observations.game_id == 1) & (observations.unit_role == "defense"),
        "coverage_status",
    ] = "missing"
    result = audit_graph_sensitivity(
        observations,
        priors,
        terminal,
        week=2,
        cutoff="2026-09-03T00:00:00Z",
        sec_teams={"A", "B", "C"},
        focus_teams=("A", "B"),
    )
    assert result["partial_game_ids"] == [1]
    assert result["scenarios"][0]["removed_game_ids"] == [1]
    assert any(
        change["delta"]["rating"] != 0
        for change in result["scenarios"][0]["changes"]
        if change["delta"]["rating"] is not None
    )


def test_historical_cohorts_and_weighted_center():
    observations, priors, terminal = inputs()
    terminal["team"] = ["A", "X", "A", "B"]
    terminal["primary_exposure"] = [1, 3, 2, 2]
    result = run(observations, priors, terminal, fbs_teams={"A", "B"})
    assert result["scale_cohorts"]["offense"]["exposure_weighted_center"] == 2.5
    assert result["scale_cohorts"]["offense"]["non_fbs_count"] == 1
    assert result["scale_cohorts"]["offense"]["common_team_center"] == 1


@pytest.mark.parametrize(
    "column,value",
    [
        ("denominator", 0),
        ("denominator", float("nan")),
        ("raw_value", float("nan")),
        ("numerator", float("nan")),
    ],
)
def test_invalid_measurements_are_excluded(column, value):
    observations, priors, terminal = inputs()
    observations.loc[0, column] = value
    result = run(observations, priors, terminal)
    assert len(result["exclusions"]) == 1


def test_wrong_role_and_adjusted_artifact_values_and_keys():
    observations, priors, terminal = inputs()
    bad = observations.copy()
    bad.loc[0, "unit_role"] = "special"
    with pytest.raises(ValueError, match="unknown role"):
        run(bad, priors, terminal)
    baseline = run(observations, priors, terminal)
    last = [x for x in baseline["passes"] if x["pass"] == 4]
    raw = {
        (x["team"], x["role"]): x["value"] for x in baseline["passes"] if x["pass"] == 0
    }
    adjusted = pd.DataFrame(
        [
            dict(
                team=x["team"],
                role=x["role"],
                raw_value=raw[(x["team"], x["role"])],
                adjusted_value=x["value"],
                opponent_adjustment=raw[(x["team"], x["role"])] - x["value"],
                primary_exposure=x["exposure"],
            )
            for x in last
        ]
    )
    assert (
        run(observations, priors, terminal, adjusted=adjusted)["adjusted_check"][
            "status"
        ]
        == "agreement"
    )
    adjusted.loc[0, "primary_exposure"] += 1
    adjusted.loc[1, "team"] = "wrong"
    assert (
        run(observations, priors, terminal, adjusted=adjusted)["adjusted_check"][
            "status"
        ]
        == "discrepancy"
    )


def test_asymmetric_quarantine_and_declared_score_mismatch():
    from cks_picks_cfb.audit.v5_ratings import audit_source_quarantine

    observations, _, _ = inputs()
    original = observations.iloc[0].copy()
    opposite = original.copy()
    opposite["team"], opposite["opponent"], opposite["unit_role"] = "B", "A", "defense"
    other_offense = original.copy()
    other_offense["team"], other_offense["opponent"] = "B", "A"
    other_defense = original.copy()
    other_defense["unit_role"] = "defense"
    observations = pd.DataFrame([original, opposite, other_offense, other_defense])
    observations.loc[
        observations.team.eq("A") & observations.unit_role.eq("offense"), "denominator"
    ] = 0
    observations.loc[
        observations.team.eq("B") & observations.unit_role.eq("defense"), "denominator"
    ] = 0
    events = pd.DataFrame(
        [
            dict(
                game_id=1,
                team="A",
                score_increment=3,
                scoring_category="field_goal",
                unit_category="offense",
            ),
            dict(
                game_id=1,
                team="B",
                score_increment=7,
                scoring_category="touchdown",
                unit_category="offense",
            ),
        ]
    )
    finals = pd.DataFrame(
        [dict(game_id=1, home_team="A", away_team="B", home_points=7, away_points=7)]
    )
    result = audit_source_quarantine(
        observations, events, finals, {(1, "A"): "known mismatch"}
    )
    game = result["affected_games"][0]
    assert game["classification"] == "partial_quarantine"
    assert [x["pair_integrity"] for x in game["scoring_pairs"]] == [
        "agreement",
        "agreement",
    ]
    assert [x["status"] for x in game["scores"]] == ["declared_mismatch", "agreement"]
    assert [x["status"] for x in game["roles"]].count("usable") == 2
    observations.loc[
        observations.team.eq("B") & observations.unit_role.eq("defense"), "denominator"
    ] = 10
    game = audit_source_quarantine(
        observations, events, finals, {(1, "A"): "known mismatch"}
    )["affected_games"][0]
    assert game["scoring_pairs"][0]["pair_integrity"] == "discrepancy"


def test_nested_component_evidence_detects_changed_game_even_if_total_matches():
    observations, priors, terminal = inputs()
    baseline = run(observations, priors, terminal)
    components = pd.DataFrame(baseline["states"]).drop(
        columns=["contributions", "adjusted_identity"]
    )
    components["evidence"] = [
        [
            dict(
                game_id=i["game_id"],
                source_week=i["week"],
                available_utc=i["available_utc"],
                exposure=i["exposure"],
                raw_ppp=i["raw_ppp"],
                adjusted_ppp=i["adjusted_ppp"],
                adjusted_z=i["adjusted_z"],
                contribution=i["contribution"],
                missing_context_reason=None
                if i["context_status"] == "complete"
                else i["context_status"],
            )
            for i in s["contributions"]
        ]
        for s in baseline["states"]
    ]
    components["k"] = 8.0
    components["evidence_weight"] = 1 - components.prior_weight
    components["completed_games"] = components.evidence.map(len)
    assert (
        run(observations, priors, terminal, components=components)["component_check"][
            "status"
        ]
        == "agreement"
    )
    index = components.evidence.map(bool).idxmax()
    components.at[index, "evidence"][0]["contribution"] += 0.1
    assert (
        run(observations, priors, terminal, components=components)["component_check"][
            "status"
        ]
        == "discrepancy"
    )
    components.at[index, "evidence"].append(components.at[index, "evidence"][0])
    assert any(
        x.get("reason") == "duplicate or mismatched source games"
        for x in run(observations, priors, terminal, components=components)[
            "component_check"
        ]["differences"]
    )


def test_preseason_null_k_and_later_empty_evidence_k():
    observations, priors, terminal = inputs()
    baseline = audit_generation(
        observations, priors, terminal, week=0, cutoff="2026-08-01T00:00:00Z"
    )
    components = pd.DataFrame(baseline["states"]).drop(
        columns=["contributions", "adjusted_identity", "prior_check"]
    )
    components["snapshot_class"] = "preseason"
    components["k"] = None
    components["evidence_weight"] = 0.0
    components["completed_games"] = 0
    components["evidence"] = [[] for _ in range(len(components))]
    assert (
        audit_generation(
            observations,
            priors,
            terminal,
            week=0,
            cutoff="2026-08-01T00:00:00Z",
            components=components,
        )["component_check"]["status"]
        == "agreement"
    )
    components["snapshot_class"] = "pregame"
    assert (
        audit_generation(
            observations,
            priors,
            terminal,
            week=0,
            cutoff="2026-08-01T00:00:00Z",
            components=components,
        )["component_check"]["status"]
        == "discrepancy"
    )
    components["k"] = 8.0
    assert (
        audit_generation(
            observations,
            priors,
            terminal,
            week=0,
            cutoff="2026-08-01T00:00:00Z",
            components=components,
        )["component_check"]["status"]
        == "agreement"
    )


def test_adjusted_comparison_keeps_fcs_graph_but_only_compares_fbs_rows():
    observations, priors, terminal = inputs()
    baseline = run(observations, priors, terminal, fbs_teams={"A", "B"})
    raw = {
        (x["team"], x["role"]): x["value"] for x in baseline["passes"] if x["pass"] == 0
    }
    adjusted = pd.DataFrame(
        [
            dict(
                team=x["team"],
                role=x["role"],
                raw_value=raw[(x["team"], x["role"])],
                adjusted_value=x["value"],
                opponent_adjustment=raw[(x["team"], x["role"])] - x["value"],
                primary_exposure=x["exposure"],
            )
            for x in baseline["passes"]
            if x["pass"] == 4 and x["team"] in {"A", "B"}
        ]
    )
    assert any(x["team"] == "C" for x in baseline["passes"])
    assert (
        run(observations, priors, terminal, fbs_teams={"A", "B"}, adjusted=adjusted)[
            "adjusted_check"
        ]["status"]
        == "agreement"
    )
    adjusted.loc[0, "adjusted_value"] += 0.1
    assert (
        run(observations, priors, terminal, fbs_teams={"A", "B"}, adjusted=adjusted)[
            "adjusted_check"
        ]["status"]
        == "discrepancy"
    )


def test_certified_prior_reconstructed_from_terminal_and_fallback_unavailable():
    observations, priors, terminal = inputs()
    terminal["team"] = ["A", "X", "A", "X"]
    terminal["primary_exposure"] = [8.0, 16.0, 8.0, 16.0]
    for role, mean in [("offense", -0.6), ("defense", 0.6)]:
        index = priors.team.eq("A") & priors.unit_role.eq(role)
        priors.loc[index, "prior_mean"] = mean
        priors.loc[index, "prior_variance"] = 0.82
    result = run(observations, priors, terminal)
    a = [s for s in result["states"] if s["team"] == "A"]
    assert all(s["prior_check"]["status"] == "agreement" for s in a)
    assert all(s["prior_check"]["terminal_exposure"] == 8 for s in a)
    assert (
        next(s for s in result["states"] if s["team"] == "B")["prior_check"]["status"]
        == "unavailable"
    )
    priors.loc[priors.team.eq("A") & priors.unit_role.eq("offense"), "prior_mean"] += (
        0.01
    )
    assert (
        next(
            s
            for s in run(observations, priors, terminal)["states"]
            if s["team"] == "A" and s["unit_role"] == "offense"
        )["prior_check"]["status"]
        == "discrepancy"
    )


def test_component_metadata_checks_cutoff_week_and_expected_source():
    observations, priors, terminal = inputs()
    result = run(observations, priors, terminal)
    components = pd.DataFrame(result["states"]).drop(
        columns=["contributions", "adjusted_identity", "prior_check"]
    )
    components["as_of_week"] = 2
    components["cutoff_utc"] = "2026-09-03T00:00:00Z"
    components["source_manifest_sha256"] = "known-source"
    good = run(
        observations,
        priors,
        terminal,
        components=components,
        expected_rating_source="known-source",
    )["component_check"]
    assert good["status"] == "agreement"
    assert good["metadata"]["cutoff_utc"] == "agreement"
    components.loc[0, "cutoff_utc"] = "2099-01-01T00:00:00Z"
    components.loc[1, "source_manifest_sha256"] = "wrong"
    components.loc[2, "as_of_week"] = 3
    bad = run(
        observations,
        priors,
        terminal,
        components=components,
        expected_rating_source="known-source",
    )["component_check"]
    assert {d["field"] for d in bad["differences"]} >= {
        "cutoff_utc",
        "source_manifest_sha256",
        "as_of_week",
    }
    assert (
        run(observations, priors, terminal, components=components)["component_check"][
            "metadata"
        ]["source_manifest_sha256"]
        == "unavailable"
    )


def test_historical_membership_groups_report_team_and_exposure_weighted_means():
    observations, priors, terminal = inputs()
    terminal = pd.DataFrame(
        [
            dict(
                season=2025,
                measurement_id="ppp",
                unit_role=role,
                team=team,
                adjusted_value=value,
                primary_exposure=exposure,
            )
            for role in ("offense", "defense")
            for team, value, exposure in [
                ("A", 1, 1),
                ("B", 3, 3),
                ("X", 5, 2),
                ("Y", 9, 6),
            ]
        ]
    )
    cohort = run(observations, priors, terminal, fbs_teams={"A", "B"})["scale_cohorts"][
        "offense"
    ]
    assert cohort["fbs"]["team_mean"] == 2
    assert cohort["fbs"]["exposure_weighted_mean"] == 2.5
    assert cohort["non_fbs"]["team_mean"] == 7
    assert cohort["non_fbs"]["exposure_weighted_mean"] == 8
    assert cohort["full"]["exposure_sum"] == 12
    assert (
        cohort["full"]["exposure_min"],
        cohort["full"]["exposure_median"],
        cohort["full"]["exposure_max"],
    ) == (1, 2.5, 6)
    assert "2025 membership unknown" in cohort["membership_reference"]
