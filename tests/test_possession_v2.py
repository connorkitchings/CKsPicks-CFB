"""Provider-keyed possession ledger: builder, independent verifier and the tie rule.

Contract 2026-10-09/01, Task 4.2-4.3. The builder and the verifier are separate
implementations; every scenario must give identical frames from both.
"""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_possession_v2 import (
    POSSESSION_COLUMNS_V2,
    SCORING_EVENT_COLUMNS_V2,
    is_event_id_v2,
)
from cks_picks_cfb.data.play_identity import PlayIdentityError
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.features.byplay.enrichment import allplays_to_byplay
from cks_picks_cfb.ratings import possession_measurements as producer
from cks_picks_cfb.ratings.possession_verification import (
    IndependentPossessionError,
    reconstruct_measurements,
)

SEASON, GAME = 2025, 1


def p(drive, number, play_id, osc, dsc, *, offense="A", quarter=1, kind="Rush", **kw):
    defense = "B" if offense == "A" else "A"
    row = {
        "season": SEASON,
        "week": 6,
        "game_id": GAME,
        "offense": offense,
        "defense": defense,
        "play_number": number,
        "drive_number": drive,
        "quarter": quarter,
        "down": 1,
        "yards_to_first": 10,
        "yards_to_goal": 60,
        "yards_gained": 5,
        "yard_line": 40,
        "adj_yd_line": 60,
        "offense_score": osc,
        "defense_score": dsc,
        "play_type": kind,
        "play_text": "",
        "ppa": 0.1,
        "scoring": 0,
        "turnover": 0,
        "penalty": 0,
        "offense_timeouts": 3,
        "defense_timeouts": 3,
        "play_id": play_id,
        "drive_id": 1000 + drive,
    }
    row.update(kw)
    return row


def base_rows() -> list[dict]:
    """A scores 6+1, B scores a field goal, A scores a touchdown: A 13, B 3."""
    return [
        p(1, 1, 11, 0, 0),
        p(1, 2, 12, 6, 0, kind="Rushing Touchdown", scoring=1),
        p(1, 3, 13, 7, 0, kind="Extra Point Good"),
        p(2, 1, 21, 0, 7, offense="B"),
        p(2, 2, 22, 3, 7, offense="B", kind="Field Goal Good", scoring=1),
        p(3, 1, 31, 7, 3),
        p(3, 2, 32, 13, 3, kind="Rushing Touchdown", scoring=1),
    ]


def population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                season=SEASON,
                week=6,
                game_id=GAME,
                kickoff_utc="2025-10-04T18:00:00Z",
                home_team="A",
                away_team="B",
                schedule_completed=True,
                outcome_valid=True,
                forecast_eligible=True,
                measurement_usable=True,
            )
        ]
    )


def outcomes(a=13.0, b=3.0) -> pd.DataFrame:
    return pd.DataFrame(
        [dict(season=SEASON, game_id=GAME, home_points=a, away_points=b)]
    )


def v2_frame(rows: list[dict]) -> pd.DataFrame:
    return allplays_to_byplay(
        pd.DataFrame(rows), nullable_ppa=True, play_identity="byplay_v2"
    )


def build(rows, **kw):
    frame = v2_frame(rows)
    return frame, producer.build_measurements(
        byplay=frame,
        population=population(),
        outcomes=outcomes(**kw),
        play_identity="byplay_v2",
    )


def events(result) -> pd.DataFrame:
    return result.scoring_events.set_index(["team", "source_play_id"])


def agree(rows, **kw):
    """Run the builder and the independent verifier; they must produce identical frames."""
    frame, built = build(rows, **kw)
    checked = reconstruct_measurements(
        byplay=frame,
        outcomes=outcomes(**kw),
        population=population(),
        play_identity="byplay_v2",
    )
    for name in ("possessions", "scoring_events", "observations", "coverage"):
        pd.testing.assert_frame_equal(
            getattr(built, name), getattr(checked, name), check_dtype=False
        )
    return frame, built


def scenario_rows() -> dict[str, list[dict]]:
    base = base_rows()
    neutral = [*base, p(3, 1, 33, 7, 3)]  # distinct play tied with 31, same scores
    td_and_admin = [*base, p(3, 2, 34, 13, 3, kind="Pass Incompletion")]
    disagree = [
        *base[:-1],
        p(3, 2, 34, 7, 3),  # tied with the touchdown but shows the pre-score
        base[-1],
        p(4, 1, 41, 19, 3, kind="Rushing Touchdown", scoring=1),  # next A event
    ]
    overtime = [
        *base,
        p(9, 1, 92, 13, 3, quarter=5),  # tied with the field goal, shows the pre-score
        p(9, 1, 91, 16, 3, quarter=5, kind="Field Goal Good", scoring=1),
    ]
    dead_twin = [*base, p(3, 2, 35, 13, 3, kind="End of Game")]
    cross_period = [*base, p(3, 1, 93, 3, 13, offense="B", quarter=5, drive_id=-999)]
    return {
        "no_ties": base,
        "neutral_tie": neutral,
        "touchdown_tied_with_admin_row": td_and_admin,
        "tie_members_disagree": disagree,
        "overtime_tie": overtime,
        "dead_play_tied": dead_twin,
        "cross_period_reuse": cross_period,
    }


SCENARIOS = scenario_rows()


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_builder_and_independent_verifier_agree(name):
    agree(SCENARIOS[name])


def test_identities_are_provider_keyed_and_validate():
    _, result = agree(SCENARIOS["no_ties"])
    assert tuple(result.possessions.columns) == POSSESSION_COLUMNS_V2
    assert tuple(result.scoring_events.columns) == SCORING_EVENT_COLUMNS_V2
    assert all(is_event_id_v2(i) for i in result.scoring_events["source_event_id"])
    assert set(result.scoring_events["source_event_id"]) == {
        f"{SEASON}:{GAME}:{i}" for i in ("12", "13", "22", "32")
    }
    assert result.possessions["drive_id"].tolist() == ["1001", "1002", "1003"]
    validate_frame(
        result.possessions,
        schema_for("possession_ledger", "data_first_possession_possession_v2"),
    )
    validate_frame(
        result.scoring_events,
        schema_for(
            "possession_scoring_event", "data_first_possession_scoring_event_v2"
        ),
    )
    validate_frame(
        result.observations,
        schema_for("possession_observation", "data_first_possession_observation_v2"),
    )


def v1_equivalent(rows):
    """The same plays through the v1 sequence identity."""
    return producer.build_measurements(
        byplay=allplays_to_byplay(pd.DataFrame(rows), nullable_ppa=True),
        population=population(),
        outcomes=outcomes(),
    )


def test_without_ties_v2_matches_v1_apart_from_the_identity_strings():
    _, v2 = agree(SCENARIOS["no_ties"])
    v1 = v1_equivalent(SCENARIOS["no_ties"])
    pd.testing.assert_frame_equal(v1.observations, v2.observations, check_dtype=False)
    pd.testing.assert_frame_equal(v1.coverage, v2.coverage, check_dtype=False)
    keep = [
        "team",
        "score_increment",
        "scoring_category",
        "unit_category",
        "quality_reason",
    ]
    pd.testing.assert_frame_equal(
        v1.scoring_events[keep], v2.scoring_events[keep], check_dtype=False
    )
    shared = [c for c in v1.possessions.columns if c != "source_play_ids"]
    pd.testing.assert_frame_equal(
        v1.possessions[shared], v2.possessions[shared], check_dtype=False
    )


def test_a_neutral_tie_changes_nothing_in_the_ledger():
    _, base = agree(SCENARIOS["no_ties"])
    frame, tied = agree(SCENARIOS["neutral_tie"])
    assert frame["play_order_unresolved"].sum() == 2  # 31 and 33 are flagged on byplay
    keep = [
        "team",
        "source_event_id",
        "score_increment",
        "scoring_category",
        "quality_reason",
    ]
    pd.testing.assert_frame_equal(
        base.scoring_events[keep], tied.scoring_events[keep], check_dtype=False
    )
    assert (tied.scoring_events["quality_reason"] != "unresolved_play_order").all()


def test_a_tie_that_carries_a_score_change_is_unresolved_and_disclosed():
    _, result = agree(SCENARIOS["touchdown_tied_with_admin_row"])
    flagged = result.scoring_events[
        result.scoring_events["quality_reason"] == "unresolved_play_order"
    ]
    assert flagged["source_play_id"].tolist() == ["32"]
    row = flagged.iloc[0]
    assert (row.scoring_category, row.unit_category) == ("unresolved", "unknown")
    assert row.score_increment == 6  # the points are kept so the game total reconciles
    assert pd.isna(row.associated_possession_id)
    a = result.observations
    ppp = a[(a.team == "A") & (a.measurement_id == "ppp") & (a.unit_role == "offense")]
    assert ppp["coverage_status"].iloc[0] == "missing"
    assert ppp["missing_reason"].iloc[0] == "unresolved_scoring_attribution"
    epa = a[
        (a.team == "A")
        & (a.measurement_id == "eligible_epa")
        & (a.unit_role == "offense")
    ]
    assert epa["coverage_status"].iloc[0] == "observed"  # EPA does not depend on order


def test_members_that_disagree_also_taint_the_next_event_of_those_teams():
    _, result = agree(SCENARIOS["tie_members_disagree"], a=19.0)
    flagged = result.scoring_events.set_index("source_play_id")["quality_reason"]
    assert flagged["32"] == "unresolved_play_order"
    assert flagged["41"] == "unresolved_play_order"  # the next A event after the group
    assert flagged["12"] != "unresolved_play_order"  # earlier events are untouched


def test_an_overtime_tie_never_touches_regulation_measurements():
    _, base = agree(SCENARIOS["no_ties"])
    frame, result = agree(SCENARIOS["overtime_tie"], a=16.0)
    overtime = result.scoring_events[
        result.scoring_events["period_class"] == "overtime"
    ]
    assert overtime["scoring_category"].tolist() == ["overtime"]  # category is kept
    assert overtime["quality_reason"].tolist() == ["unresolved_play_order"]
    assert overtime["unit_category"].tolist() == ["unknown"]
    regulation = ~result.scoring_events["period_class"].eq("overtime")
    assert (
        result.scoring_events.loc[regulation, "quality_reason"]
        != "unresolved_play_order"
    ).all()
    ppp = result.observations
    ppp = ppp[(ppp.measurement_id == "ppp") & (ppp.unit_role == "offense")]
    assert (ppp["coverage_status"] == "observed").all()


def test_a_tied_dead_play_is_not_a_reorderable_pair():
    frame, result = agree(SCENARIOS["dead_play_tied"])
    assert frame["play_order_unresolved"].sum() == 2  # flagged on byplay for disclosure
    assert (result.scoring_events["quality_reason"] != "unresolved_play_order").all()


def test_drive_ids_keep_a_reused_drive_number_apart():
    frame, result = agree(SCENARIOS["cross_period_reuse"])
    assert not frame["play_order_unresolved"].any()
    reused = result.possessions[result.possessions["drive_number"] == 3]
    assert sorted(reused["drive_id"]) == ["-999", "1003"]
    assert reused["offense"].nunique() == 2


def test_the_wrong_identity_for_a_frame_is_refused():
    v2 = v2_frame(SCENARIOS["no_ties"])
    v1 = allplays_to_byplay(pd.DataFrame(SCENARIOS["no_ties"]), nullable_ppa=True)
    with pytest.raises(
        producer.PossessionMeasurementError, match="needs play_identity"
    ):
        producer.build_possession_ledger(byplay=v2, population=population())
    with pytest.raises(PlayIdentityError, match="requires byplay_v2"):
        producer.build_possession_ledger(
            byplay=v1, population=population(), play_identity="byplay_v2"
        )
    with pytest.raises(IndependentPossessionError, match="needs play_identity"):
        reconstruct_measurements(
            byplay=v2, outcomes=outcomes(), population=population()
        )
    with pytest.raises(IndependentPossessionError, match="byplay_v2"):
        reconstruct_measurements(
            byplay=v1,
            outcomes=outcomes(),
            population=population(),
            play_identity="byplay_v2",
        )
    with pytest.raises(
        producer.PossessionMeasurementError, match="unknown play identity"
    ):
        producer.build_possession_ledger(
            byplay=v1, population=population(), play_identity="byplay_v3"
        )


def test_the_verifier_rejects_tampered_order_flags():
    frame = v2_frame(SCENARIOS["neutral_tie"])
    forged = frame.assign(play_order_reason=None, play_order_unresolved=False)
    with pytest.raises(
        IndependentPossessionError, match="disagree with the recomputed ties"
    ):
        reconstruct_measurements(
            byplay=forged,
            outcomes=outcomes(),
            population=population(),
            play_identity="byplay_v2",
        )


def test_v1_error_path_for_duplicate_stable_source_play_ids():
    """The v1 duplicate guard had no test; pin it before v2 sits beside it."""
    v1 = allplays_to_byplay(pd.DataFrame(base_rows()), nullable_ppa=True)
    duplicated = pd.concat([v1, v1.iloc[[0]]], ignore_index=True)
    with pytest.raises(
        producer.PossessionMeasurementError, match="duplicate stable source play IDs"
    ):
        producer.build_possession_ledger(byplay=duplicated, population=population())
    with pytest.raises(IndependentPossessionError, match="duplicate stable play keys"):
        reconstruct_measurements(
            byplay=duplicated, outcomes=outcomes(), population=population()
        )


def test_an_injected_v2_ledger_must_be_unique_on_the_provider_drive():
    frame, built = build(SCENARIOS["no_ties"])
    repeated = pd.concat(
        [built.possessions, built.possessions.iloc[[0]]], ignore_index=True
    )
    with pytest.raises(producer.PossessionMeasurementError, match="repeat an identity"):
        producer.build_measurements(
            byplay=frame,
            population=population(),
            outcomes=outcomes(),
            possessions=repeated,
            scoring_events=built.scoring_events,
            play_identity="byplay_v2",
        )
    again = producer.build_measurements(
        byplay=frame,
        population=population(),
        outcomes=outcomes(),
        possessions=built.possessions,
        scoring_events=built.scoring_events,
        play_identity="byplay_v2",
    )
    pd.testing.assert_frame_equal(
        built.observations, again.observations, check_dtype=False
    )


# --- the R1 envelope accepts provider-keyed plays (Task 4.5) ---------------------------


def test_the_r1_envelope_matches_v1_when_no_play_is_tied():
    from cks_picks_cfb.ratings import score_envelope_r1 as r1

    rows = SCENARIOS["no_ties"]
    finals = {(GAME, "A"): 13.0, (GAME, "B"): 3.0}
    v2_plays = v2_frame(rows)
    v1_plays = allplays_to_byplay(pd.DataFrame(rows), nullable_ppa=True)
    new, unresolved_v2 = r1.apply_r1(v2_plays, finals)
    old, unresolved_v1 = r1.apply_r1(v1_plays, finals)
    assert unresolved_v1 == unresolved_v2
    keep = ["drive_number", "play_number", "offense_score", "defense_score"]
    pd.testing.assert_frame_equal(
        old[keep].reset_index(drop=True),
        new[keep].reset_index(drop=True),
        check_dtype=False,
    )
    assert r1.restoration_jumps(v2_plays) == r1.restoration_jumps(v1_plays)


def test_streams_with_a_tied_play_are_left_unchanged_and_reported_unresolved():
    from cks_picks_cfb.ratings import score_envelope_r1 as r1

    plays_v2 = v2_frame(SCENARIOS["touchdown_tied_with_admin_row"])
    finals = {(GAME, "A"): 13.0, (GAME, "B"): 3.0}
    out, unresolved = r1.apply_r1(plays_v2, finals)
    assert unresolved == {(GAME, "A"), (GAME, "B")}
    ordered = plays_v2.sort_values(r1.ORDER_COLUMNS, kind="mergesort")
    pd.testing.assert_series_equal(
        ordered["offense_score"].reset_index(drop=True),
        out["offense_score"].reset_index(drop=True),
        check_dtype=False,
    )
    assert r1.restoration_jumps(plays_v2) == set()  # tied streams are skipped
