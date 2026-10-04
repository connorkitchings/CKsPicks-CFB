"""The served V5 rating path fits ``ppp`` only: EPA observations cannot move it.

Behavioural proof: the intended-update rating states are identical, record for record, when
every non-PPP observation is removed, scrambled or made extreme, and they do change when a
PPP observation changes (so the test has power). Structural proof: the served modules import
the intended-update implementation and never the EPA candidates in the rating tournament.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings import possession_intended_update as piu

ROOT = Path(__file__).resolve().parents[1]
TEAMS = ("A", "B", "C", "D")
EPA_FAMILY = (
    "eligible_epa",
    "epa_per_possession",
    "ppa_per_play",
    "epa_pass",
    "epa_rush",
    "early_down_epa",
)


def _schedule():
    games = [
        (1, 101, "A", "B"),
        (1, 102, "C", "D"),
        (2, 201, "A", "C"),
        (2, 202, "B", "D"),
        (3, 301, "A", "D"),
        (3, 302, "B", "C"),
    ]
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": w,
                "game_id": g,
                "kickoff_utc": pd.Timestamp("2026-09-05T19:00:00Z")
                + pd.Timedelta(days=7 * (w - 1)),
                "home_team": h,
                "away_team": a,
            }
            for w, g, h, a in games
        ]
    )


def _observations(seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for game in _schedule().itertuples():
        for team, opponent in (
            (game.home_team, game.away_team),
            (game.away_team, game.home_team),
        ):
            for role in ("offense", "defense"):
                for measurement in (
                    "ppp",
                    "offensive_possession_points",
                    "non_offense_points",
                    *EPA_FAMILY,
                ):
                    denominator = float(rng.integers(8, 14))
                    numerator = float(rng.normal(2.0, 1.0)) * denominator
                    rows.append(
                        {
                            "season": 2026,
                            "week": game.week,
                            "game_id": game.game_id,
                            "kickoff_utc": game.kickoff_utc,
                            "team": team,
                            "opponent": opponent,
                            "measurement_id": measurement,
                            "unit_role": role,
                            "raw_value": numerator / denominator,
                            "numerator": numerator,
                            "denominator": denominator,
                            "coverage_status": "observed",
                        }
                    )
    return pd.DataFrame(rows)


def _priors():
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "team": t,
                "unit_role": r,
                "prior_mean": 0.1 * i,
                "prior_variance": 0.5,
            }
            for i, t in enumerate(TEAMS)
            for r in ("offense", "defense")
        ]
    )


def _terminal():
    return pd.DataFrame(
        columns=["season", "measurement_id", "unit_role", "adjusted_value"]
    )


def _states(observations):
    updater = piu.IntendedUpdate(
        schedule=_schedule(),
        observations=observations,
        priors=_priors(),
        historical_terminal=_terminal(),
    )
    pregame = updater.pregame()
    current = updater.current(post_week=2, cutoff_utc="2026-09-30T00:00:00Z")
    return pregame, current


def _record_hash(frame: pd.DataFrame) -> str:
    ordered = frame.sort_index(axis=1)
    text = ordered.to_json(orient="records", date_format="iso", double_precision=15)
    return hashlib.sha256(
        json.dumps(json.loads(text), sort_keys=True).encode()
    ).hexdigest()


def _hashes(observations):
    pregame, current = _states(observations)
    return (
        _record_hash(pregame.rating_states),
        _record_hash(pregame.team_states),
        _record_hash(current.rating_states),
        _record_hash(current.team_states),
    )


def test_the_served_measurement_is_ppp():
    assert piu.MEASUREMENT_ID == "ppp" and piu.CANDIDATE_ID.startswith("ppp__")


def test_removing_every_epa_observation_changes_nothing():
    base = _observations()
    ppp_only = base[~base.measurement_id.isin(EPA_FAMILY)]
    assert _hashes(base) == _hashes(ppp_only)


def test_scrambling_or_extreme_epa_values_changes_nothing():
    base = _observations()
    scrambled = base.copy()
    epa = scrambled.measurement_id.isin(EPA_FAMILY)
    scrambled.loc[epa, ["numerator", "raw_value"]] = [999.0, 999.0]
    assert _hashes(base) == _hashes(scrambled)


def test_withholding_epa_as_missing_changes_nothing():
    base = _observations()
    withheld = base.copy()
    epa = withheld.measurement_id.isin(EPA_FAMILY)
    withheld.loc[epa, ["numerator", "raw_value", "denominator"]] = np.nan
    withheld.loc[epa, "coverage_status"] = "missing"
    assert _hashes(base) == _hashes(withheld)


def test_the_other_scoring_observations_do_not_feed_the_rating_either():
    base = _observations()
    trimmed = base[base.measurement_id.eq("ppp")]
    assert _hashes(base) == _hashes(trimmed)


def test_the_test_has_power_a_ppp_change_does_move_the_state():
    base = _observations()
    changed = base.copy()
    row = changed.index[
        (changed.measurement_id == "ppp")
        & (changed.game_id == 101)
        & (changed.team == "A")
        & (changed.unit_role == "offense")
    ][0]
    changed.loc[row, ["numerator", "raw_value"]] = [
        changed.loc[row, "numerator"] + 20.0,
        changed.loc[row, "raw_value"] + 20.0 / changed.loc[row, "denominator"],
    ]
    assert _hashes(base) != _hashes(changed)


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def test_the_served_path_imports_the_intended_update_and_never_the_epa_candidates():
    served = [
        "scripts/pipeline/build_v5_intended_update_2026.py",
        "scripts/pipeline/build_v5_intended_update_forecasts.py",
        "scripts/pipeline/publish_v5_intended_update_ratings.py",
    ]
    for relative in served:
        imports = _imports(ROOT / relative)
        assert any("possession_intended_update" in name for name in imports), relative
        assert not any("possession_rating_tournament" in name for name in imports), (
            relative
        )
    implementation = _imports(
        ROOT / "src/cks_picks_cfb/ratings/possession_intended_update.py"
    )
    assert not any("possession_rating_tournament" in name for name in implementation)
    assert not any(
        "epa" in name.lower()
        for name in implementation
        if name.startswith("cks_picks_cfb")
    )


def test_the_rating_builder_records_the_intended_update_parent_chain():
    text = (ROOT / "scripts/pipeline/build_v5_intended_update_2026.py").read_text()
    for parent in (
        "accepted_rating_manifest_sha256",
        "historical_measurement_manifest_sha256",
        "measurement_manifest_sha256",
        "source_lock_sha256",
    ):
        assert parent in text
    # The builder names the PPP candidate it builds, the same one the updater defines.
    assert piu.CANDIDATE_ID in text
