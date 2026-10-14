"""Hash-checked R2 adapters and complete normalized season inputs."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings.possession_measurements import build_measurements
from cks_picks_cfb.season.manifest import canonical, sha, utc, validate_ref


class Reader(Protocol):
    def read_bytes(self, path: str) -> bytes: ...


def read_ref(reader: Reader, ref: dict) -> bytes:
    validate_ref(ref)
    raw = reader.read_bytes(ref["uri"])
    if sha(raw) != ref["sha256"]:
        raise ValueError(f"input checksum changed: {ref['uri']}")
    return raw


def frame(reader: Reader, ref: dict) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(read_ref(reader, ref)))


@dataclass
class SeasonInputs:
    schedule: pd.DataFrame
    finals: pd.DataFrame
    observations: pd.DataFrame
    events: pd.DataFrame
    bridge: dict
    priors: pd.DataFrame
    terminal: pd.DataFrame
    historical_population: pd.DataFrame
    historical_events: pd.DataFrame
    quotes: pd.DataFrame
    historical_lines: pd.DataFrame


def load_inputs(
    reader: Reader,
    model: dict,
    revision: dict,
    through_week: int,
    *,
    cache_dir: Path | None = None,
    code_sha: str = "",
) -> SeasonInputs:
    m = model["inputs"]
    r = revision["inputs"]
    schedule = frame(reader, r["schedule"])
    required = {"season", "week", "game_id", "kickoff_utc", "home_team", "away_team"}
    if (
        required - set(schedule)
        or schedule.empty
        or schedule.duplicated(["season", "game_id"]).any()
    ):
        raise ValueError("schedule incomplete or duplicated")
    if (
        not schedule.season.eq(2026).all()
        or schedule[["week", "game_id", "home_team", "away_team"]].isna().any().any()
    ):
        raise ValueError("invalid season schedule")
    if "cancelled" in schedule:
        if schedule.cancelled.isna().any():
            raise ValueError("cancellation status missing")
        schedule = schedule[~schedule.cancelled.astype(bool)].copy()
    if (schedule.week.astype(int) < 0).any() or not np.equal(
        schedule.week.astype(float), schedule.week.astype(int)
    ).all():
        raise ValueError("invalid week identity")
    if schedule.home_team.eq(schedule.away_team).any():
        raise ValueError("game participants are identical")
    schedule["kickoff_utc"] = schedule.kickoff_utc.map(utc)
    for name in ("home_team", "away_team"):
        schedule[name + "_provider"] = schedule[name]
        schedule[name] = schedule[name].map(canonical_team)
    completed = schedule[schedule.week.le(through_week)].copy()
    if set(completed.week.astype(int)) != set(range(through_week + 1)):
        raise ValueError("completed weeks must be continuous from Week 0")
    ids = set(completed.game_id.astype(int))
    finals = frame(reader, r["finals"])
    if {"season", "game_id", "home_points", "away_points"} - set(
        finals
    ) or finals.duplicated(["season", "game_id"]).any():
        raise ValueError("finals incomplete or duplicated")
    finals = finals[finals.season.eq(2026) & finals.game_id.isin(ids)].copy()
    scores = finals[["home_points", "away_points"]].to_numpy(float)
    if (
        set(finals.game_id.astype(int)) != ids
        or not np.isfinite(scores).all()
        or (scores < 0).any()
        or (scores != np.floor(scores)).any()
    ):
        raise ValueError("every completed game requires valid final scores")
    byplay = frame(reader, r["byplay"])
    drives = frame(reader, r["drives"])
    for name, table in (("plays", byplay), ("drives", drives)):
        if {"season", "game_id"} - set(table):
            raise ValueError(f"{name} lacks game identity")
        table_ids = set(table.loc[table.season.eq(2026), "game_id"].astype(int))
        if not ids <= table_ids:
            raise ValueError(f"missing required {name}: {sorted(ids - table_ids)}")
    byplay = byplay[byplay.season.eq(2026) & byplay.game_id.isin(ids)].copy()
    drives = drives[drives.season.eq(2026) & drives.game_id.isin(ids)].copy()
    play_key = (
        ["season", "game_id", "source_play_id"]
        if "source_play_id" in byplay
        else ["season", "game_id", "drive_number", "play_number"]
    )
    drive_key = (
        ["season", "game_id", "drive_id"]
        if "drive_id" in drives
        else ["season", "game_id", "drive_number"]
    )
    for name, table, key in (
        ("plays", byplay, play_key),
        ("drives", drives, drive_key),
    ):
        if (
            set(key) - set(table)
            or table[key].isna().any().any()
            or table.duplicated(key).any()
        ):
            raise ValueError(f"duplicate/missing {name} identity")
    drive_column = "drive_id" if "drive_id" in byplay else "drive_number"
    if drive_column not in drives:
        raise ValueError("play/drive identity schemas differ")
    known_drives = set(zip(drives.game_id, drives[drive_column]))
    if not set(zip(byplay.game_id, byplay[drive_column])) <= known_drives:
        raise ValueError("play references absent drive")
    for name in ("offense", "defense"):
        if name in byplay:
            byplay[name] = byplay[name].map(canonical_team)
    joined = byplay.merge(
        completed[["game_id", "home_team", "away_team"]],
        on="game_id",
        validate="many_to_one",
    )
    for column in ("offense", "defense"):
        if (
            column not in joined
            or (
                ~(
                    joined[column].eq(joined.home_team)
                    | joined[column].eq(joined.away_team)
                )
            ).any()
        ):
            raise ValueError("play participant is absent from schedule")
    reconciliation = frame(reader, r["reconciliation"])
    if {"game_id", "blocking"} - set(reconciliation) or reconciliation.duplicated(
        "game_id"
    ).any():
        raise ValueError("stream reconciliation incomplete")
    checked = reconciliation[reconciliation.game_id.isin(ids)]
    if (
        set(checked.game_id.astype(int)) != ids
        or checked.blocking.fillna(True).astype(bool).any()
        or (
            "classification" in checked
            and checked.classification.ne("exact_match").any()
        )
    ):
        raise ValueError("missing/incomplete/conflicting play or drive stream")
    population = completed.assign(
        forecast_eligible=True,
        schedule_completed=True,
        outcome_valid=True,
        measurement_usable=True,
    )
    if "observations" in r:
        if "scoring_events" not in r:
            raise ValueError("imported measurements require scoring events")
        observations = frame(reader, r["observations"])
        events = frame(reader, r["scoring_events"])
    else:
        cache_identity = {
            "refs": {
                name: r[name]
                for name in ("schedule", "finals", "byplay", "drives", "reconciliation")
            },
            "through_week": through_week,
            "play_identity": revision.get("play_identity", "byplay_v1"),
            "code_sha": code_sha,
        }
        cache = cache_dir / sha(canonical(cache_identity)) if cache_dir else None
        receipt = cache / "measurement-cache.json" if cache else None
        if receipt and receipt.exists():
            record = json.loads(receipt.read_bytes())
            if record["identity"] != cache_identity:
                raise ValueError("measurement cache identity differs")
            frames = {}
            for name, ref in record["refs"].items():
                raw = (cache / ref["file"]).read_bytes()
                if sha(raw) != ref["sha256"]:
                    raise ValueError("measurement cache checksum changed")
                frames[name] = pd.read_parquet(io.BytesIO(raw))
            observations, events = frames["observations"], frames["events"]
        else:
            result = build_measurements(
                byplay=byplay,
                population=population,
                outcomes=finals,
                scope="season_2026",
                play_identity=revision.get("play_identity", "byplay_v1"),
            )
            observations, events = result.observations, result.scoring_events
            if cache:
                cache.mkdir(parents=True, exist_ok=True)
                refs = {}
                for name, table in (("observations", observations), ("events", events)):
                    path = cache / f"{name}.parquet"
                    table.to_parquet(path, index=False)
                    refs[name] = {"file": path.name, "sha256": sha(path.read_bytes())}
                receipt.write_bytes(
                    canonical({"identity": cache_identity, "refs": refs})
                )
    observations = observations[
        observations.season.eq(2026) & observations.game_id.isin(ids)
    ].copy()
    for name in ("team", "opponent"):
        observations[name] = observations[name].map(canonical_team)
    ppp = observations[observations.measurement_id.eq("ppp")]
    expected = {
        (int(g.game_id), t, role)
        for g in completed.itertuples()
        for t in (g.home_team, g.away_team)
        for role in ("offense", "defense")
    }
    actual = set(zip(ppp.game_id.astype(int), ppp.team, ppp.unit_role))
    if actual != expected or ppp.duplicated(["game_id", "team", "unit_role"]).any():
        raise ValueError("PPP observations do not cover completed team-game roles")
    events = events[events.season.eq(2026) & events.game_id.isin(ids)].copy()
    events["team"] = events.team.map(canonical_team)
    # Require independently reconciled exact score totals, including unresolved allocations.
    if {"team", "score_increment"} - set(events):
        raise ValueError("scoring events lack score reconciliation")
    participants = {
        (int(g.game_id), team)
        for g in completed.itertuples()
        for team in (g.home_team, g.away_team)
    }
    if not set(zip(events.game_id.astype(int), events.team)) <= participants:
        raise ValueError("scoring event belongs to a foreign participant")
    if (
        "source_event_id" in events
        and events.duplicated(["game_id", "source_event_id"]).any()
    ):
        raise ValueError("duplicate scoring event identity")
    increments = pd.to_numeric(events.score_increment, errors="raise")
    if increments.isna().any() or (increments < 0).any():
        raise ValueError("scoring events contain unresolved score amounts")
    totals = (
        events.assign(score_increment=increments)
        .groupby(["game_id", "team"])
        .score_increment.sum()
    )
    score_by_id = finals.set_index("game_id")
    for game in completed.itertuples():
        for team, column in (
            (game.home_team, "home_points"),
            (game.away_team, "away_points"),
        ):
            if (
                totals.get((game.game_id, team), 0)
                != score_by_id.loc[game.game_id, column]
            ):
                raise ValueError(
                    f"score reconciliation differs: game {game.game_id}, team {team}"
                )
    terminal = frame(reader, m["terminal"])
    historical_population = frame(reader, m["historical_population"])
    historical_events = frame(reader, m["historical_events"])
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS

    for name, table in (
        ("terminal", terminal),
        ("historical population", historical_population),
        ("historical events", historical_events),
    ):
        if "season" not in table or not set(table.season.astype(int)) <= set(
            DEVELOPMENT_SEASONS
        ):
            raise ValueError(f"{name} includes a forbidden model season")
    if not {
        "forecast_eligible",
        "schedule_completed",
        "outcome_valid",
        "measurement_usable",
    } <= set(historical_population):
        from cks_picks_cfb.data.data_first_possession_v1 import build_population

        historical_population = build_population(
            historical_population, scope="historical"
        )
    return SeasonInputs(
        schedule,
        finals,
        observations,
        events,
        json.loads(read_ref(reader, m["bridge"])),
        frame(reader, m["priors"]),
        terminal,
        historical_population,
        historical_events,
        frame(reader, r["market_quotes"]) if "market_quotes" in r else pd.DataFrame(),
        frame(reader, r["historical_lines"])
        if "historical_lines" in r
        else pd.DataFrame(),
    )
