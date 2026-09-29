"""Reconstruct the 2026 Week 4 Alabama/South Carolina ratings as a diagnostic."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.audit.corpus import concat_all, read_any
from cks_picks_cfb.ratings_lab.adjusted_game import four_pass_graph
from cks_picks_cfb.ratings_lab.artifacts import (
    R2LabStore,
    ReadOnlySource,
    canonical_json,
    sha256,
)
from cks_picks_cfb.ratings_lab.contracts import Observation, Rating
from cks_picks_cfb.ratings_lab.updaters import V5_GAME_AT_CUTOFF


def _live_observations(cache: Path | None) -> pd.DataFrame:
    if cache is not None:
        source = cache / "live_measurement_observations.parquet"
        if (
            sha256(source.read_bytes())
            != "65787e4bb820c5e9a9d6776bca15c423fda51418d821bb21e0fd913ef593c12f"
        ):
            raise ValueError(
                "Week 4 source observations differ from pinned local import"
            )
        return pd.read_parquet(source)
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("Week 4 diagnostic requires CFB_STORAGE_BACKEND=r2")
    required = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in required}
    if not all(config.values()):
        raise ValueError("Preview read-source configuration is incomplete")
    storage = ReadOnlySource(
        R2LabStore(
            bucket=config["BUCKET"],
            account=config["ACCOUNT_ID"],
            access=config["ACCESS_KEY"],
            secret=config["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
        )
    )
    uri = (
        "artifacts/research/data-first-football-v1/possession-v1/measurements/runs/"
        "possession-v1-measurements-20260927-w4/measurement-manifest.json"
    )
    payload = storage.read(uri)
    if (
        sha256(payload)
        != "c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f"
    ):
        raise ValueError("Week 4 measurement manifest differs from pinned source")
    manifest = json.loads(payload)
    rating_uri = (
        "artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/"
        "possession-v1-rating-replay-20260927-w4/retained-rating-replay-manifest.json"
    )
    if (
        sha256(storage.read(rating_uri))
        != "75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0"
    ):
        raise ValueError("Week 4 rating manifest differs from pinned source")
    return concat_all(read_any(storage, manifest["output_refs"]["observations"]))


def run(cache: Path | None, audit_path: Path, output: Path) -> dict[str, object]:
    audit = json.loads(audit_path.read_text())
    observations = _live_observations(cache)
    observed = observations[
        observations.measurement_id.eq("ppp")
        & observations.coverage_status.eq("observed")
        & pd.to_numeric(observations.denominator, errors="coerce").gt(0)
    ]
    graph = four_pass_graph(list(observed.itertuples(index=False)))
    records = {}
    for team in ("Alabama", "South Carolina"):
        records[team] = {}
        for role in ("offense", "defense"):
            baseline = audit["teams"][team][role]
            center, scale, sign = audit["scale"][role]
            rows = observed[observed.team.eq(team) & observed.unit_role.eq(role)]
            sources = []
            for row in rows.itertuples(index=False):
                opponent_role = "defense" if role == "offense" else "offense"
                opponent = graph.opponent_values.get((str(row.opponent), opponent_role))
                league_center = graph.opponent_centers.get(opponent_role)
                missing = opponent is None or league_center is None
                native = (
                    float(row.raw_value)
                    if missing
                    else float(row.raw_value) - (opponent - league_center)
                )
                value = sign * (native - center) / scale
                sources.append(
                    Observation(
                        2026,
                        int(row.week),
                        int(row.game_id),
                        team,
                        role,
                        "ppp_adj_game_at_cutoff_v1",
                        value,
                        float(row.denominator),
                        (
                            pd.Timestamp(row.kickoff_utc) + pd.Timedelta(hours=6)
                        ).isoformat(),
                        "live",
                        missing_reason="missing_opponent_context_raw_ppp"
                        if missing
                        else None,
                    )
                )
            prior = Rating(
                float(baseline["prior_mean"]), float(baseline["prior_variance"])
            )
            rating, explanation = V5_GAME_AT_CUTOFF.estimate(prior, sources)
            terminal = baseline["terminal"]
            if (
                abs(graph.adjusted[(team, role)] - float(terminal["adjusted_value"]))
                > 1e-9
            ):
                raise ValueError(
                    "live four-pass graph differs from certified Week 4 terminal"
                )
            old = baseline["prior_contribution"] + sum(
                item["mean_contribution"] for item in baseline["items"]
            )
            records[team][role] = {
                "accepted_v5_mean": old,
                "repaired_diagnostic_mean": rating.mean,
                "variance": rating.variance,
                "prior_weight": explanation["prior_weight"],
                "prior_contribution": explanation["prior_contribution"],
                "source_games": explanation["evidence_contributions"],
            }
        records[team]["overall"] = {
            "accepted_v5": (
                records[team]["offense"]["accepted_v5_mean"]
                + records[team]["defense"]["accepted_v5_mean"]
            )
            / 2,
            "repaired_diagnostic": (
                records[team]["offense"]["repaired_diagnostic_mean"]
                + records[team]["defense"]["repaired_diagnostic_mean"]
            )
            / 2,
        }
    report = {
        "schema_version": "v5_intended_update_live_diagnostic_v1",
        "measurement_manifest_sha256": "c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f",
        "rating_manifest_sha256": "75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0",
        "cutoff": "after_2026_week_4_terminal",
        "purpose": "diagnostic_only_not_a_selection_rule",
        "teams": records,
    }
    output.write_bytes(canonical_json(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-cache", type=Path)
    parser.add_argument(
        "--audit",
        default=Path("docs/research/2026-09-28-current-v5-ratings-evidence.json"),
        type=Path,
    )
    parser.add_argument("--local-output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.local_cache, args.audit, args.local_output)
    print(args.local_output, sha256(canonical_json(result)))
