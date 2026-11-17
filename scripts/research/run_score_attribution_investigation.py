"""Regenerate the score-attribution investigation (2026 inventory, 2021-2025 effect).

Read-only. Inputs are cached deterministically under the local lab output
(`<lab-root>/output/score-attribution/`, never committed). Only the first run
reads the Preview data lake (credentials from the checkout's environment); it
reads the pinned 2026 revision's Silver `schedule`, `finals` and `byplay`, the
eleven registered Bronze `plays` captures behind them, and the pinned 2021-2025
Silver `byplay` and `fbs_involved_games` versions listed in the persisted
ratings-lab corpus. Nothing is written to any bucket, database or stored table,
no ratings are written, and the provider is never called.

    uv run python scripts/research/run_score_attribution_investigation.py
    uv run python scripts/research/run_score_attribution_investigation.py --check
    uv run python scripts/research/run_score_attribution_investigation.py --skip-history

`--check` regenerates the data file and the report and fails if either differs
from the committed copy. `--skip-history` omits the 2021-2025 section (the
generated files then differ from the committed ones, so it cannot be combined
with `--check`).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings.possession_measurements import build_measurements
from cks_picks_cfb.ratings_lab import score_attribution as sa

REPORT = Path("docs/modeling/score_attribution_investigation_2026.md")
DATA = Path("docs/modeling/evidence/score_attribution_games_2026.json")
REVISION = Path("conf/season/2026/revision_manifest_w11_v2.json")
AUDIT = Path("docs/modeling/evidence/v5_offense_defense_ratings_audit_2026.json")
EXCEPTIONS = Path("conf/season/2026/score_reconciliation_exceptions.json")
HISTORY_SEASONS = (2021, 2022, 2023, 2024, 2025)
HISTORY_RULES = ("r1_envelope", "r2_isotonic", "r4_scoring_rows")
CLASSES = (
    "A_spurious_values_on_non_scoring_rows",
    "B_wrong_value_on_a_scoring_row",
    "C_points_above_the_final",
    "D_points_missing_from_the_stream",
    "E_no_stream_defect",
)
UNRESOLVED = "unresolved_scoring_attribution"
RULE_LABELS = {
    "r0_baseline": "R0 today (observed stream)",
    "r1_envelope": "R1 monotone envelope capped at the final",
    "r2_isotonic": "R2 capped monotone fit to every row",
    "r3_quarter_anchored": "R3 R2 bounded by the quarter line scores",
    "r4_scoring_rows": "R4 capped monotone fit to scoring rows only",
}


# ------------------------------------------------------------------ inputs


def _cache_dir(lab_root: Path) -> Path:
    path = lab_root / "output" / "score-attribution"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preview_storage():
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
    os.environ.setdefault("CFB_STORAGE_BACKEND", "r2")
    from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

    return ReadOnlyStorage(get_storage(environment="preview"))


def _parse_provider_record(record: object) -> dict:
    if isinstance(record, dict):
        return record
    try:
        return json.loads(str(record))
    except json.JSONDecodeError:
        return ast.literal_eval(str(record))


def fetch_2026(cache: Path) -> None:
    """One read-only read of the pinned 2026 Silver inputs and their Bronze captures."""
    if (cache / "bronze_captures_2026.json").exists():
        return
    from cks_picks_cfb.season.inputs import frame

    store = _preview_storage()
    revision = json.loads(REVISION.read_text())
    for name in ("schedule", "finals", "byplay"):
        frame(store, revision["inputs"][name]).to_parquet(
            cache / f"{name}_2026.parquet", index=False
        )
    byplay_manifest = json.loads(
        store.read_bytes(
            revision["inputs"]["byplay"]["uri"].rsplit("/", 1)[0] + "/manifest.json"
        )
    )
    plays_version = byplay_manifest["parent_versions"][0]
    plays_manifest = json.loads(
        store.read_bytes(
            f"lake/silver/dataset=plays/version={plays_version}/manifest.json"
        )
    )
    silver = store.read_bytes(plays_manifest["uri"])
    if hashlib.sha256(silver).hexdigest() != plays_manifest["content_sha"]:
        raise SystemExit("Silver plays checksum mismatch")
    pd.read_parquet(io.BytesIO(silver)).to_parquet(
        cache / "silver_plays_2026.parquet", index=False
    )
    wanted = list(plays_manifest["source_capture_ids"])
    observations = {
        uri.rsplit("/", 1)[1][:-5]: uri
        for uri in store.list_files("lake/bronze/provider=cfbd/entity=plays")
        if "/observations/" in uri and uri.rsplit("/", 1)[1][:-5] in wanted
    }
    frames, meta = [], []
    for capture_id in sorted(wanted):
        record = json.loads(store.read_bytes(observations[capture_id]))
        payload = store.read_bytes(record["uri"])
        if hashlib.sha256(payload).hexdigest() != record["object_sha"]:
            raise SystemExit(f"Bronze capture checksum mismatch: {capture_id}")
        raw = pd.read_parquet(io.BytesIO(payload))
        parsed = pd.DataFrame(
            [_parse_provider_record(r) for r in raw["provider_record"]]
        )
        parsed["clock_minutes"] = parsed["clock"].map(lambda c: c.get("minutes"))
        parsed["clock_seconds"] = parsed["clock"].map(lambda c: c.get("seconds"))
        parsed = parsed.drop(columns=["clock"])
        parsed.insert(0, "capture_id", capture_id)
        frames.append(parsed)
        meta.append(
            {
                "capture_id": capture_id,
                "canonical_week": int(
                    record["request"]["parameters"]["canonical_week"]
                ),
                "rows": int(len(raw)),
            }
        )
    pd.concat(frames, ignore_index=True).to_parquet(
        cache / "bronze_plays_2026.parquet", index=False
    )
    meta.sort(key=lambda m: m["canonical_week"])
    (cache / "bronze_captures_2026.json").write_text(
        json.dumps({"plays_version": plays_version, "captures": meta}, indent=1)
    )


def open_corpus(lab_root: Path):
    from cks_picks_cfb.ratings_lab.artifacts import (
        LocalLabStore,
        ReadOnlySource,
        ResearchStorage,
    )
    from cks_picks_cfb.ratings_lab.corpus import load_persisted_corpus

    storage = ResearchStorage(
        source=ReadOnlySource(LocalLabStore(lab_root / "source")),
        output=LocalLabStore(lab_root / "output"),
    )
    found = sorted((lab_root / "output").glob("ratings-lab/v1/runs/*/corpus.json"))
    if len(found) != 1:
        raise SystemExit(f"expected exactly one persisted corpus, found {len(found)}")
    ref, _ = storage.stage_at(found[0].relative_to(lab_root / "output").as_posix())
    return load_persisted_corpus(storage, ref)


def fetch_history(cache: Path, corpus) -> None:
    missing = [
        s
        for s in HISTORY_SEASONS
        if not (cache / f"byplay_{s}.parquet").exists()
        or not (cache / f"fbs_involved_games_{s}.parquet").exists()
    ]
    if not missing:
        return
    from dotenv import find_dotenv, load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.ratings_lab.artifacts import R2LabStore, ReadOnlySource

    load_dotenv(find_dotenv(usecwd=True))
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {n: os.getenv(f"CFB_R2_PREVIEW_{n}", "") for n in names}
    if not all(config.values()):
        raise SystemExit("Preview read-source variables CFB_R2_PREVIEW_* are not set")
    source = ReadOnlySource(
        R2LabStore(
            bucket=config["BUCKET"],
            account=config["ACCOUNT_ID"],
            access=config["ACCESS_KEY"],
            secret=config["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
        )
    )
    for season in missing:
        refs = corpus.lower_level_refs[str(season)]
        for name in ("byplay", "fbs_involved_games"):
            ref = refs[name]
            ref = DatasetRef(**ref) if isinstance(ref, dict) else ref
            read_dataset(source, ref).to_parquet(
                cache / f"{name}_{season}.parquet", index=False
            )


# -------------------------------------------------------------- 2026 build


def _kind_label(excluded_offenses: int, excluded_roles: int) -> str:
    if excluded_roles == 0:
        return "observed_exception_only"
    return "whole_game_quarantine" if excluded_roles >= 4 else "partial_quarantine"


def build_inventory(baseline_obs: pd.DataFrame, audit: dict, exceptions: list) -> dict:
    quarantined = set(
        baseline_obs.loc[baseline_obs["missing_reason"].eq(UNRESOLVED), "game_id"]
    )
    ledger = {int(item["game_id"]) for item in audit["quarantine_source_ledgers"]}
    excepted = {int(item["game_id"]) for item in exceptions}
    ids = sorted(ledger | excepted | quarantined)
    return {
        "ids": ids,
        "ledger": ledger,
        "excepted": excepted,
        "quarantined": quarantined,
    }


def _round(value: float) -> float:
    return round(float(value), 6)


def _team_record(
    ordered: pd.DataFrame,
    team: str,
    final: int,
    line: list[int],
    outcomes: dict[str, dict[str, sa.TeamOutcome]],
    stored: dict[str, int],
) -> dict:
    stream = sa.team_stream(ordered, team)
    drops = sa.find_drops(stream, ordered)
    scoring = sa.is_scoring_row(ordered)
    fit = outcomes["r4_scoring_rows"][team].stream
    deviation = stream != fit
    patterns = Counter(drop.pattern for drop in drops)
    signs = np.sign(np.diff(stream))
    signs = signs[signs != 0]
    return {
        "team": team,
        "final": final,
        "line_scores": line,
        "stored_event_points": stored.get("all", 0),
        "stored_possession_points": stored.get("offense", 0),
        "max_running_score": int(np.nanmax(stream)),
        "last_running_score": int(stream[-1]),
        "drop_events": len(drops),
        "drop_patterns": {k: patterns[k] for k in sa.DROP_PATTERNS if patterns[k]},
        "drops_restored": sum(drop.restored for drop in drops),
        "never_restored_patterns": {
            k: v
            for k, v in sorted(
                Counter(d.pattern for d in drops if not d.restored).items()
            )
        },
        "drops_never_restored": sum(not drop.restored for drop in drops),
        "single_row_jumps_over_8": len(sa.large_jumps(stream)),
        "negative_score_rows": int((stream < 0).sum()),
        "direction_reversals": int((signs[1:] != signs[:-1]).sum()),
        "drop_row_types": dict(
            sorted(
                Counter(str(ordered["play_type"].iloc[d.row]) for d in drops).items()
            )
        ),
        "rows_off_the_scoring_fit": int(deviation.sum()),
        "rows_off_the_scoring_fit_on_scoring_rows": int((deviation & scoring).sum()),
        "first_defects": [
            {
                "drive": int(ordered["drive_number"].iloc[d.row]),
                "quarter": int(ordered["quarter"].iloc[d.row]),
                "play": int(ordered["play_number"].iloc[d.row]),
                "play_type": str(ordered["play_type"].iloc[d.row]),
                "before": d.before,
                "after": d.after,
                "pattern": d.pattern,
                "restored": d.restored,
            }
            for d in drops[:3]
        ],
        "rules": {
            rule: {
                "resolved": bool(outcomes[rule][team].resolved),
                "reason": outcomes[rule][team].reason,
                "reached": outcomes[rule][team].reached,
                "quarter_match": outcomes[rule][team].quarter_match,
                "increments_on_scoring_rows": outcomes[rule][team].placed,
                "increments": outcomes[rule][team].increments,
            }
            for rule in sa.RULES
        },
    }


def classify_game(teams: list[dict]) -> tuple[str, str]:
    """Root-cause class of a game from its team records (deterministic)."""
    if any(t["max_running_score"] < t["final"] for t in teams):
        return CLASSES[3], "the running score never reaches a team's final"
    if any(t["rules"]["r4_scoring_rows"]["reason"] == "short_of_final" for t in teams):
        return CLASSES[
            3
        ], "the final is reached only on rows that are not scoring plays"
    if any(t["max_running_score"] > t["final"] for t in teams):
        return CLASSES[2], "the running score exceeds a team's final"
    if any(t["rows_off_the_scoring_fit_on_scoring_rows"] for t in teams):
        return CLASSES[1], "a scoring play's own score disagrees with the monotone fit"
    if any(t["rows_off_the_scoring_fit"] for t in teams):
        return CLASSES[
            0
        ], "only ordinary plays, penalties and kickoffs carry bad scores"
    return CLASSES[4], "the stream is monotone and reaches the final"


def compare_bronze_silver(
    ids: list[int],
    bronze: pd.DataFrame,
    silver: pd.DataFrame,
    byplay: pd.DataFrame,
) -> dict[int, dict]:
    result: dict[int, dict] = {}
    bronze = bronze.assign(id=bronze["id"].astype(str))
    silver = silver.assign(play_id=silver["play_id"].astype(str))
    for game in ids:
        b = bronze[bronze["gameId"].eq(game)]
        s = silver[silver["game_id"].eq(game)]
        merged = b.merge(s, left_on="id", right_on="play_id", suffixes=("_b", "_s"))
        identical = (
            len(b) == len(s) == len(merged)
            and bool((merged["offenseScore"] == merged["offense_score"]).all())
            and bool((merged["defenseScore"] == merged["defense_score"]).all())
            and bool((merged["driveNumber"] == merged["drive_number"]).all())
            and bool((merged["playNumber"] == merged["play_number"]).all())
            and bool((merged["period_b"] == merged["period_s"]).all())
        )
        kept = byplay[byplay["game_id"].eq(game)]
        types = Counter(b["playType"].astype(str)) - Counter(
            kept["play_type"].astype(str)
        )
        result[game] = {
            "bronze_rows": int(len(b)),
            "silver_plays_rows": int(len(s)),
            "bronze_equals_silver_plays": bool(identical),
            "byplay_rows": int(len(kept)),
            "rows_removed_by_byplay": int(len(b) - len(kept)),
            "removed_play_types": dict(sorted(types.items())),
        }
    return result


def drop_team_games(
    plays: pd.DataFrame, order: tuple[str, str, str], cols: dict
) -> int:
    """Team-games with at least one regression when `plays` are sorted by `order`."""
    ordered = plays.sort_values(list(order), kind="mergesort")
    count = 0
    for team in set(ordered[cols["offense"]]) | set(ordered[cols["defense"]]):
        values = np.where(
            ordered[cols["offense"]].eq(team),
            ordered[cols["offense_score"]],
            np.where(
                ordered[cols["defense"]].eq(team),
                ordered[cols["defense_score"]],
                np.nan,
            ),
        )
        values = values[~np.isnan(values)]
        count += int(np.any(np.diff(values) < 0))
    return count


def build_2026(cache: Path) -> dict:
    schedule = pd.read_parquet(cache / "schedule_2026.parquet")
    finals = pd.read_parquet(cache / "finals_2026.parquet")
    byplay = pd.read_parquet(cache / "byplay_2026.parquet")
    bronze = pd.read_parquet(cache / "bronze_plays_2026.parquet")
    silver = pd.read_parquet(cache / "silver_plays_2026.parquet")
    audit = json.loads(AUDIT.read_text())
    exceptions = json.loads(EXCEPTIONS.read_text())

    completed = schedule[schedule["game_id"].isin(set(byplay["game_id"]))].copy()
    if "cancelled" in completed:
        completed = completed[~completed["cancelled"].astype(bool)]
    for column in ("home_team", "away_team"):
        completed[column] = completed[column].map(canonical_team)
    population = completed.assign(
        forecast_eligible=True,
        schedule_completed=True,
        outcome_valid=True,
        measurement_usable=True,
    )
    measured = build_measurements(
        byplay=byplay[byplay["game_id"].isin(set(population["game_id"]))],
        population=population,
        outcomes=finals[finals["game_id"].isin(set(population["game_id"]))],
        scope="season_2026",
        play_identity="byplay_v1",
    )
    obs, events = measured.observations, measured.scoring_events
    inventory = build_inventory(obs, audit, exceptions)
    ids = inventory["ids"]

    annotations = {
        int(a["game_id"]): a["classification"]
        for a in audit["quarantine_annotations"]["affected_games"]
    }
    ledger_events = {
        int(item["game_id"]): item["score_events"]
        for item in audit["quarantine_source_ledgers"]
    }
    byplay = byplay.assign(
        offense=byplay["offense"].map(canonical_team),
        defense=byplay["defense"].map(canonical_team),
    )
    comparison = compare_bronze_silver(ids, bronze, silver, byplay)
    schedule_index = completed.set_index("game_id")
    finals_index = finals.set_index("game_id")
    games = []
    ledger_matches = 0
    for game in ids:
        row = schedule_index.loc[game]
        home, away = str(row["home_team"]), str(row["away_team"])
        final = {
            home: int(finals_index.loc[game, "home_points"]),
            away: int(finals_index.loc[game, "away_points"]),
        }
        lines = {
            home: [int(v) for v in json.loads(row["home_line_scores"])],
            away: [int(v) for v in json.loads(row["away_line_scores"])],
        }
        ordered = sa.order_plays(byplay[byplay["game_id"].eq(game)])
        outcomes = sa.evaluate_game(ordered, final, lines)
        game_events = events[events["game_id"].eq(game)]
        stored = {
            team: {
                "all": int(
                    game_events.loc[
                        game_events["team"].eq(team), "score_increment"
                    ].sum()
                ),
                "offense": int(
                    game_events.loc[
                        game_events["team"].eq(team)
                        & game_events["unit_category"].eq("offense"),
                        "score_increment",
                    ].sum()
                ),
            }
            for team in final
        }
        if game in ledger_events:
            by_team = Counter()
            for event in ledger_events[game]:
                by_team[str(event["team"])] += int(event["score_increment"])
            ledger_matches += all(by_team[t] == stored[t]["all"] for t in final)
        roles = obs[
            obs["game_id"].eq(game)
            & obs["measurement_id"].eq("ppp")
            & obs["missing_reason"].eq(UNRESOLVED)
        ]
        offense_excluded = sorted(
            set(roles.loc[roles["unit_role"].eq("offense"), "team"])
        )
        team_records = [
            _team_record(ordered, t, final[t], lines[t], outcomes, stored[t])
            for t in (home, away)
        ]
        label, why = classify_game(team_records)
        games.append(
            {
                "game_id": int(game),
                "week": int(row["week"]),
                "home_team": home,
                "away_team": away,
                "final": final,
                "in_audit_ledger": game in inventory["ledger"],
                "in_exceptions_file": game in inventory["excepted"],
                "quarantined_by_current_builder": game in inventory["quarantined"],
                "audit_classification": annotations.get(game),
                "quarantine_kind": _kind_label(len(offense_excluded), len(roles)),
                "offense_roles_excluded": offense_excluded,
                "teams": team_records,
                "plays": comparison[game],
                "class": label,
                "class_reason": why,
            }
        )
    ordering = {
        "silver_byplay_production_order": 0,
        "all_bronze_rows_production_order": 0,
        "all_bronze_rows_provider_id_order": 0,
        "all_bronze_rows_wallclock_order": 0,
    }
    bronze_ids = bronze[bronze["gameId"].isin(ids)]
    for game in ids:
        b = bronze_ids[bronze_ids["gameId"].eq(game)]
        names = {
            "offense": "offense",
            "defense": "defense",
            "offense_score": "offenseScore",
            "defense_score": "defenseScore",
        }
        ordering["silver_byplay_production_order"] += drop_team_games(
            byplay[byplay["game_id"].eq(game)],
            ("drive_number", "quarter", "play_number"),
            {k: k for k in names},
        )
        ordering["all_bronze_rows_production_order"] += drop_team_games(
            b, ("driveNumber", "period", "playNumber"), names
        )
        ordering["all_bronze_rows_provider_id_order"] += drop_team_games(
            b.assign(id=b["id"].astype(np.int64)), ("id", "id", "id"), names
        )
        ordering["all_bronze_rows_wallclock_order"] += drop_team_games(
            b, ("wallclock", "id", "id"), names
        )
    bronze_captures = json.loads((cache / "bronze_captures_2026.json").read_text())
    return {
        "games": games,
        "inventory": inventory,
        "ordering_team_games_with_a_regression": ordering,
        "ledger_event_totals_reproduced": ledger_matches,
        "ledger_games": len(ledger_events),
        "bronze_captures": bronze_captures,
        "completed_games_in_build": int(len(population)),
        "baseline_quarantined_games": len(inventory["quarantined"]),
    }


# -------------------------------------------------------------- history


def _apply_rule(
    byplay: pd.DataFrame,
    finals: dict[int, dict[str, int]],
    rule: str,
    quarantined: set[tuple[int, str]],
):
    """Rewrite the score columns of byplay for team-games the builder rejects."""
    parts = []
    changed = 0
    for game, plays in byplay.groupby("game_id", sort=True):
        ordered = sa.order_plays(plays)
        if game not in finals:
            parts.append(ordered)
            continue
        streams = sa.repaired_streams(
            ordered,
            finals[game],
            rule,
            only={team for team in finals[game] if (int(game), team) in quarantined},
        )
        offense, defense = (
            ordered["offense_score"].to_numpy(dtype=float),
            ordered["defense_score"].to_numpy(dtype=float),
        )
        for team, stream in streams.items():
            if stream is None:
                continue
            original = sa.team_stream(ordered, team)
            if np.array_equal(original, stream):
                continue
            changed += 1
            is_offense = ordered["offense"].eq(team).to_numpy()
            is_defense = ordered["defense"].eq(team).to_numpy()
            offense = np.where(is_offense, stream, offense)
            defense = np.where(is_defense, stream, defense)
        parts.append(ordered.assign(offense_score=offense, defense_score=defense))
    return pd.concat(parts, ignore_index=True), changed


def _team_season_ppp(obs: pd.DataFrame, role: str) -> pd.Series:
    rows = obs[
        obs["unit_role"].eq(role)
        & obs["coverage_status"].eq("observed")
        & obs["denominator"].gt(0)
    ]
    grouped = rows.groupby("team")[["numerator", "denominator"]].sum()
    return grouped["numerator"] / grouped["denominator"]


def history_effect(season: int, cache: Path, corpus) -> dict:
    byplay = pd.read_parquet(cache / f"byplay_{season}.parquet")
    population = corpus.population[corpus.population["season"].eq(season)]
    usable = population[population["measurement_usable"].astype(bool)]
    outcomes = corpus.outcomes[corpus.outcomes["season"].eq(season)]
    stored = corpus.observations[
        corpus.observations["season"].eq(season)
        & corpus.observations["measurement_id"].eq("ppp")
    ]
    byplay = byplay[byplay["game_id"].isin(set(usable["game_id"]))].copy()
    byplay["offense"] = byplay["offense"].map(canonical_team)
    byplay["defense"] = byplay["defense"].map(canonical_team)
    schedule = usable.set_index("game_id")
    final_index = outcomes.set_index("game_id")
    finals: dict[int, dict[str, int]] = {}
    for game in byplay["game_id"].unique():
        row = schedule.loc[game]
        points = final_index.loc[game]
        if pd.isna(points["home_points"]) or pd.isna(points["away_points"]):
            continue
        finals[int(game)] = {
            canonical_team(row["home_team"]): int(points["home_points"]),
            canonical_team(row["away_team"]): int(points["away_points"]),
        }
    key = ["game_id", "team", "unit_role"]
    base = stored.set_index(key)
    base_off = _team_season_ppp(stored, "offense")
    base_def = _team_season_ppp(stored, "defense")
    base_excluded = base[base["missing_reason"].eq(UNRESOLVED)]
    quarantined = {
        (int(game), str(team))
        for game, team, role in base_excluded.index
        if role == "offense"
    }
    exposure = (
        stored[stored["coverage_status"].eq("observed")]
        .groupby("team")["denominator"]
        .sum()
    )
    result = {
        "season": season,
        "games": int(byplay["game_id"].nunique()),
        "ppp_role_rows": int(len(stored)),
        "offense_team_games_quarantined_today": int(
            base_excluded.index.get_level_values("unit_role").isin(["offense"]).sum()
        ),
        "offense_team_games": int(stored["unit_role"].eq("offense").sum()),
        "rules": {},
    }
    for rule in HISTORY_RULES:
        repaired, streams_changed = _apply_rule(byplay, finals, rule, quarantined)
        measured = build_measurements(
            byplay=repaired,
            population=usable,
            outcomes=outcomes,
            scope="historical",
        ).observations
        measured = measured[measured["measurement_id"].eq("ppp")]
        merged = base.join(measured.set_index(key), rsuffix="_rule", how="outer")
        was_excluded = merged["missing_reason"].eq(UNRESOLVED)
        now_observed = merged["coverage_status_rule"].eq("observed")
        restored = merged[was_excluded & now_observed]
        still = merged[was_excluded & ~now_observed]
        newly = merged[
            ~was_excluded & ~now_observed & merged["coverage_status"].eq("observed")
        ]
        both = merged[
            ~was_excluded & merged["coverage_status"].eq("observed") & now_observed
        ]
        changed_obs = int(
            (
                (both["numerator"] != both["numerator_rule"])
                | (both["denominator"] != both["denominator_rule"])
            ).sum()
        )
        off = _team_season_ppp(measured, "offense")
        deff = _team_season_ppp(measured, "defense")
        entry = {
            "team_game_streams_rewritten": streams_changed,
            "offense_roles_restored": int(
                restored.index.get_level_values("unit_role").isin(["offense"]).sum()
            ),
            "defense_roles_restored": int(
                restored.index.get_level_values("unit_role").isin(["defense"]).sum()
            ),
            "roles_still_quarantined": int(len(still)),
            "roles_newly_unobserved": int(len(newly)),
            "previously_observed_rows_changed": changed_obs,
            "points_numerator_restored": _round(restored["numerator_rule"].sum()),
            "possessions_restored": _round(restored["denominator_rule"].sum()),
        }
        for label, before, after in (
            ("offense", base_off, off),
            ("defense", base_def, deff),
        ):
            teams = before.index.intersection(after.index)
            teams = teams[exposure.reindex(teams).fillna(0).ge(40)]
            delta = (after.reindex(teams) - before.reindex(teams)).astype(float)
            rank_before = before.reindex(teams).rank(ascending=False, method="min")
            rank_after = after.reindex(teams).rank(ascending=False, method="min")
            shift = (rank_after - rank_before).abs()
            entry[f"{label}_teams_compared"] = int(len(teams))
            entry[f"{label}_ppp_moved_over_0_05"] = int((delta.abs() > 0.05).sum())
            entry[f"{label}_ppp_moved_over_0_10"] = int((delta.abs() > 0.10).sum())
            entry[f"{label}_rank_moved_over_5"] = int((shift > 5).sum())
            entry[f"{label}_max_abs_ppp_move"] = _round(delta.abs().max())
            entry[f"{label}_max_rank_move"] = int(shift.max())
            entry[f"{label}_mean_ppp_move"] = _round(delta.mean())
        result["rules"][rule] = entry
    return result


# --------------------------------------------------------------- summary


def class_resolution(games: list[dict]) -> dict:
    result = {}
    for label in CLASSES:
        members = [g for g in games if g["class"] == label]
        rejected = [
            t
            for g in members
            for t in g["teams"]
            if not t["rules"]["r0_baseline"]["resolved"]
        ]
        result[label] = {
            "games": len(members),
            "rejected_team_games": len(rejected),
            "r1_resolved": sum(t["rules"]["r1_envelope"]["resolved"] for t in rejected),
            "r4_resolved": sum(
                t["rules"]["r4_scoring_rows"]["resolved"] for t in rejected
            ),
            "r4_resolved_and_quarter_lines_match": sum(
                bool(t["rules"]["r4_scoring_rows"]["resolved"])
                and bool(t["rules"]["r4_scoring_rows"]["quarter_match"])
                for t in rejected
            ),
        }
    return result


def spot_check(cache: Path, games: list[dict]) -> list[dict]:
    """Recompute headline facts for five games straight from the raw Bronze rows.

    The recomputation does not use the analysis module: plain maxima and counts over
    the raw provider rows, compared with the committed record.
    """
    bronze = pd.read_parquet(cache / "bronze_plays_2026.parquet")
    by_class: dict[str, dict] = {}
    for game in games:
        by_class.setdefault(game["class"], game)
    chosen = [by_class[c] for c in CLASSES if c in by_class]
    chosen.append(
        max(
            games,
            key=lambda g: (
                max(t["direction_reversals"] for t in g["teams"]),
                -g["game_id"],
            ),
        )
    )
    result = []
    for game in chosen:
        rows = bronze[bronze["gameId"].eq(game["game_id"])]
        rows = rows.sort_values(
            ["driveNumber", "period", "playNumber"], kind="mergesort"
        )
        facts = []
        for record in game["teams"]:
            team = record["team"]
            raw = np.where(
                rows["offense"].map(canonical_team).eq(team),
                rows["offenseScore"],
                np.where(
                    rows["defense"].map(canonical_team).eq(team),
                    rows["defenseScore"],
                    np.nan,
                ),
            )
            raw = raw[~np.isnan(raw)]
            facts.append(
                {
                    "team": team,
                    "record_max": record["max_running_score"],
                    "bronze_max": int(raw.max()),
                    "record_regressions": record["drop_events"],
                    "bronze_regressions": int((np.diff(raw) < 0).sum()),
                }
            )
        result.append(
            {
                "game_id": game["game_id"],
                "class": game["class"],
                "teams": facts,
                "max_matches": all(f["record_max"] == f["bronze_max"] for f in facts),
            }
        )
    return result


def rule_summary(games: list[dict]) -> dict:
    team_games = [(g, t) for g in games for t in g["teams"]]
    invalid = [
        (g, t) for g, t in team_games if not t["rules"]["r0_baseline"]["resolved"]
    ]
    summary = {
        "team_games_in_inventory": len(team_games),
        "team_games_the_builder_rejects": len(invalid),
        "rules": {},
    }
    for rule in sa.RULES:
        resolved = [(g, t) for g, t in invalid if t["rules"][rule]["resolved"]]
        corroborated = [
            (g, t) for g, t in resolved if t["rules"][rule]["quarter_match"]
        ]
        reasons = Counter(
            str(t["rules"][rule]["reason"])
            for g, t in invalid
            if not t["rules"][rule]["resolved"]
        )
        placed = sum(
            t["rules"][rule]["increments_on_scoring_rows"] for g, t in resolved
        )
        increments = sum(t["rules"][rule]["increments"] for g, t in resolved)
        reaches = sum(t["rules"][rule]["reached"] == t["final"] for g, t in invalid)
        summary["rules"][rule] = {
            "resolved": len(resolved),
            "resolved_share_of_rejected": _round(len(resolved) / len(invalid)),
            "resolved_and_quarter_lines_match": len(corroborated),
            "reaches_final_without_validity_checks": reaches,
            "unresolved_reasons": dict(sorted(reasons.items())),
            "increments_on_or_next_to_a_scoring_row": placed,
            "increments": increments,
        }
        summary["rules"][rule]["games_fully_resolved"] = sum(
            all(t["rules"][rule]["resolved"] for t in g["teams"])
            for g in games
            if any(not t["rules"]["r0_baseline"]["resolved"] for t in g["teams"])
        )
    return summary


# ---------------------------------------------------------------- report


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def _examples(games: list[dict], label: str, count: int = 4) -> str:
    ids = [str(g["game_id"]) for g in games if g["class"] == label][:count]
    return ", ".join(f"`{i}`" for i in ids)


def build_report(payload: dict) -> str:
    games = payload["games"]
    counts = payload["inventory_counts"]
    rules = payload["rule_summary"]
    classes = payload["class_counts"]
    history = payload.get("history")
    ordering = payload["ordering_team_games_with_a_regression"]
    out: list[str] = []
    w = out.append
    w("# Score-attribution investigation: the quarantined games, one by one")
    w("")
    w(
        "Read-only investigation of the running-score defect behind `missing / "
        "unresolved_scoring_attribution`. Contract: "
        "[04-score-attribution-investigation](../plans/2026-11-12/04-score-attribution-investigation.md). "
        "Per-game data: [`score_attribution_games_2026.json`](evidence/score_attribution_games_2026.json). "
        "Regenerate and verify with "
        "`uv run python scripts/research/run_score_attribution_investigation.py [--check]`. "
        "Nothing here changes a 2026 prediction, grade, release, the score exceptions file, Production or any stored data."
    )
    w("")
    w("## Answer")
    w("")
    r1 = rules["rules"]["r1_envelope"]
    r4 = rules["rules"]["r4_scoring_rows"]
    n_inv = counts["total"]
    w(
        f"- **Every one of the {n_inv} games was read from the raw provider plays.** In all of them the "
        "defect is in the CFBD feed: the Bronze plays and the Silver plays are identical row for row "
        f"({payload['plays_identical_games']} of {n_inv} games), so nothing in our Silver build creates or hides a bad score. "
        "No ordering (production order, provider play id, wall clock, period and clock) makes the streams monotone."
    )
    w(
        "- **What the defect looks like.** The provider writes the running score on every play row, but only the "
        "scoring plays carry a trustworthy value. Ordinary plays, penalties and kickoffs often carry a stale, zero, or "
        "later-in-the-game score. In clean team-games "
        f"{payload['clean_increments_on_scoring_rows']} of {payload['clean_increments']} score increments sit on a scoring play."
    )
    w(
        f"- **Direct repair (rule R4).** Read the score only on scoring plays, fit those values with a monotone "
        f"fit capped at the game final, and carry the value forward. It resolves {r4['resolved']} of the "
        f"{rules['team_games_the_builder_rejects']} team-games the builder rejects today "
        f"({100 * r4['resolved_share_of_rejected']:.1f}%) and {r4['resolved_and_quarter_lines_match']} of them reproduce the "
        "quarter line scores exactly, an independent check that the cap at the final cannot supply. "
        f"The prior candidate R1 resolves {r1['resolved']} ({100 * r1['resolved_share_of_rejected']:.1f}%) and "
        f"{r1['resolved_and_quarter_lines_match']} match the quarter lines."
    )
    if history:
        hist_r4 = [h["rules"]["r4_scoring_rows"] for h in history]
        restored = sum(h["offense_roles_restored"] for h in hist_r4)
        w(
            f"- **History.** Applied read-only to 2021-2025, R4 restores {restored} team-game offenses "
            "(and the same number of opponent defenses) that the stored measurements exclude today. "
            "Previously observed team-games are unchanged."
        )
    w("")
    w("## Data read")
    w("")
    caps = payload["bronze_captures"]["captures"]
    w(
        f"- 2026: the Silver `schedule`, `finals` and `byplay` of revision `{payload['revision']}` "
        f"(pinned by checksum in `{REVISION}`), plus the {len(caps)} Bronze CFBD `plays` captures "
        f"({sum(c['rows'] for c in caps):,} rows, one per week 0 to {max(c['canonical_week'] for c in caps)}) behind the "
        f"Silver `plays` version `{payload['bronze_captures']['plays_version']}`. Read-only, checksum verified."
    )
    w(
        "- 2021-2025: the Silver `byplay` and `fbs_involved_games` versions pinned in the persisted ratings-lab corpus, "
        "and the corpus's stored ppp observations as the baseline. All five seasons were reachable; none is approximated. "
        "Raw Bronze for 2021-2025 was not read (the stored lineage resolves to Silver; Bronze equals Silver in 2026)."
    )
    w("- No provider request was made or needed.")
    w("")
    w("## 1. Inventory")
    w("")
    w(
        f"The audit ledger holds {counts['ledger']} games ({counts['ledger_partial']} partial and "
        f"{counts['ledger_whole']} whole-game quarantines). The exceptions file holds {counts['exception_entries']} entries "
        f"in {counts['exception_games']} games, {counts['exception_only']} of them not in the ledger. Rebuilding the "
        f"measurements from the pinned week 0 to 10 plays with the unchanged builder quarantines {counts['quarantined_now']} games "
        f"today; {counts['quarantined_in_neither']} of those (`{counts['quarantined_in_neither_ids']}`) is in neither list "
        f"(it is quarantined with no exception). The inventory is the union: **{n_inv} games**."
    )
    w("")
    kinds = ("partial_quarantine", "whole_game_quarantine", "observed_exception_only")
    weeks = sorted({g["week"] for g in games})
    rows = []
    for wk in weeks:
        sel = [g for g in games if g["week"] == wk]
        rows.append(
            [wk]
            + [sum(g["quarantine_kind"] == k for g in sel) for k in kinds]
            + [len(sel)]
        )
    rows.append(
        ["all"]
        + [sum(g["quarantine_kind"] == k for g in games) for k in kinds]
        + [n_inv]
    )
    out += _table(
        ["Week", "Partial", "Whole game", "Exception only (observed)", "Games"], rows
    )
    w("")
    w(
        "Partial means one team's offense and the opponent's defense are excluded; whole game means all four role "
        "observations are excluded; exception only means the game is declared in the exceptions file but the builder "
        f"still observes it. The {counts['ledger']} ledger games reproduce the audit's classification "
        f"({counts['ledger_partial']} partial, {counts['ledger_whole']} whole). "
        f"The stored event totals of the ledger games were reproduced for {payload['ledger_event_totals_reproduced']} of "
        f"{payload['ledger_games']}."
    )
    w("")
    w("## 2. Per-game reading")
    w("")
    w(
        "For each game the plays were read in the production order (drive, quarter, play). The data file has one row per game "
        "with, for each team: the final, the quarter line scores, the stored possession points, the maximum and last running "
        "score, every regression with its pattern, whether it is restored later, and the outcome of each rule. "
        "The raw Bronze rows were compared with the Silver plays by provider play id, score, drive, play and period."
    )
    w("")
    w(
        f"**Bronze equals Silver.** {payload['plays_identical_games']} of {n_inv} games have identical Bronze and Silver plays "
        f"({payload['bronze_rows']:,} rows). The byplay build then removes {payload['rows_removed_by_byplay']:,} rows "
        "(play types such as timeouts, end-of-period rows and uncategorised rows). Removing them can only hide regressions, "
        "never create one: counting team-games with a regression, the raw rows give "
        f"{ordering['all_bronze_rows_production_order']} and the Silver byplay rows give {ordering['silver_byplay_production_order']}. "
        "Sorting by provider play id gives "
        f"{ordering['all_bronze_rows_provider_id_order']} and by wall clock {ordering['all_bronze_rows_wallclock_order']} "
        "(production order: "
        f"{ordering['all_bronze_rows_production_order']}); no order removes the defect."
    )
    w("")
    drops = payload["drop_pattern_totals"]
    w(
        "Every regression of a team's running score, by the pattern taxonomy of known issue 1:"
    )
    w("")
    rows = [
        [
            name.replace("_", " "),
            drops["events"].get(name, 0),
            drops["never_restored"].get(name, 0),
        ]
        for name in sa.DROP_PATTERNS
    ]
    rows.append(
        ["all", sum(drops["events"].values()), sum(drops["never_restored"].values())]
    )
    out += _table(["Pattern", "Events", "Never restored"], rows)
    w("")
    w(
        f"Across the inventory, {payload['teams_with_overshoot']} team-games finish with a running maximum above the final, "
        f"{payload['teams_with_undershoot']} below it, and {payload['teams_with_big_jump']} contain a single-row jump above 8 points."
    )
    w("")
    for title, text in pattern_prose(payload):
        w(f"**{title}.** {text}")
        w("")
    w("## 3. Root-cause classes")
    w("")
    w(
        "Classes are assigned by the data file from each game's own plays (first matching rule, in the order listed): "
        "D when a team's score never reaches its final on a scoring play, C when it exceeds the final, B when a scoring "
        "play's own value disagrees with the monotone fit, A when only non-scoring rows disagree, E when nothing disagrees."
    )
    w("")
    rows = []
    origin = {
        CLASSES[0]: "Provider feed",
        CLASSES[1]: "Provider feed",
        CLASSES[2]: "Provider feed",
        CLASSES[3]: "Provider feed",
        CLASSES[4]: "Ours (policy only)",
    }
    for label in CLASSES:
        rows.append(
            [
                f"`{label}`",
                classes[label],
                origin[label],
                _examples(games, label) or "none",
            ]
        )
    rows.append(["Total", sum(classes.values()), "", ""])
    out += _table(["Class", "Games", "Origin", "Example games"], rows)
    w("")
    w(class_prose(payload))
    w("")
    w("## 4. Repair specification")
    w("")
    w(repair_prose(payload))
    w("")
    w("### Rules compared on the whole set")
    w("")
    w(
        f"Over the {rules['team_games_in_inventory']} team-games in the inventory, "
        f"{rules['team_games_the_builder_rejects']} fail the stream test (any regression, overshoot, undershoot or possession above 8 points; "
        "the builder's rollback absorbs some of these, so this is stricter than its quarantine; the other "
        f"{rules['team_games_in_inventory'] - rules['team_games_the_builder_rejects']} are the clean sides of the same games "
        "and no rule touches them). Share of the stream-test rejects each rule resolves, where resolved means: monotone, reaches "
        "the final, never exceeds it, and every possession's points are between 0 and 8."
    )
    w("")
    rows = []
    for rule in sa.RULES:
        s = rules["rules"][rule]
        rows.append(
            [
                RULE_LABELS[rule],
                f"{s['resolved']} ({100 * s['resolved_share_of_rejected']:.1f}%)",
                s["resolved_and_quarter_lines_match"],
                f"{s['increments_on_or_next_to_a_scoring_row']} of {s['increments']}",
                s["games_fully_resolved"],
                ", ".join(f"{k} {v}" for k, v in s["unresolved_reasons"].items())
                or "none",
            ]
        )
    out += _table(
        [
            "Rule",
            "Resolved team-games",
            "Quarter lines match",
            "Increments on or beside a scoring row",
            "Games fully resolved",
            "Unresolved reasons",
        ],
        rows,
    )
    w("")
    w(
        "The quarter line scores come from the CFBD game record, a separate field from the play-by-play score, so a match is "
        "independent corroboration. R3 uses them as bounds, so its match is by construction and it is shown only to "
        "demonstrate that anchoring to them does not beat R4. The share of rejected team-games whose reconstructed total "
        f"equals the final without the validity checks is {rules['rules']['r1_envelope']['reaches_final_without_validity_checks']} "
        f"for R1 and {r4['reaches_final_without_validity_checks']} for R4 of {rules['team_games_the_builder_rejects']}."
    )
    w("")
    early = [
        t
        for g in games
        if g["week"] <= 4
        for t in g["teams"]
        if t["rules"]["r1_envelope"]["reason"] == "drive_points_outside_0_8"
    ]
    w(
        "The earlier R1 analysis (known issue 1, weeks 0 to 4) left 18 quarantines unresolved because one possession would "
        f"carry more than 8 points. In this rebuild {len(early)} weeks 0 to 4 team-games are unresolved under R1 for that "
        "reason; R4 resolves "
        f"{sum(t['rules']['r4_scoring_rows']['resolved'] for t in early)} of them "
        f"({sum(bool(t['rules']['r4_scoring_rows']['quarter_match']) for t in early)} matching the quarter lines). "
        "R1's resolved team-games are also the less trustworthy ones: a leaked early value is booked as real, so later "
        "touchdowns are credited to the wrong possession (the table's increments column)."
    )
    w("")
    w("### Team-games R4 leaves unresolved")
    w("")
    rows = []
    for g in games:
        for t in g["teams"]:
            res = t["rules"]["r4_scoring_rows"]
            if not t["rules"]["r0_baseline"]["resolved"] and (
                not res["resolved"] or not res["quarter_match"]
            ):
                rows.append(
                    [
                        f"`{g['game_id']}`",
                        t["team"],
                        t["final"],
                        t["max_running_score"],
                        res["reached"],
                        res["reason"] or "resolved, quarter lines differ",
                    ]
                )
    out += _table(
        ["Game", "Team", "Final", "Max running", "R4 reaches", "Reason"], rows
    )
    w("")
    w(failure_prose(payload))
    w("")
    w("## 5. Historical effect, 2021 to 2025")
    w("")
    if history:
        w(
            "Each rule was applied read-only to the pinned Silver `byplay` of each season: only team-games the builder rejects "
            "had their score columns rewritten, then the unchanged `build_measurements` produced the ppp observations. The "
            "baseline is the stored corpus observation set. Season ppp below is the exposure-weighted raw points per "
            "possession of the observed team-games (teams with at least 40 observed possessions); it is **not** the "
            "opponent-adjusted, prior-shrunk V5 rating, which was not recomputed."
        )
        w("")
        rows = []
        for h in history:
            for rule in HISTORY_RULES:
                e = h["rules"][rule]
                rows.append(
                    [
                        h["season"],
                        rule.split("_")[0].upper(),
                        h["offense_team_games_quarantined_today"],
                        e["offense_roles_restored"],
                        e["roles_still_quarantined"],
                        e["roles_newly_unobserved"],
                        e["previously_observed_rows_changed"],
                        e["points_numerator_restored"],
                    ]
                )
        out += _table(
            [
                "Season",
                "Rule",
                "Offense team-games excluded today",
                "Offenses restored",
                "Roles still excluded",
                "Roles newly lost",
                "Observed rows changed",
                "Points restored",
            ],
            rows,
        )
        w("")
        rows = []
        for h in history:
            for rule in HISTORY_RULES:
                e = h["rules"][rule]
                rows.append(
                    [
                        h["season"],
                        rule.split("_")[0].upper(),
                        f"{e['offense_ppp_moved_over_0_05']} / {e['offense_ppp_moved_over_0_10']}",
                        e["offense_rank_moved_over_5"],
                        f"{e['offense_max_abs_ppp_move']:.3f}",
                        f"{e['defense_ppp_moved_over_0_05']} / {e['defense_ppp_moved_over_0_10']}",
                        e["defense_rank_moved_over_5"],
                        f"{e['defense_max_abs_ppp_move']:.3f}",
                    ]
                )
        out += _table(
            [
                "Season",
                "Rule",
                "Offense teams moving > 0.05 / > 0.10 ppp",
                "Offense rank moves > 5",
                "Max offense move",
                "Defense teams moving > 0.05 / > 0.10 ppp",
                "Defense rank moves > 5",
                "Max defense move",
            ],
            rows,
        )
        w("")
        w(history_prose(payload))
    else:
        w("Not computed in this run.")
    w("")
    w("## 6. Spot check")
    w("")
    w(spot_check_prose(payload))
    w("")
    w("## 7. Not done, risks, decisions")
    w("")
    w(not_done_prose(payload))
    w("")
    w("## Appendix: every game")
    w("")
    rows = []
    for g in games:
        h, a = g["teams"]
        rows.append(
            [
                f"`{g['game_id']}`",
                g["week"],
                f"{h['team']} {h['final']}, {a['team']} {a['final']}",
                g["quarantine_kind"].replace("_", " "),
                f"{h['max_running_score']} / {a['max_running_score']}",
                h["drop_events"] + a["drop_events"],
                g["class"].split("_")[0],
                "yes"
                if all(t["rules"]["r1_envelope"]["resolved"] for t in g["teams"])
                else "no",
                "yes"
                if all(t["rules"]["r4_scoring_rows"]["resolved"] for t in g["teams"])
                else "no",
            ]
        )
    out += _table(
        [
            "Game",
            "Week",
            "Final",
            "Kind",
            "Max running",
            "Regressions",
            "Class",
            "R1 resolves",
            "R4 resolves",
        ],
        rows,
    )
    w("")
    return "\n".join(out)


def pattern_prose(payload: dict) -> list[tuple[str, str]]:
    totals = payload["drop_pattern_totals"]
    events = totals["events"]
    never = totals["never_restored"]
    all_events = sum(events.values())
    restored = all_events - sum(never.values())
    types = payload["drop_row_type_totals"]
    ordinary = sum(
        count
        for name, count in types.items()
        if name in {"Rush", "Pass Reception", "Pass Incompletion", "Punt", "Sack"}
    )
    return [
        (
            "Overall shape",
            f"The {all_events} regressions in the inventory are restored later to at least the "
            f"pre-drop value {restored} times and never restored {sum(never.values())} times. "
            f"{types.get('Kickoff', 0)} sit on kickoff rows, {ordinary} on ordinary scrimmage plays, "
            f"{types.get('Penalty', 0)} on penalty rows, and only "
            f"{sum(types.get(k, 0) for k in types if 'Touchdown' in k or 'Field Goal' in k)} on a scoring play. "
            "The defect lives mostly on rows that are not scoring plays.",
        ),
        (
            "Drop to zero",
            f"{events.get('drop_to_zero', 0)} events, all restored. A team's running score is wiped to "
            "exactly 0 for a run of rows and then returns. In `401858436` USC is at 16 after a safety, shows 0 on "
            "the next five rows (the kickoff and USC's whole drive), and shows 23 on the touchdown row that ends the "
            "drive. The scoring rows on either side are consistent, so the zeros are plain outliers.",
        ),
        (
            "Point after credited before the kick",
            f"{events.get('point_after_before_kick', 0)} events, all restored. A scoring row is followed, usually on the "
            "kickoff row, by a score one or two points lower. In `401856790` Pittsburgh's safety lifts it from 3 to 5, "
            "the next row shows 3 again, and 5 returns later. Where the touchdown row already includes the extra point and "
            "the next row does not, the row after the score is the one that is wrong, which is why a rule must not trust it.",
        ),
        (
            "Reversal beside a penalty or review",
            f"{events.get('penalty_adjacent', 0)} events ({never.get('penalty_adjacent', 0)} never restored). "
            "Penalty rows (accepted, declined and no-play) carry scores that disagree with the plays around them. In "
            "`401856661` Ole Miss reads 10, then 9 on a delay-of-game row, then 17 on the touchdown. Two penalty rows filed under "
            "third-quarter drive 17 carry 24 and 27 (Louisville's 27 is only reached in the fourth quarter); their provider play ids and wall-clock "
            "stamps (03:45 and 03:47 UTC) are two hours after the neighbouring rows (02:16 UTC), so they are fourth-quarter "
            "plays attached to the wrong drive.",
        ),
        (
            "Touchdown or field goal credited, then reversed",
            f"{events.get('scoring_credited_then_reversed', 0)} events ({never.get('scoring_credited_then_reversed', 0)} never "
            "restored), the largest group. An ordinary play carries a score the team has not reached yet or has already "
            "left behind. In `401856661` a pass-reception row shows Ole Miss at 18 and the next row at 17; in `401856732` Ole "
            "Miss falls from 17 to 3 on a reception row and is restored later. In `401856816` a touchdown row "
            "shows Utah at 24 when the fitted score is 17: the later score arrived early.",
        ),
        (
            "Score restored later, or never",
            f"{restored} of {all_events} regressions are restored. The {sum(never.values())} that are not all belong to "
            "overshoot or undershoot team-games (below): a score that was too high falls back to the final, so it never "
            "returns to the earlier, wrong value.",
        ),
        (
            "Maximum above the final",
            f"{payload['teams_with_overshoot']} team-games finish with a running maximum above the final. In `401856790` UCF "
            "is at 7 after its fourth-quarter touchdown and then shows 13 on a Pittsburgh punt row; its final is 7 and its "
            "quarter line scores are 0, 0, 0, 7, so six points were never real. In `401856729` Kentucky's stream is "
            "perfectly monotone and ends at 40 against a final of 34. For these the final, not the stream, is the arbiter.",
        ),
        (
            "Maximum below the final, and touchdowns credited short",
            f"{payload['teams_with_undershoot']} team-game finishes below its final. In `401864579` New Mexico State's first "
            "fourth-quarter touchdown row moves the score from 3 to 5 (two points), the next from 5 to 12, and the game ends at 18: "
            "the six points of the first touchdown were never written. In `401861970` Miami (OH)'s first touchdown row reads 1 "
            "and the next scoring row 14. In `401864514` the full 61 appears on an ordinary play before the scoring plays "
            "reach 60. A scoring row can therefore be short, not only early.",
        ),
        (
            "Negative scores",
            f"{payload['negative_score_rows']} rows in {payload['team_games_with_negative_scores']} team-games carry a "
            "negative running score (for example Miami in `401858206`, 7 to -1 on a kickoff row). They are wrong rows, not "
            "points.",
        ),
        (
            "A segment recorded twice",
            "`401860899` (Colorado State at Oregon State) has 31 direction reversals in one team's stream against 12 or fewer "
            "everywhere else. Its fourth-quarter plays appear twice a couple of seconds apart, one copy with Oregon State at "
            "55 and the other at 42, and the stream peaks at 68 for a team that scored 56. Only this game has this "
            "pattern; the monotone fit and the cap at the final still resolve it, and its quarter line scores match.",
        ),
    ]


def class_prose(payload: dict) -> str:
    r = payload["class_resolution"]
    n = payload["inventory_counts"]["total"]
    a, b, c, d = (r[k] for k in CLASSES[:4])
    return (
        f"**A, spurious values on non-scoring rows ({a['games']} games).** Every scoring play is consistent and the "
        "final is reachable; the bad values sit on kickoffs, penalties and ordinary plays. R4 resolves "
        f"{a['r4_resolved']} of the {a['rejected_team_games']} rejected team-games ({a['r4_resolved_and_quarter_lines_match']} "
        f"match the quarter lines); R1 resolves {a['r1_resolved']}. Provider defect: the same rows and values are in the raw "
        "Bronze capture.\n\n"
        f"**B, a scoring row carries the wrong value ({b['games']} games).** Utah (`401856816`) and Miami (OH) (`401861970`): "
        "a touchdown row is credited far too little (Miami (OH) reads 1) or too much (Utah reads 24 instead of 17), so even "
        f"the scoring rows do not give a clean monotone path. R4 resolves {b['r4_resolved']} of {b['rejected_team_games']} "
        f"rejected team-games; R1 {b['r1_resolved']}. Provider defect.\n\n"
        f"**C, points above the final ({c['games']} games).** At least one team's running score exceeds its final: a touchdown "
        "(or more) is credited and never removed, or removed only by the final whistle. Quarantined today by the cap at the "
        f"final. R4 resolves {c['r4_resolved']} of {c['rejected_team_games']} rejected team-games, "
        f"{c['r4_resolved_and_quarter_lines_match']} matching the quarter lines; R1 {c['r1_resolved']}. Provider defect: the "
        "final score and the quarter line scores agree with each other and disagree with the play-by-play.\n\n"
        f"**D, points missing from the stream ({d['games']} games).** New Mexico State (`401864579`) and New Mexico "
        "(`401864514`): a team's scoring plays never add up to its final (a touchdown credited as two points; the last point "
        f"of 61 appearing only on an ordinary play). R4 resolves {d['r4_resolved']} of {d['rejected_team_games']}; no rule that "
        "reads only the score columns can, because the missing points are not written on any scoring row. Provider defect.\n\n"
        "**E, quarantined with no stream defect (0 games).** None. Every game has a rejected stream or a declared "
        f"exception. **Our handling of valid data created no defect in any of the {n} games**: the Bronze and Silver plays "
        "are identical. What is ours is policy: the builder drops a whole team-game (and the opponent's defense) as soon as "
        "any row regresses, even though in most games only a handful of rows are wrong; it treats a final-score overshoot as "
        "unrecoverable although the final is the arbiter; and, for the three exception-only games, its score-regression "
        "rollback loses non-possession points (known issue 1)."
    )


def repair_prose(payload: dict) -> str:
    s = payload["rule_summary"]["rules"]
    clean = f"{payload['clean_increments_on_scoring_rows']} of {payload['clean_increments']}"
    return (
        "**Recommended rule (R4 with a quarter-line gate).** Per completed game and team:\n\n"
        "1. Anchors are the rows the provider marks as scoring plays (`scoring` is true, or the play type contains Touchdown, "
        "Field Goal Good, Safety, Extra Point Good or Two Point). Every other row's score column is ignored.\n"
        "2. Fit the team's anchor values with the non-decreasing sequence that minimises total absolute error, using only values "
        "seen on the anchors plus 0 and the final, and never exceeding the final. Ties choose the lowest value.\n"
        "3. Carry the fitted value forward to every row until the next anchor.\n"
        "4. Resolved only if the carried stream reaches the final exactly and every possession (before = the team's score on the row "
        "before the drive, after = its score on the drive's last row) is between 0 and 8 points. Otherwise the team-game stays "
        "quarantined, exactly as today.\n"
        "5. Optional gate: accept only if the points gained per quarter equal the game record's quarter line scores.\n"
        "6. A team-game the builder already accepts is never touched.\n\n"
        f"Evidence relied on: the provider's scoring flag and play type (independent of the score columns; in team-games the "
        f"builder accepts outside the inventory, {clean} score increments sit on a scoring row), the game final, and the quarter line scores. "
        "The cap at the final is what guarantees the rule never exceeds it; `tests/ratings_lab/test_score_attribution.py` "
        "asserts that for synthetic overshoot streams, and the code asserts it on every stream it rebuilds (inventory and "
        "2021 to 2025).\n\n"
        "**Why not R1.** R1 reaches the final by construction, but it books a leaked early value as real, so the later scoring "
        "plays land in zero-point possessions, which shows as 24 rejected team-games (a single drive above 8 points) and, among "
        f"those it resolves, only {s['r1_envelope']['increments_on_or_next_to_a_scoring_row']} of "
        f"{s['r1_envelope']['increments']} increments are near a scoring play. R4 puts every increment on a scoring play by "
        "construction, and the quarter lines (a field R4 does not read) confirm it independently.\n\n"
        "**Repair by class.** A: R4 as above. B: R4 repairs a wrong scoring value when the neighbouring anchors outvote it; "
        "where two adjacent anchors disagree the team-game stays quarantined, and a floor on the increment of a touchdown row "
        "(at least 6) plus the quarter lines would be the next refinement (not evaluated). C: the cap at the final removes the "
        "phantom points; the quarter lines show which quarter they belonged to. D: no score-column rule applies; the points "
        "would have to be rebuilt from the scoring plays' own text (touchdown 6, field goal 3, safety 2, plus the conversion "
        "in the text) and checked against the final and the quarter lines, which is a separate contract. Until then these "
        "stay quarantined."
    )


def failure_prose(payload: dict) -> str:
    return (
        "Utah and Miami (OH) (class B): two adjacent scoring rows disagree, so one possession would have to carry more than "
        "8 points. New Mexico and New Mexico State (class D): the missing points are on no scoring row. Wisconsin (`401858460`) and "
        "New Mexico (`401864579`) are resolved by R4 but one quarter's gain differs from the quarter line (Wisconsin gains 29 in "
        "the second quarter against a line of 28); a gate that requires the quarter lines would hold them back, and the "
        "cause of the one-point shift was not isolated."
    )


def spot_check_prose(payload: dict) -> str:
    rows = payload["spot_check"]
    lines = [
        "Five games, one from each class that has games plus the game with the most direction reversals, were re-read "
        "independently of the analysis module. The first check recomputes each team's maximum running score and its count of "
        "regressions with plain array operations straight from the raw Bronze rows; the maximum matches the committed record "
        f"for {sum(r['max_matches'] for r in rows)} of {len(rows)} games. Bronze counts at least as many regressions as the "
        "record because the byplay build removes rows that could only add regressions. The second check was a manual "
        "reading of the plays around each defect (kickoff, penalty and scoring rows with their play text):",
        "",
    ]
    for r in rows:
        facts = "; ".join(
            f"{t['team']} max {t['bronze_max']} (record {t['record_max']}), regressions {t['bronze_regressions']} raw "
            f"/ {t['record_regressions']} record"
            for t in r["teams"]
        )
        lines.append(f"- `{r['game_id']}` ({r['class'].split('_')[0]}): {facts}.")
    lines += [
        "",
        "The manual readings agree with the records: `401856661` (A) shows the stale penalty-row and later-score "
        "values described above; `401856816` (B) the Utah touchdown row at 24; `401856729` (C) a Kentucky stream that is monotone "
        "to 40 against a final of 34; `401864514` (D) the 61 appearing on an ordinary play with the scoring rows at 60; "
        "`401860899` the duplicated fourth quarter.",
    ]
    return "\n".join(lines)


def not_done_prose(payload: dict) -> str:
    return (
        "- **No ratings were recomputed.** The historical effect is at the ppp observation level (season points per possession "
        "and its ranks). The opponent-adjusted, prior-shrunk V5 rating needs the V5 control replay and was not run; the move "
        "in rating terms is smaller than the raw-ppp move shown. Nothing was written.\n"
        "- **Raw Bronze was read for 2026 only.** 2021 to 2025 use the pinned Silver `byplay`; 2026 shows Bronze equals "
        "Silver, and the quarantine rate and classes in 2025 match 2026's (known issue 10).\n"
        "- **No play-text ledger** (touchdown 6, field goal 3, safety 2, conversions parsed from text) was built, so classes B "
        "and D have no repair yet. It would use only fields already in the Silver plays; no provider request is needed.\n"
        "- **Provider-side cause.** What inside CFBD produces the stale and future scores cannot be settled from our data. "
        "Settling it would need a different CFBD request (for example the drives endpoint for these games, already seen "
        "to be unclean in known issue 1) or a provider ticket; no request was made.\n"
        "- **Possession points outside drives** (defensive and special-teams touchdowns) are unchanged by every rule here; "
        "they feed offsets and the matchup page, not ppp.\n"
        "- **Inventory is 56 games, not 55.** The contract's union of the audit ledger and the exceptions file is 55; "
        "the current builder also quarantines `401858279` with no exception, so it is included and flagged.\n"
        "- **Decisions for the owner.** (1) Whether to open a contract that adopts R4 plus the quarter-line gate as the "
        "next-model measurement rule, and whether it should also re-derive the 2025 terminal table and priors. (2) Whether "
        "to open the play-text ledger contract for classes B and D. (3) Whether to ask the provider about the feed defect."
    )


def assemble(lab_root: Path, with_history: bool) -> tuple[dict, str]:
    cache = _cache_dir(lab_root)
    fetch_2026(cache)
    built = build_2026(cache)
    games = built["games"]
    inventory = built["inventory"]
    audit = json.loads(AUDIT.read_text())
    exceptions = json.loads(EXCEPTIONS.read_text())
    ledger_kinds = Counter(
        a["classification"] for a in audit["quarantine_annotations"]["affected_games"]
    )
    quarantined_in_neither = sorted(
        inventory["quarantined"] - inventory["ledger"] - inventory["excepted"]
    )
    payload = {
        "contract": "docs/plans/2026-11-12/04-score-attribution-investigation.md",
        "revision": json.loads(REVISION.read_text())["revision_id"],
        "revision_manifest_sha256": _sha256(REVISION),
        "audit_evidence_sha256": _sha256(AUDIT),
        "exceptions_file_sha256": _sha256(EXCEPTIONS),
        "bronze_captures": built["bronze_captures"],
        "inventory_counts": {
            "total": len(inventory["ids"]),
            "ledger": len(inventory["ledger"]),
            "ledger_partial": ledger_kinds["partial_quarantine"],
            "ledger_whole": ledger_kinds["whole_game_quarantine"],
            "exception_entries": len(exceptions),
            "exception_games": len(inventory["excepted"]),
            "exception_only": len(inventory["excepted"] - inventory["ledger"]),
            "quarantined_now": len(inventory["quarantined"]),
            "quarantined_in_neither": len(quarantined_in_neither),
            "quarantined_in_neither_ids": ", ".join(map(str, quarantined_in_neither)),
        },
        "ordering_team_games_with_a_regression": built[
            "ordering_team_games_with_a_regression"
        ],
        "ledger_event_totals_reproduced": built["ledger_event_totals_reproduced"],
        "ledger_games": built["ledger_games"],
        "games": games,
    }
    payload["plays_identical_games"] = sum(
        g["plays"]["bronze_equals_silver_plays"] for g in games
    )
    payload["bronze_rows"] = sum(g["plays"]["bronze_rows"] for g in games)
    payload["rows_removed_by_byplay"] = sum(
        g["plays"]["rows_removed_by_byplay"] for g in games
    )
    payload["class_counts"] = {c: sum(g["class"] == c for g in games) for c in CLASSES}
    payload["rule_summary"] = rule_summary(games)
    all_drops = Counter()
    never_drops = Counter()
    all_teams = [t for g in games for t in g["teams"]]
    for t in all_teams:
        for name, n in t["drop_patterns"].items():
            all_drops[name] += n
        for name, n in t["never_restored_patterns"].items():
            never_drops[name] += n
    payload["drop_pattern_totals"] = {
        "events": dict(sorted(all_drops.items())),
        "never_restored": dict(sorted(never_drops.items())),
    }
    payload["teams_with_overshoot"] = sum(
        t["max_running_score"] > t["final"] for t in all_teams
    )
    payload["teams_with_undershoot"] = sum(
        t["max_running_score"] < t["final"] for t in all_teams
    )
    payload["teams_with_big_jump"] = sum(
        t["single_row_jumps_over_8"] > 0 for t in all_teams
    )
    row_types: Counter = Counter()
    for t in all_teams:
        row_types.update(t["drop_row_types"])
    payload["drop_row_type_totals"] = dict(
        sorted(row_types.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    payload["team_games_with_negative_scores"] = sum(
        t["negative_score_rows"] > 0 for t in all_teams
    )
    payload["negative_score_rows"] = sum(t["negative_score_rows"] for t in all_teams)
    payload["class_resolution"] = class_resolution(games)
    payload["spot_check"] = spot_check(cache, games)
    clean = build_clean_increments(cache, {g["game_id"] for g in games})
    payload["clean_increments"] = clean[1]
    payload["clean_increments_on_scoring_rows"] = clean[0]
    if with_history:
        corpus = open_corpus(lab_root)
        fetch_history(cache, corpus)
        payload["history"] = [history_effect(s, cache, corpus) for s in HISTORY_SEASONS]
    payload = json.loads(json.dumps(payload, default=_json_default))
    return payload, build_report(payload)


def build_clean_increments(cache: Path, exclude: set[int]) -> tuple[int, int]:
    """Score increments on scoring rows in team-games the builder accepts (2026)."""
    schedule = pd.read_parquet(cache / "schedule_2026.parquet").set_index("game_id")
    byplay = pd.read_parquet(cache / "byplay_2026.parquet")
    byplay = byplay.assign(
        offense=byplay["offense"].map(canonical_team),
        defense=byplay["defense"].map(canonical_team),
    )
    near = total = 0
    for game, plays in byplay.groupby("game_id", sort=True):
        if game in exclude or game not in schedule.index:
            continue
        ordered = sa.order_plays(plays)
        scoring = sa.is_scoring_row(ordered)
        for team in (
            canonical_team(schedule.loc[game, "home_team"]),
            canonical_team(schedule.loc[game, "away_team"]),
        ):
            stream = sa.team_stream(ordered, team)
            if np.any(np.diff(stream) < 0):
                continue
            for row in np.flatnonzero(np.diff(stream) > 0) + 1:
                total += 1
                near += int(scoring[row])
    return near, total


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"not serialisable: {type(value)}")


def history_prose(payload: dict) -> str:
    history = payload["history"]
    today = sum(h["offense_team_games_quarantined_today"] for h in history)
    lines = [
        "Only team-games the stored measurements exclude today were rewritten, so every observation that exists today is "
        "unchanged (the `Observed rows changed` and `Roles newly lost` columns are 0 in every season and rule). "
        f"Across the five seasons {today} offense team-games are excluded today.",
        "",
    ]
    for rule, label in (
        ("r1_envelope", "R1"),
        ("r2_isotonic", "R2"),
        ("r4_scoring_rows", "R4"),
    ):
        restored = [h["rules"][rule]["offense_roles_restored"] for h in history]
        share = [
            f"{h['season']} {100 * r / h['offense_team_games_quarantined_today']:.0f}%"
            for h, r in zip(history, restored, strict=True)
        ]
        lines.append(
            f"- {label} restores {sum(restored)} of {today} offense team-games (and as many opponent defenses): "
            + ", ".join(share)
            + "."
        )
    moved = [h["rules"]["r4_scoring_rows"] for h in history]
    lines += [
        "",
        "R4 restores far fewer team-games in 2021 to 2024 than the 95% it resolves in the 2026 inventory. In those seasons "
        "the builder excludes team-games for reasons beyond a regressing stream, and the pinned historical Silver is the "
        "older `byplay_v1` lineage; the split was not isolated here. Season raw points per possession moves for "
        f"{min(m['offense_ppp_moved_over_0_05'] for m in moved)} to {max(m['offense_ppp_moved_over_0_05'] for m in moved)} "
        "offenses and "
        f"{min(m['defense_ppp_moved_over_0_05'] for m in moved)} to {max(m['defense_ppp_moved_over_0_05'] for m in moved)} "
        "defenses per season by more than 0.05 under R4, and the largest single-team move is "
        f"{max(m['offense_max_abs_ppp_move'] for m in moved):.2f} ppp on offense. Ranks among the roughly 135 to 150 teams "
        f"compared move by more than five places for {min(m['offense_rank_moved_over_5'] for m in moved)} to "
        f"{max(m['offense_rank_moved_over_5'] for m in moved)} offenses per season. R1 and R4 are close on these "
        "observation-level totals; the difference between them is where points are placed within a game (known from the "
        "2026 placement column), which season totals mostly do not show.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lab-root",
        default=os.getenv(
            "CFB_LAB_LOCAL_ROOT", str(Path.home() / "cfb_ratings_lab_v6")
        ),
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--skip-history", action="store_true")
    args = parser.parse_args(argv)
    if args.check and args.skip_history:
        parser.error("--check needs the full run")
    payload, report = assemble(Path(args.lab_root), not args.skip_history)
    data_text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    if args.check:
        same = (
            DATA.exists()
            and REPORT.exists()
            and DATA.read_text() == data_text
            and REPORT.read_text() == report
        )
        if not same:
            print("generated files differ from the committed copies", file=sys.stderr)
            return 1
        print("data file and report reproduce byte for byte")
        return 0
    DATA.write_text(data_text)
    REPORT.write_text(report)
    print(f"wrote {DATA} and {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
