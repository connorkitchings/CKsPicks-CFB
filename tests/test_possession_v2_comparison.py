import pandas as pd

from scripts.analysis.possession_v2_comparison import compare_events


def events(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "source_event_id",
            "team",
            "score_increment",
            "scoring_category",
            "unit_category",
            "quality_reason",
        ],
    )


ID_MAP = {
    "2025:1:3:1": "2025:1:900",
    "2025:1:3:2": "2025:1:901",
    "2025:2:1:1": "2025:2:7",
}


def test_matching_events_compare_equal_and_missing_reasons_are_not_differences():
    v1 = events(
        [("2025:1:3:1", "A", 6, "eligible_regulation_offense", "offense", None)]
    )
    v2 = events(
        [("2025:1:900", "A", 6, "eligible_regulation_offense", "offense", None)]
    )
    result = compare_events(v1, v2, ID_MAP)
    assert result["shared_events"] == 1 and result["shared_events_differing"] == 0
    assert result["only_v1"] == [] and result["only_v2"] == []


def test_a_changed_event_is_reported_with_its_game():
    v1 = events(
        [("2025:1:3:1", "A", 6, "eligible_regulation_offense", "offense", None)]
    )
    v2 = events(
        [("2025:1:900", "A", 6, "unresolved", "unknown", "unresolved_play_order")]
    )
    result = compare_events(v1, v2, ID_MAP)
    assert result["shared_events_differing"] == 1 and result[
        "shared_differing_games"
    ] == [1]


def test_one_sided_events_are_listed_with_their_games_and_points():
    v1 = events(
        [("2025:1:3:2", "A", 0, "unresolved", "unknown", "impossible_score_increment")]
    )
    v2 = events(
        [
            ("2025:1:555", "A", 3, "regulation_non_offense", "non_offense", None),
            ("2025:2:7", "B", 0, "unresolved", "unknown", "impossible_score_increment"),
        ]
    )
    result = compare_events(v1, v2, ID_MAP)
    assert result["only_v1"] == ["2025:1:901|A"]
    assert result["only_v2"] == ["2025:1:555|A", "2025:2:7|B"]
    assert result["one_sided_games"] == [1, 2]
    assert result["one_sided_points"] == 3


def test_v1_events_at_an_unmappable_sequence_are_counted_not_compared():
    v1 = events([("2025:1:19:4", "A", 0, "unresolved", "unknown", "x")])
    result = compare_events(v1, events([]), ID_MAP)
    assert result["unmapped_v1_events"] == 1 and result["shared_events"] == 0
