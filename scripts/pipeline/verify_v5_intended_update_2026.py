#!/usr/bin/env python3
"""Independently replay every 2026 intended-update pregame/current rating."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.adjusted_game import CutoffAdjustment
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.corpus import Corpus
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import V5_GAME_AT_CUTOFF
from scripts.pipeline.build_v5_intended_update_2026 import _inputs

TEAM_COLUMNS = [
    "season",
    "week",
    "game_id",
    "cutoff_utc",
    "team",
    "offense_rating",
    "offense_variance",
    "defense_rating",
    "defense_variance",
    "overall_rating",
    "overall_variance",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _observations(frame: pd.DataFrame) -> list[Observation]:
    rows = frame[frame.measurement_id.eq("ppp")]
    result = []
    for row in rows.itertuples(index=False):
        valid = (
            row.coverage_status == "observed"
            and pd.notna(row.raw_value)
            and pd.notna(row.denominator)
            and float(row.denominator) > 0
        )
        result.append(
            Observation(
                2026,
                int(row.week),
                int(row.game_id),
                str(row.team),
                str(row.unit_role),
                "ppp",
                float(row.raw_value) if valid else None,
                float(row.denominator) if pd.notna(row.denominator) else 0.0,
                (pd.Timestamp(row.kickoff_utc) + pd.Timedelta(hours=6)).isoformat(),
                "live",
                missing_reason=None
                if valid
                else str(row.missing_reason or row.coverage_status),
            )
        )
    return result


def _compare(actual: pd.DataFrame, expected: pd.DataFrame, *, keys: list[str]) -> float:
    paired = actual.merge(
        expected, on=keys, suffixes=("_stored", "_rebuilt"), validate="one_to_one"
    )
    if len(paired) != len(actual) or len(actual) != len(expected):
        raise ValueError("independent rating replay changed state keys")
    maximum = 0.0
    for left, right in (
        ("rating_mean", "mean"),
        ("rating_variance", "variance"),
        ("usable_exposure", "usable_exposure"),
    ):
        col_left = left + ("_stored" if left == right else "")
        col_right = right + ("_rebuilt" if left == right else "")
        delta = float((paired[col_left] - paired[col_right]).abs().max())
        maximum = max(maximum, delta)
        if delta > 1e-9:
            raise ValueError(f"independent rating replay changed {left}: {delta}")
    if not (paired.source_game_ids == paired.evidence_game_ids).all():
        raise ValueError("independent rating replay changed source-game IDs")
    return maximum


def verify(
    *,
    manifest_raw: bytes,
    children: dict[str, bytes],
    source_lock: Path,
    cache: Path | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_raw)
    verify_signed_payload(manifest, label="2026 intended-update ratings")
    if (
        manifest.get("schema_version") != "v5_intended_update_2026_rating_manifest_v1"
        or manifest.get("state") != "frozen"
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ValueError("2026 rating manifest is incomplete or unrecognized")
    lock_raw = source_lock.read_bytes()
    lock = json.loads(lock_raw)
    if manifest["parents"]["source_lock_sha256"] != _sha(lock_raw):
        raise ValueError("2026 rating source lock changed")
    if (
        manifest["parents"]["measurement_manifest_sha256"]
        != lock["research_2026_measurement_sha256"]
    ):
        raise ValueError("2026 rating measurement parent changed")
    frames = {}
    for name, ref in manifest["output_refs"].items():
        raw = children[name]
        if _sha(raw) != ref["raw_sha256"]:
            raise ValueError(f"2026 rating child changed: {name}")
        frames[name] = pd.read_parquet(io.BytesIO(raw))
        if len(frames[name]) != int(ref["rows"]):
            raise ValueError(f"2026 rating child count changed: {name}")
    schedule, observations, priors, terminal = _inputs(lock, cache)
    stored_priors = (
        frames["priors"].sort_values(["team", "unit_role"]).reset_index(drop=True)
    )
    source_priors = priors.sort_values(["team", "unit_role"]).reset_index(drop=True)
    if not stored_priors.equals(source_priors):
        raise ValueError("2026 certified preseason priors changed")
    games = [
        Game(
            2026,
            int(row.week),
            int(row.game_id),
            pd.Timestamp(row.kickoff_utc).isoformat(),
            str(row.home_team),
            str(row.away_team),
        )
        for row in schedule.itertuples(index=False)
    ]
    raw_observations = _observations(observations)
    priors_map = {
        (2026, str(row.team), str(row.unit_role)): Rating(
            float(row.prior_mean), float(row.prior_variance)
        )
        for row in priors.itertuples(index=False)
    }
    corpus = Corpus(
        pd.DataFrame(),
        observations,
        pd.DataFrame(),
        terminal,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        {"measurement": {"sha256": manifest["parents"]["measurement_manifest_sha256"]}},
        {},
    )
    adjuster = CutoffAdjustment(corpus, extra_scale_seasons=(2026,))
    pregame = replay(
        games,
        raw_observations,
        design=V5_GAME_AT_CUTOFF,
        measurement_id="ppp_adj_game_at_cutoff_v1",
        timing_class="live",
        fixed_priors=priors_map,
        cutoff_evidence=adjuster.game_evidence,
    )
    expected = pd.DataFrame.from_records(
        {
            "season": item.season,
            "week": item.week,
            "game_id": item.game_id,
            "team": item.team,
            "unit_role": item.role,
            "mean": item.rating.mean,
            "variance": item.rating.variance,
            "usable_exposure": item.usable_exposure,
            "evidence_game_ids": json.dumps(item.evidence_game_ids),
        }
        for item in pregame
    )
    maximum = _compare(
        frames["pregame_roles"],
        expected,
        keys=["season", "week", "game_id", "team", "unit_role"],
    )
    source_index: dict[tuple[str, str], list[Observation]] = {}
    for item in raw_observations:
        source_index.setdefault((item.team, item.role), []).append(item)
    current = frames["current_roles"]
    teams = sorted(priors.team.astype(str).unique())
    for post_week_text, cutoff in manifest["post_week_cutoffs"].items():
        post_week = int(post_week_text)
        artificial = Game(
            2026, post_week + 1, 900000000 + post_week, cutoff, teams[0], teams[1]
        )
        rows = current[current.week.eq(post_week + 1)]
        if len(rows) != 276:
            raise ValueError("current rating generation lacks 138 teams")
        for row in rows.itertuples(index=False):
            evidence = adjuster.game_evidence(
                artificial,
                row.team,
                row.unit_role,
                source_index.get((row.team, row.unit_role), []),
            )
            expected_rating, _ = V5_GAME_AT_CUTOFF.estimate(
                priors_map[(2026, row.team, row.unit_role)], evidence
            )
            delta = max(
                abs(float(row.rating_mean) - expected_rating.mean),
                abs(float(row.rating_variance) - float(expected_rating.variance)),
            )
            maximum = max(maximum, delta)
            expected_ids = [
                item.game_id
                for item in evidence
                if item.value is not None and item.exposure > 0
            ]
            if delta > 1e-9 or json.loads(row.source_game_ids) != expected_ids:
                raise ValueError(
                    f"current rating differs from independent cutoff replay: "
                    f"post_week={post_week}, team={row.team}, role={row.unit_role}, "
                    f"delta={delta}, stored_ids={row.source_game_ids}, expected_ids={expected_ids}"
                )
    for prefix, frame in (
        ("pregame", frames["pregame_teams"]),
        ("current_post", frames["current_teams"]),
    ):
        for name, digest in manifest["generation_hashes"].items():
            if not name.startswith(prefix + "_"):
                continue
            week = int(name.rsplit("w", 1)[-1])
            part = frame[frame.week.eq(week if prefix == "pregame" else week + 1)]
            ordered = part.sort_values(
                ["season", "week", "game_id", "team"],
                kind="mergesort",
                na_position="first",
            )
            if canonical_frame_digest(ordered, columns=TEAM_COLUMNS) != digest:
                raise ValueError(f"rating generation hash changed: {name}")
    return signed_payload(
        {
            "schema_version": "v5_intended_update_2026_rating_verification_v1",
            "state": "verified",
            "rating_manifest_raw_sha256": _sha(manifest_raw),
            "pregame_roles": len(frames["pregame_roles"]),
            "current_roles": len(current),
            "current_team_generations": len(manifest["post_week_cutoffs"]),
            "maximum_mean_or_variance_difference": maximum,
            "production_activation_authorized": False,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-output", type=Path)
    parser.add_argument("--manifest-uri")
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--local-cache", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if bool(args.local_output) == bool(args.manifest_uri):
        raise ValueError("provide one local output or manifest URI")
    if args.apply and (args.local_output or args.local_cache):
        raise ValueError("immutable verifier must re-read certified R2 sources")
    storage = get_storage(environment="preview") if args.manifest_uri else None
    if storage:
        raw = storage.read_bytes(args.manifest_uri)
        manifest = json.loads(raw)
        children = {
            name: storage.read_bytes(ref["uri"])
            for name, ref in manifest["output_refs"].items()
        }
    else:
        root = args.local_output
        raw = (root / "rating-manifest.json").read_bytes()
        manifest = json.loads(raw)
        children = {
            name: (root / f"{name}.parquet").read_bytes()
            for name in manifest["output_refs"]
        }
    result = verify(
        manifest_raw=raw,
        children=children,
        source_lock=args.source_lock,
        cache=args.local_cache,
    )
    if args.apply:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty:
            raise ValueError(
                "rating verifier publication requires clean committed code"
            )
        uri = (
            f"{args.manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
        )
        payload = canonical_json(result)
        if storage.exists(uri):
            if storage.read_bytes(uri) != payload:
                raise ValueError("immutable rating verifier collision")
        else:
            storage.write_bytes(payload, uri)
        print(json.dumps({"verification_uri": uri, "raw_sha256": _sha(payload)}))
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
