"""Gold converters, contracts and lineage for provider-keyed identity (contract 2026-10-09/01, Task 4.4)."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.play_identity import lineage_problem
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.features.aggregations.drives import aggregate_drives
from cks_picks_cfb.metrics import contracts as gc
from cks_picks_cfb.metrics import ledger as ml
from tests.test_possession_v2 import GAME, SCENARIOS, SEASON, build

VERSIONS = {"byplay": "byplay_v2"}
FINALS = {(GAME, "A"): 13.0, (GAME, "B"): 3.0}


def gold(name: str, **kw):
    rows = SCENARIOS[name]
    frame, result = build(rows, **kw)
    drives = aggregate_drives(frame, schema_version="drives_v2").merge(
        frame[["game_id", "season", "week"]].drop_duplicates(), on="game_id", how="left"
    )
    possessions = ml.possessions_to_v2(
        result.possessions, drives, source_versions=VERSIONS
    )
    return frame, result, drives, possessions


def test_possessions_gain_v2_ids_and_validate():
    _, _, _, possessions = gold("no_ties")
    validate_frame(
        possessions, schema_for("football_possessions", "football_possessions_v2")
    )
    assert gc.possessions_v2_problems(possessions) == []
    first = possessions.iloc[0]
    assert first.possession_id == gc.possession_id_for_v2(SEASON, GAME, "1001", "A")
    assert first.possession_id != gc.possession_id_for(SEASON, GAME, 1, "A")
    assert first.start_yards_to_goal is not None and first.scoring_opportunity in (
        True,
        False,
    )


def test_a_reused_drive_number_gives_two_possessions_not_one():
    _, _, _, possessions = gold("cross_period_reuse")
    reused = possessions[possessions["drive_number"] == 3]
    assert len(reused) == 2 and reused["possession_id"].nunique() == 2
    assert gc.possessions_v2_problems(possessions) == []


def test_a_possession_without_a_drive_row_keeps_nulls():
    _, result, drives, _ = gold("no_ties")
    thin = drives[drives["drive_id"] != "1002"]
    out = ml.possessions_to_v2(result.possessions, thin, source_versions=VERSIONS)
    row = out[out["drive_id"] == "1002"].iloc[0]
    assert pd.isna(row.start_yards_to_goal) and row.scoring_opportunity is None


def test_converters_need_v2_inputs_and_v1_converters_refuse_them():
    frame, result, drives, possessions = gold("no_ties")
    with pytest.raises(ml.LedgerConversionError, match="needs v2 possessions"):
        ml.possessions_to_v2(
            result.possessions.drop(columns="drive_id"),
            drives,
            source_versions=VERSIONS,
        )
    with pytest.raises(ml.LedgerConversionError, match="provider-keyed v2 frames"):
        ml.possessions_to_v1(result.possessions, drives, source_versions=VERSIONS)
    with pytest.raises(ml.LedgerConversionError, match="provider-keyed v2 frames"):
        ml.scoring_events_to_v1(
            result.scoring_events, frame, finals=FINALS, source_versions=VERSIONS
        )
    v1_events = result.scoring_events.assign(source_event_id="2025:1:1:2")
    with pytest.raises(ml.LedgerConversionError, match="v2 event ids"):
        ml.scoring_events_to_v2(
            v1_events, frame, finals=FINALS, source_versions=VERSIONS
        )


def test_events_convert_to_a_valid_v2_ledger():
    frame, result, _, possessions = gold("no_ties")
    ledger = ml.scoring_events_to_v2(
        result.scoring_events, frame, finals=FINALS, source_versions=VERSIONS
    )
    validate_frame(
        ledger, schema_for("football_scoring_ledger", "football_scoring_ledger_v2")
    )
    assert gc.scoring_ledger_v2_problems(ledger, possessions) == []
    assert set(ledger.admission) == {"baseline_unchanged"}
    touchdown = ledger[(ledger.team == "A") & (ledger.source_play_id == "12")].iloc[0]
    assert touchdown.source_event_id == f"{SEASON}:{GAME}:12"
    assert touchdown.associated_possession_id == gc.possession_id_for_v2(
        SEASON, GAME, "1001", "A"
    )
    assert touchdown.raw_score_before == 0.0 and touchdown.raw_score_after == 6.0


def test_an_unresolved_play_order_marker_gets_a_null_increment_and_no_asserted_before():
    frame, result, _, possessions = gold("touchdown_tied_with_admin_row")
    ledger = ml.scoring_events_to_v2(
        result.scoring_events, frame, finals=FINALS, source_versions=VERSIONS
    )
    marker = ledger[ledger.source_play_id == "32"].iloc[0]
    assert marker.scoring_category == "unresolved" and pd.isna(marker.score_increment)
    assert marker.quality_reason == "unresolved_play_order"
    assert pd.isna(marker.raw_score_before)  # the order of the tied plays is unknown
    assert not pd.isna(marker.raw_score_after)
    assert gc.scoring_ledger_v2_problems(ledger, possessions) == []


def admitted(ledger_events, frame, finals=FINALS):
    groups = {
        (GAME, e.team, e.source_event_id): f"g:{e.team}"
        for e in ledger_events.itertuples()
    }
    return ml.scoring_events_to_v2(
        ledger_events,
        frame,
        finals=finals,
        source_versions=VERSIONS,
        groups=groups,
        admitted_evidence={"g:A": ("e1",), "g:B": ("e2",)},
        admitted_rule_version="r1_envelope_v2",
        populate_envelopes=True,
    )


def test_envelopes_are_asserted_without_ties_and_stop_at_a_tied_play():
    frame, result, _, _ = gold("no_ties")
    clean = admitted(result.scoring_events, frame)
    a = clean[clean.team == "A"].sort_values("source_play_id")
    assert a["envelope_after"].notna().all()
    assert a.iloc[-1].envelope_after == 13

    frame, result, _, _ = gold("touchdown_tied_with_admin_row")
    tied = admitted(result.scoring_events, frame)
    a = tied[tied.team == "A"].set_index("source_play_id")
    assert pd.isna(a.loc["32", "envelope_after"])  # the tied play stops the envelope


def test_possession_ids_never_collide_across_identity_versions():
    assert gc.possession_id_for_v2(2025, 1, "1001", "A") != gc.possession_id_for(
        2025, 1, 1001, "A"
    )
    assert gc.possession_id_for_v2(2025, 1, "-999", "A") != gc.possession_id_for_v2(
        2025, 1, "999", "A"
    )


def test_contract_checks_catch_a_forged_v2_ledger():
    frame, result, _, possessions = gold("no_ties")
    ledger = ml.scoring_events_to_v2(
        result.scoring_events, frame, finals=FINALS, source_versions=VERSIONS
    )
    forged = ledger.assign(
        source_event_id=ledger["source_event_id"].str.replace("2025:1:", "2025:1:9")
    )
    assert any(
        "disagrees with source_play_id" in p
        for p in gc.scoring_ledger_v2_problems(forged, possessions)
    )
    legacy = ledger.assign(source_event_id="2025:1:1:2")
    assert any(
        "not a v2 event id" in p
        for p in gc.scoring_ledger_v2_problems(legacy, possessions)
    )
    bad_possessions = possessions.assign(possession_id="deadbeef")
    assert any(
        "not the deterministic v2 id" in p
        for p in gc.possessions_v2_problems(bad_possessions)
    )


@pytest.mark.parametrize(
    ("dataset", "version"),
    [
        ("drives", "drives_v2"),
        ("possession_ledger", "data_first_possession_possession_v2"),
        ("possession_scoring_event", "data_first_possession_scoring_event_v2"),
        ("possession_observation", "data_first_possession_observation_v2"),
        ("football_possessions", "football_possessions_v2"),
        ("football_scoring_ledger", "football_scoring_ledger_v2"),
        ("scoring_attribution_evidence", "scoring_attribution_evidence_v2"),
    ],
)
def test_every_v2_version_refuses_each_superseded_parent(dataset, version):
    superseded = [
        {"dataset": "byplay", "schema_version": "byplay_v1"},
        {"dataset": "drives", "schema_version": "drives_v1"},
        {
            "dataset": "possession_ledger",
            "schema_version": "data_first_possession_possession_v1",
        },
        {
            "dataset": "possession_scoring_event",
            "schema_version": "data_first_possession_scoring_event_v1",
        },
        {
            "dataset": "possession_observation",
            "schema_version": "data_first_possession_observation_v1",
        },
        {
            "dataset": "football_possessions",
            "schema_version": "football_possessions_v1",
        },
        {
            "dataset": "football_scoring_ledger",
            "schema_version": "football_scoring_ledger_v1",
        },
        {
            "dataset": "scoring_attribution_evidence",
            "schema_version": "scoring_attribution_evidence_v1",
        },
    ]
    for parent in superseded:
        assert "superseded" in lineage_problem(dataset, version, [parent])
    ok = [
        {
            "dataset": "possession_population",
            "schema_version": "data_first_possession_population_v1",
        }
    ]
    assert lineage_problem(dataset, version, ok) is None


def test_v1_builds_may_still_use_v1_parents():
    parent = [{"dataset": "byplay", "schema_version": "byplay_v1"}]
    assert (
        lineage_problem(
            "possession_ledger", "data_first_possession_possession_v1", parent
        )
        is None
    )
