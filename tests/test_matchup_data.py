"""Matchup data layer v2 builders: names, game log, raw and adjusted stats, components."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.ratings.possession_measurements import adjust_possession_history

SHA = "a" * 64
MSHA = "b" * 64
KICK = {0: "2026-08-29T16:00:00Z", 1: "2026-09-05T16:00:00Z", 2: "2026-09-12T16:00:00Z"}
ALIAS = {
    "Hawai'i": "Hawai_i",
    "Hawaii": "Hawai_i",
    "Hawai i": "Hawai_i",
    "FIU": "Florida International",
}
GAME_NAMES = {"Alpha", "Beta", "Hawai'i", "Florida International"}


def team_stats(poss=10, points=20, epa=5.0, plays=60, nonoff=0, ppp_missing=False):
    return dict(
        poss=poss,
        points=points,
        epa=epa,
        plays=plays,
        nonoff=nonoff,
        ppp_missing=ppp_missing,
    )


def game_rows(game_id, week, home, away, home_stats, away_stats):
    """32 observation rows; defense rows carry the opponent's numbers."""
    rows = []
    for team, opp, side, own, other in (
        (home, away, "home", home_stats, away_stats),
        (away, home, "away", away_stats, home_stats),
    ):
        for role, src in (("offense", own), ("defense", other)):
            miss = src["ppp_missing"]
            spec = {
                "eligible_possessions": (src["poss"], 1.0, src["poss"], "count", False),
                "offensive_possession_points": (
                    src["points"],
                    1.0,
                    src["points"],
                    "count",
                    miss,
                ),
                "ppp": (
                    src["points"],
                    src["poss"],
                    src["points"] / src["poss"],
                    "possessions",
                    miss,
                ),
                "eligible_epa": (src["epa"], 1.0, src["epa"], "count", False),
                "epa_per_possession": (
                    src["epa"],
                    src["poss"],
                    src["epa"] / src["poss"],
                    "possessions",
                    False,
                ),
                "eligible_scrimmage_plays": (
                    src["plays"],
                    1.0,
                    src["plays"],
                    "count",
                    False,
                ),
                "plays_per_possession": (
                    src["plays"],
                    src["poss"],
                    src["plays"] / src["poss"],
                    "possessions",
                    False,
                ),
                "non_offense_points": (
                    src["nonoff"],
                    1.0,
                    src["nonoff"],
                    "count",
                    miss,
                ),
            }
            for measure, (num, den, raw, unit, missing) in spec.items():
                rows.append(
                    {
                        "season": 2026,
                        "week": week,
                        "game_id": game_id,
                        "kickoff_utc": KICK[week],
                        "team": team,
                        "opponent": opp,
                        "side": side,
                        "measurement_id": measure,
                        "unit_role": role,
                        "numerator": num,
                        "denominator": den,
                        "raw_value": np.nan if missing else raw,
                        "usable_exposure": 0.0 if missing else den,
                        "exposure_unit": unit,
                        "coverage_status": "missing" if missing else "observed",
                        "missing_reason": "unresolved_scoring_attribution"
                        if missing
                        else None,
                        "quality_flags": "mixed_eligibility_drive",
                        "timing_class": "live",
                    }
                )
    return rows


def world():
    obs = pd.DataFrame(
        game_rows(
            1,
            0,
            "Alpha",
            "Hawai_i",
            team_stats(10, 30, 8.0, 60),
            team_stats(12, 12, -2.0, 70, nonoff=7),
        )
        + game_rows(
            2,
            1,
            "Beta",
            "Alpha",
            team_stats(11, 22, 4.0, 66),
            team_stats(10, 40, 9.0, 55, ppp_missing=True),
        )
        + game_rows(
            3,
            2,
            "Hawai_i",
            "Beta",
            team_stats(9, 18, 1.0, 50),
            team_stats(11, 33, 6.0, 64),
        )
    )
    name_map = md.resolve_game_names(
        set(obs.team) | set(obs.opponent), GAME_NAMES, ALIAS
    )
    return md.prepare_observations(obs, name_map), name_map


FBS = {"Alpha", "Beta", "Hawai'i"}
CUTOFFS = {
    1: pd.Timestamp("2026-09-03T04:00:00Z"),
    2: pd.Timestamp("2026-09-10T04:00:00Z"),
    3: pd.Timestamp("2026-09-17T04:00:00Z"),
}


def test_resolve_game_names_handles_legacy_aliases_and_game_names():
    mapped = md.resolve_game_names(
        {"Hawai_i", "Florida International", "Alpha", "Unknown FCS"}, GAME_NAMES, ALIAS
    )
    assert mapped == {
        "Hawai_i": "Hawai'i",  # three alias keys, one is a game name
        "Florida International": "Florida International",  # already a game name
        "Alpha": "Alpha",
        "Unknown FCS": "Unknown FCS",
    }


def test_resolve_game_names_rejects_ambiguity():
    with pytest.raises(md.MatchupDataError, match="ambiguous"):
        md.resolve_game_names({"Hawai_i"}, {"Hawai'i", "Hawaii"}, ALIAS)


def test_prepare_rejects_missing_columns_and_duplicates():
    obs, _ = world()
    with pytest.raises(md.MatchupDataError, match="lack columns"):
        md.prepare_observations(obs.drop(columns=["side"]), {})
    with pytest.raises(md.MatchupDataError, match="duplicate"):
        md.prepare_observations(pd.concat([obs.iloc[:32], obs.iloc[:1]]), {})


def test_game_log_is_row_for_row_with_flags_and_game_names():
    prepared, _ = world()
    log = md.build_game_log(
        prepared,
        fbs_names=FBS,
        measurement_manifest_sha256=MSHA,
        source_versions={"m": "x"},
    )
    assert len(log) == len(prepared) == 96
    assert list(log.columns) == list(md.GAME_LOG_COLUMNS)
    assert set(log.team) == {"Alpha", "Beta", "Hawai'i"}  # game names, not Hawai_i
    bad = log[
        (log.team == "Alpha") & (log.game_id == 2) & (log.measurement_id == "ppp")
    ]
    off = bad[bad.unit_role == "offense"].iloc[0]
    assert off.coverage_status == "missing" and not off.rating_usable
    assert off.missing_reason == "unresolved_scoring_attribution"
    # rating_usable is for PPP rows only
    assert not log[log.measurement_id == "epa_per_possession"].rating_usable.any()
    assert log[
        (log.measurement_id == "ppp") & (log.coverage_status == "observed")
    ].rating_usable.all()
    assert log.opponent_fbs.all()


def test_stats_ratio_of_sums_excluded_games_and_week_window():
    prepared, _ = world()
    stats = md.build_possession_stats(
        prepared,
        season=2026,
        as_of_cutoffs=CUTOFFS,
        fbs_names=FBS,
        rating_manifest_sha256=SHA,
        measurement_manifest_sha256=MSHA,
        source_versions={"m": "x"},
    )

    def get(week, team, role, metric):
        row = stats[
            (stats.as_of_week == week)
            & (stats.team == team)
            & (stats.role == role)
            & (stats.metric == metric)
        ]
        assert len(row) == 1, (week, team, role, metric)
        return row.iloc[0]

    # as_of 3 = games in weeks 0-1... plus week 2? week < 3 includes weeks 0, 1, 2.
    alpha = get(3, "Alpha", "offense", "ppp")
    # Alpha offense: game 1 (30/10) usable; game 2 ppp missing -> excluded, not counted.
    assert (
        alpha.value == pytest.approx(3.0)
        and alpha.games == 1
        and alpha.games_excluded == 1
    )
    assert alpha.excluded == [
        {"game_id": 2, "reason": "unresolved_scoring_attribution"}
    ]
    # Alpha defense (what it allowed): game 1 Hawai_i 12/12, game 2 Beta 22/11 -> 34/23
    assert get(3, "Alpha", "defense", "ppp").value == pytest.approx(34 / 23)
    # EPA per play uses eligible EPA over eligible scrimmage plays, all observed games
    assert get(3, "Alpha", "offense", "epa_per_play").value == pytest.approx(
        (8.0 + 9.0) / (60 + 55)
    )
    assert get(3, "Alpha", "offense", "possessions_per_game").value == pytest.approx(
        (10 + 10) / 2
    )
    # non-offense points: offense scored; defense allowed. Hawai'i own 7 in game 1
    assert get(
        3, "Hawai'i", "offense", "non_offense_points_per_game"
    ).value == pytest.approx((7 + 0) / 2)
    # window: as_of 1 sees only week 0; as_of 2 adds week 1
    assert get(1, "Alpha", "offense", "ppp").games == 1
    assert get(2, "Alpha", "offense", "ppp").games_excluded == 1
    assert stats[stats.as_of_week == 1].team.nunique() == 2  # Alpha and Hawai'i only


def test_stats_availability_buffer_blocks_games_not_yet_available():
    prepared, _ = world()
    # Cutoff 5 hours after the week-1 kickoff: availability needs 6 hours.
    early = {2: pd.Timestamp("2026-09-05T21:00:00Z")}
    stats = md.build_possession_stats(
        prepared,
        season=2026,
        as_of_cutoffs=early,
        fbs_names=FBS,
        rating_manifest_sha256=SHA,
        measurement_manifest_sha256=MSHA,
        source_versions={},
    )
    assert set(stats[stats.metric == "ppp"].team) == {
        "Alpha",
        "Hawai'i",
    }  # week-1 game excluded


def test_stats_rank_direction_and_pace_unranked():
    prepared, _ = world()
    stats = md.build_possession_stats(
        prepared,
        season=2026,
        as_of_cutoffs={3: CUTOFFS[3]},
        fbs_names=FBS,
        rating_manifest_sha256=SHA,
        measurement_manifest_sha256=MSHA,
        source_versions={},
    )
    off = stats[
        (stats.role == "offense") & (stats.metric == "epa_per_possession")
    ].sort_values("value", ascending=False)
    assert off["rank"].tolist() == list(range(1, len(off) + 1))  # higher is better
    dfn = stats[
        (stats.role == "defense") & (stats.metric == "epa_per_possession")
    ].sort_values("value")
    assert dfn["rank"].tolist() == list(
        range(1, len(dfn) + 1)
    )  # lower allowed is better
    assert stats[stats.metric == "possessions_per_game"]["rank"].isna().all()


def test_adjusted_matches_the_ratings_adjuster_and_never_reads_the_future():
    prepared, _ = world()
    adj = md.build_possession_adjusted(
        prepared,
        season=2026,
        as_of_cutoffs=CUTOFFS,
        fbs_names=FBS,
        rating_manifest_sha256=SHA,
        measurement_manifest_sha256=MSHA,
    )
    window = prepared[
        prepared.measurement_id.isin(md.ADJUSTED_MEASUREMENTS)
        & prepared.observed
        & prepared.denominator.gt(0)
        & prepared.week.lt(3)
        & prepared.available_utc.le(CUTOFFS[3])
    ]
    raw, adjusted = adjust_possession_history(
        window[
            [
                "team",
                "opponent",
                "unit_role",
                "measurement_id",
                "numerator",
                "denominator",
            ]
        ]
    )
    row = adj[
        (adj.as_of_week == 3)
        & (adj.team == "Hawai'i")
        & (adj.role == "offense")
        & (adj.measurement_id == "epa_per_possession")
    ].iloc[0]
    assert row.adjusted_value == pytest.approx(
        adjusted[("Hawai_i", "offense", "epa_per_possession")]
    )
    assert row.opponent_adjustment == pytest.approx(row.raw_value - row.adjusted_value)
    assert row.adjustment_method == md.ADJUSTMENT_METHOD
    # as_of 1 has no adjusted row for a team that had not played
    assert set(adj[adj.as_of_week == 1].team) == {"Alpha", "Hawai'i"}


def _roles_fixture(prepared):
    def explanation(contribs, prior_weight, prior_contribution, k=8.0):
        return json.dumps(
            {
                "evidence_contributions": contribs,
                "k": k,
                "prior_contribution": prior_contribution,
                "prior_weight": prior_weight,
            }
        )

    def contrib(game_id, adj, exposure, contribution):
        return {
            "game_id": game_id,
            "source_week": 0,
            "raw_ppp": adj,
            "adjusted_ppp": adj,
            "adjusted_z": 1.5 * adj - 2.0,
            "exposure": exposure,
            "contribution": contribution,
            "available_utc": "2026-08-29T22:00:00+00:00",
            "missing_context_reason": None,
        }

    c1 = contrib(1, 3.0, 10.0, 0.9)
    cut = pd.Timestamp("2026-09-10T04:00:00Z")
    current = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 2,
                "game_id": None,
                "cutoff_utc": cut,
                "team": "Alpha",
                "unit_role": "offense",
                "rating_mean": 1.0 + 0.9,
                "rating_variance": 0.3,
                "prior_mean": 1.0,
                "prior_variance": 0.66,
                "usable_exposure": 10.0,
                "source_game_ids": "[1]",
                "explanation": explanation([c1], 0.4, 1.0),
            },
            {
                "season": 2026,
                "week": 2,
                "game_id": None,
                "cutoff_utc": cut,
                "team": "Hawai_i",
                "unit_role": "offense",
                "rating_mean": 0.2,
                "rating_variance": 0.5,
                "prior_mean": 0.2,
                "prior_variance": 0.5,
                "usable_exposure": 0.0,
                "source_game_ids": "[]",
                "explanation": explanation([], 1.0, 0.2),
            },
        ]
    )
    pregame = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": 2,
                "cutoff_utc": pd.Timestamp(KICK[1]),
                "team": "Alpha",
                "unit_role": "offense",
                "rating_mean": 1.9,
                "rating_variance": 0.3,
                "prior_mean": 1.0,
                "prior_variance": 0.66,
                "usable_exposure": 10.0,
                "source_game_ids": "[1]",
                "explanation": explanation([c1], 0.4, 1.0),
            }
        ]
    )
    priors = pd.DataFrame(
        [
            {
                "season": 2026,
                "team": "Alpha",
                "unit_role": "offense",
                "prior_mean": 1.0,
                "prior_variance": 0.66,
                "prior_source": "rho_0_60",
                "prior_source_season": 2025.0,
                "annual_decay_steps": 1,
                "fallback_reason": None,
            }
        ]
    )
    return priors, pregame, current


def test_components_decompose_priors_pregame_and_current_with_excluded_games():
    prepared, name_map = world()
    priors, pregame, current = _roles_fixture(prepared)
    comps = md.build_rating_components(
        run_id="run",
        manifest_sha256=SHA,
        candidate_id="cand",
        priors=priors,
        pregame_roles=pregame,
        current_roles=current,
        prepared=prepared,
        name_map=name_map,
        season=2026,
        preseason_cutoff=pd.Timestamp("2026-08-20T00:00:00Z"),
    )
    assert list(comps.columns) == list(md.COMPONENT_COLUMNS)
    ids = set(comps.component_id)
    assert ids == {
        "run:pregame:Alpha:preseason:offense",
        "run:pregame:Alpha:2:offense",
        "run:current:post-week-1:Alpha:offense",
        "run:current:post-week-1:Hawai_i:offense",
    }
    cur = comps[comps.component_id == "run:current:post-week-1:Alpha:offense"].iloc[0]
    # decomposition identity and weights
    assert cur.rating_mean == pytest.approx(
        cur.prior_contribution + sum(e["contribution"] for e in cur.evidence)
    )
    assert cur.prior_weight + cur.evidence_weight == pytest.approx(1.0)
    assert (
        cur.completed_games == 1
        and cur.snapshot_class == "current"
        and cur.as_of_week == 2
    )
    # game 2 (Alpha offense PPP unresolved) is excluded, with its reason; available after kickoff+6h
    assert cur.excluded_observations == [
        {"game_id": 2, "week": 1, "reason": "unresolved_scoring_attribution"}
    ]
    pre = comps[comps.component_id == "run:pregame:Alpha:2:offense"].iloc[0]
    assert (
        pre.game_id == 2 and pre.excluded_observations == []
    )  # game 2 not yet available pregame
    # legacy name: snapshot id uses the rating name, team column the game name
    hawaii = comps[
        comps.component_id == "run:current:post-week-1:Hawai_i:offense"
    ].iloc[0]
    assert hawaii.rating_team == "Hawai_i" and hawaii.team == "Hawai'i"
    season0 = comps[comps.component_id == "run:pregame:Alpha:preseason:offense"].iloc[0]
    assert (
        season0.prior_weight == 1.0
        and season0.evidence == []
        and season0.prior_detail["prior_source"] == "rho_0_60"
    )


def test_components_reject_source_ids_that_disagree_with_evidence():
    prepared, name_map = world()
    priors, pregame, current = _roles_fixture(prepared)
    current.loc[0, "source_game_ids"] = "[1, 99]"
    with pytest.raises(md.MatchupDataError, match="source_game_ids"):
        md.build_rating_components(
            run_id="run",
            manifest_sha256=SHA,
            candidate_id="c",
            priors=priors,
            pregame_roles=pregame,
            current_roles=current,
            prepared=prepared,
            name_map=name_map,
            season=2026,
            preseason_cutoff=pd.Timestamp("2026-08-20T00:00:00Z"),
        )


def test_fit_rating_scale_recovers_center_spread_sign():
    comps = pd.DataFrame(
        {
            "unit_role": ["offense", "defense"],
            "evidence": [
                [
                    {"adjusted_ppp": x, "adjusted_z": (x - 1.6) / 0.9}
                    for x in (1.0, 2.0, 3.0)
                ],
                [
                    {"adjusted_ppp": x, "adjusted_z": -(x - 2.0) / 1.2}
                    for x in (0.5, 1.5, 2.5)
                ],
            ],
        }
    )
    scale = md.fit_rating_scale(comps)
    assert scale["offense"]["center"] == pytest.approx(1.6)
    assert (
        scale["offense"]["spread"] == pytest.approx(0.9)
        and scale["offense"]["sign"] == 1.0
    )
    assert scale["defense"]["center"] == pytest.approx(2.0)
    assert (
        scale["defense"]["spread"] == pytest.approx(1.2)
        and scale["defense"]["sign"] == -1.0
    )
    assert max(v["max_residual"] for v in scale.values()) < 1e-12


def test_records_and_payload_hash_are_deterministic_and_sensitive():
    prepared, _ = world()
    log = md.build_game_log(
        prepared,
        fbs_names=FBS,
        measurement_manifest_sha256=MSHA,
        source_versions={"m": "x"},
    )
    payload = md.MatchupPayload(frames={"team_game_measurements": log})
    records = payload.records()["team_game_measurements"]
    assert len(records) == 96 and isinstance(records[0]["source_versions"], str)
    assert records[0]["kickoff_utc"].tzinfo is not None
    nan_row = next(r for r in records if r["coverage_status"] == "missing")
    assert nan_row["raw_value"] is None  # NaN becomes NULL
    first = md.payload_sha256({"team_game_measurements": records})
    shuffled = md.payload_sha256({"team_game_measurements": list(reversed(records))})
    assert first == shuffled and len(first) == 64
    changed = [dict(r) for r in records]
    changed[0]["numerator"] = (changed[0]["numerator"] or 0) + 1
    assert md.payload_sha256({"team_game_measurements": changed}) != first


def test_upsert_sql_shapes():
    assert "DO NOTHING" in md.upsert_sql("team_rating_components")
    sql = md.upsert_sql("team_possession_stats")
    assert "ON CONFLICT (season, as_of_week, team, role, metric) DO UPDATE" in sql
    assert "%(excluded)s::jsonb" in sql and "updated_at = NOW()" in sql
