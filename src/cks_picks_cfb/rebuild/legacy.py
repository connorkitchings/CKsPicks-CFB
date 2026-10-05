"""Legacy Step 5 helpers used only by the baseline-reproduction and comparison stages.

Copied verbatim (apart from the exception class) from
``scripts/research/run_data_first_possession_measurements.py`` (``_ref``,
``_concat_source_frames``, ``_repair``, ``_sources``) and
``scripts/analysis/build_admitted_ledger_5c.py`` (``_finals``, ``_evidence_ids``,
``_materiality``), so library code does not import research or script namespaces. Any
divergence from the originals would break the byte-identical Step 5 reproduction gate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest
from cks_picks_cfb.data.data_first_possession_v1 import (
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
)
from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.ratings import admission as adm
from cks_picks_cfb.rebuild.errors import GateError


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: value[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def _concat_source_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate source seasons with explicit all-null dtype handling."""
    if not frames:
        return pd.DataFrame()
    columns = list(dict.fromkeys(column for frame in frames for column in frame))
    unstable = {
        column
        for column in columns
        if len({str(frame[column].dtype) for frame in frames if column in frame}) > 1
        and any(column in frame and frame[column].isna().all() for frame in frames)
    }
    normalized = [
        frame.astype({column: "object" for column in unstable if column in frame})
        for frame in frames
    ]
    return pd.concat(normalized, ignore_index=True)


def _repair(
    storage: Any, uri: str, *, scope: str = "historical", config: Mapping | None = None
) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if scope == "season_2026":
        raise GateError("the 2026 scope is not part of the legacy baseline")
    if raw_sha != REQUIRED_REPAIR_RAW_SHA256:
        raise GateError("Repair manifest raw checksum is not the approved parent")
    payload = verify_repair_manifest(json.loads(raw))
    if payload.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise GateError("Repair manifest canonical checksum is not the approved parent")
    return payload, raw_sha


def _sources(
    storage: Any, repair: Mapping[str, Any], *, scope: str = "historical"
) -> dict[int, dict[str, DatasetRef]]:
    if scope == "season_2026":
        raise GateError("the 2026 scope is not part of the legacy baseline")
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise GateError("Repair manifest does not bind core eligibility")
    result: dict[int, dict[str, DatasetRef]] = {}
    for value in verify_core_eligibility(json.loads(storage.read_bytes(str(uri)))):
        season = int(value["season"])
        result.setdefault(season, {})[str(value["dataset"])] = _ref(value)
    if any({"byplay", "game_outcomes"} - set(refs) for refs in result.values()):
        raise GateError("Repair core sources lack byplay or outcome evidence")
    return result


def _finals(population: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    scores = population
    if "home_points" not in population.columns:
        scores = population.merge(
            outcomes[
                ["season", "game_id", "home_points", "away_points"]
            ].drop_duplicates(["season", "game_id"]),
            on=["season", "game_id"],
            how="left",
        )
    finals = {}
    for row in scores.itertuples(index=False):
        if getattr(row, "outcome_valid", False):
            if pd.notna(row.home_points):
                finals[(int(row.game_id), str(row.home_team))] = float(row.home_points)
            if pd.notna(row.away_points):
                finals[(int(row.game_id), str(row.away_team))] = float(row.away_points)
    return finals


def _evidence_ids(
    cfbd_dir: Path, decisions: pd.DataFrame
) -> dict[str, tuple[str, ...]]:
    """One deterministic evidence id per admitted group, tied to the retained bundle hash."""
    manifest = [
        json.loads(line)
        for line in (cfbd_dir / "manifest.jsonl").read_text().splitlines()
        if line.strip()
    ]
    game_bundle: dict[int, str] = {}
    for record in manifest:
        for row in json.loads((cfbd_dir / "raw" / record["file"]).read_bytes()):
            game_bundle[int(row["gameId"])] = record["sha256"]
    out: dict[str, tuple[str, ...]] = {}
    for row in decisions[decisions["decision"] == adm.ADMITTED].itertuples(index=False):
        sha = game_bundle[int(row.game_id)]
        digest = hashlib.sha256(f"{row.group_id}|{sha}".encode()).hexdigest()[:20]
        out[row.group_id] = (f"cfbd_drives:{digest}",)
    return out


FULL_SEASON_POSSESSIONS = 60  # FCS teams in FBS-involved games have far fewer


def _materiality(
    base_events: pd.DataFrame, admitted: pd.DataFrame, possessions: pd.DataFrame
) -> dict:
    """Raw PPP and raw PPP rank deltas on the admitted output (adjusted/state deltas: 6A).

    Reported for every team-season and for team-seasons with at least
    ``FULL_SEASON_POSSESSIONS`` eligible possessions; the small samples are mostly FCS teams
    that appear in one or two FBS-involved games, where one touchdown moves PPP by 0.5+.
    """
    reg = possessions[
        (possessions["period_class"] == "regulation")
        & possessions["possession_eligible"].fillna(False).astype(bool)
        & possessions["quality_reason"].isna()
    ]
    n = reg.groupby(["season", "offense"]).size().rename("n")

    def ppp(events: pd.DataFrame) -> pd.Series:
        pts = (
            events[events["scoring_category"] == "eligible_regulation_offense"]
            .groupby(["season", "team"])["score_increment"]
            .sum()
        )
        pts.index.names = ["season", "offense"]
        return (pts / n).dropna()

    before, after = ppp(base_events), ppp(admitted)
    both = pd.concat([before.rename("b"), after.rename("a"), n], axis=1).dropna()
    both["delta"] = both["a"] - both["b"]
    both["rank_b"] = both.groupby("season")["b"].rank(ascending=False, method="min")
    both["rank_a"] = both.groupby("season")["a"].rank(ascending=False, method="min")
    both["rank_delta"] = (both["rank_a"] - both["rank_b"]).abs()

    def summary(frame: pd.DataFrame) -> dict:
        return {
            "team_seasons": len(frame),
            "raw_ppp_changed": int((frame["delta"].abs() > 1e-12).sum()),
            "raw_ppp_delta_gt_0_05": int((frame["delta"].abs() > 0.05).sum()),
            "max_abs_raw_ppp_delta": round(float(frame["delta"].abs().max()), 5),
            "raw_rank_move_gt_5": int((frame["rank_delta"] > 5).sum()),
            "max_raw_rank_move": int(frame["rank_delta"].max()),
        }

    full = both[both["n"] >= FULL_SEASON_POSSESSIONS].copy()
    # Ranks are only meaningful among comparable team-seasons.
    full["rank_b"] = full.groupby("season")["b"].rank(ascending=False, method="min")
    full["rank_a"] = full.groupby("season")["a"].rank(ascending=False, method="min")
    full["rank_delta"] = (full["rank_a"] - full["rank_b"]).abs()
    return {
        "all_team_seasons": summary(both),
        f"at_least_{FULL_SEASON_POSSESSIONS}_possessions": summary(full),
        "adjusted_and_state_deltas": "not computed in 5C; they need the 6A rating rebuild",
    }


# Public names for the helpers above.
ref = _ref
concat_source_frames = _concat_source_frames
repair = _repair
sources = _sources
finals = _finals
evidence_ids = _evidence_ids
materiality = _materiality


# ---------------------------------------------------------------------------
# Legacy grading helpers for Stage 6B reproduction and retrospective grading.
# Copied verbatim from scripts/pipeline/backfill_v5_unconstrained_grades.py
# (spread_result, total_result) and scripts/pipeline/score_to_db.py
# (_profit, _normalize_result).
# ---------------------------------------------------------------------------


def spread_result(
    home_points: float | None,
    away_points: float | None,
    line: float | None,
    lean: str | None,
) -> str | None:
    """Frozen-line spread grade for a lean; None when ungradable."""
    if home_points is None or away_points is None or line is None:
        return None
    if lean not in ("home", "away"):
        return None
    cover_margin = (home_points - away_points) + line
    if cover_margin > 0:
        return "win" if lean == "home" else "loss"
    if cover_margin < 0:
        return "loss" if lean == "home" else "win"
    return "push"


def total_result(
    home_points: float | None,
    away_points: float | None,
    line: float | None,
    lean: str | None,
) -> str | None:
    """Frozen-line total grade for a lean; None when ungradable."""
    if home_points is None or away_points is None or line is None:
        return None
    if lean not in ("over", "under"):
        return None
    score = home_points + away_points
    if score > line:
        return "win" if lean == "over" else "loss"
    if score < line:
        return "loss" if lean == "over" else "win"
    return "push"


def _profit(result: str, price: float | None = None) -> float:
    if result == "push":
        return 0.0
    if result == "loss":
        return -1.1 if price is None else -1.0
    if price is not None:
        from cks_picks_cfb.models.market_grading import american_profit_per_unit

        return american_profit_per_unit(price)
    return 1.0


def _normalize_result(val: Any) -> str | None:
    """Map CSV 'Win'/'Loss'/'Push'/NaN to lower-case enum value or None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().lower()
    if s in {"win", "loss", "push"}:
        return s
    return None


def score_bets(bets_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
    """Score bets against game outcomes. Copied verbatim from scripts/pipeline/score_weekly_bets.py."""
    scored = bets_df.merge(scores_df, left_on="game_id", right_on="id", how="left")

    scored["home_margin"] = scored["home_points"] - scored["away_points"]
    scored["total_score"] = scored["home_points"] + scored["away_points"]

    def get_spread_result(row):
        if pd.isna(row["home_points"]) or pd.isna(row["home_team_spread_line"]):
            return None

        margin = row["home_points"] - row["away_points"]
        line = row["home_team_spread_line"]
        cover_margin = margin + line

        bet_side = str(row.get("Spread Bet", "")).lower()
        if bet_side not in ("home", "away"):
            bet_side = str(row.get("spread_lean", "")).lower()

        if cover_margin > 0:
            return (
                "Win"
                if bet_side == "home"
                else "Loss"
                if bet_side == "away"
                else "No Bet"
            )
        elif cover_margin < 0:
            return (
                "Loss"
                if bet_side == "home"
                else "Win"
                if bet_side == "away"
                else "No Bet"
            )
        else:
            return "Push"

    def get_total_result(row):
        if pd.isna(row["total_score"]) or pd.isna(row["total_line"]):
            return None

        score = row["total_score"]
        line = row["total_line"]
        bet_side = str(row.get("Total Bet", "")).lower()
        if bet_side not in ("over", "under"):
            bet_side = str(row.get("total_lean", "")).lower()

        if score > line:
            return (
                "Win"
                if bet_side == "over"
                else "Loss"
                if bet_side == "under"
                else "No Bet"
            )
        elif score < line:
            return (
                "Loss"
                if bet_side == "over"
                else "Win"
                if bet_side == "under"
                else "No Bet"
            )
        else:
            return "Push"

    scored["Spread Bet Result"] = scored.apply(get_spread_result, axis=1)
    scored["Total Bet Result"] = scored.apply(get_total_result, axis=1)
    scored["Spread Result"] = scored["home_margin"]
    scored["Total Result"] = scored["total_score"]

    return scored
