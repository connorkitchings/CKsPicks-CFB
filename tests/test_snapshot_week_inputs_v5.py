"""V5 serving snapshots do not depend on V4 model-ready Gold features."""

from scripts.pipeline.snapshot_week_inputs import required_inputs


def test_v5_snapshot_ref_roles_exclude_v4_features():
    v5 = required_inputs(v5_mode=True)
    v4 = required_inputs(v5_mode=False)
    assert ("games", "games") in v5
    assert ("betting_lines", "market_snapshots") in v5
    assert ("point_in_time_matchups", "point_in_time_matchups") not in v5
    assert ("point_in_time_matchups", "point_in_time_matchups") in v4
