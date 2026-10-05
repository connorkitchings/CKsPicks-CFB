"""Stage: the signed 6A receipt.

Everything in the receipt is derived from published objects (hash-checked against the
published root manifest), the two Task 4 reports and a read-only catalog check; only the
non-claims are fixed text. The stage verifier re-derives the receipt from the same sources and
requires the same signed checksum, so no claim can drift from its evidence. Signing is
canonical-content checksum signing, not cryptographic authentication.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any

import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.rebuild import catalog_publish
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun

PREFIX = "rebuild/6a/{run_id}/receipt/"
SCHEMA = "rebuild_6a_receipt_v1"
NON_CLAIMS = (
    "Production activation is not authorized and did not occur.",
    "Not all source defects are repaired: reverted allocation groups keep their baseline allocation.",
    "This is Preview-only evidence; nothing here is certified for serving or production.",
    "The CFBD rights basis is the user-specified terms URI, not an independent legal finding.",
    "Signing is canonical-content checksum signing, not cryptographic signer authentication.",
    "No serving, selection or authorization records were written; production prefixes and "
    "tables were not read.",
    "Seasons before 2026 have no website publication; they are compared only with the served "
    "r9 and r9cert research artifacts.",
)
SIX_B_ARTIFACTS = (
    "ratings/team_states.parquet",
    "ratings/rating_states.parquet",
    "ratings/priors.parquet",
    "ratings/terminal.parquet",
    "forecast/bundle.json",
    "forecast/feature_frame.parquet",
    "forecast/offsets.parquet",
    "comparison/decisions.csv",
    "comparison/admitted_events.parquet",
    "states_2026/final_teams.parquet",
    "states_2026/final_roles.parquet",
    "states_2026/current_teams.parquet",
    "states_2026/pregame_teams.parquet",
    "states_2026/priors.parquet",
    "states_2026/observations.parquet",
)
NOT_PROVIDED = (
    "2026 offsets and Week 5 application features and forecasts (6B replay scope)",
    "the cutover week N and the exact release packet (Stages 7-8)",
    "any serving, selection or authorization record",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def catalog_check(entries) -> dict[str, Any]:
    """Read-only Preview catalog verification of the registered versions."""
    import psycopg

    from cks_picks_cfb.data.runtime import resolve_runtime_target
    from cks_picks_cfb.rebuild.targets import assert_preview_database

    ids = [e.version_id for e in entries]
    with psycopg.connect(resolve_runtime_target("preview").database_url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            cur.execute(
                "SELECT version_id, content_sha, uri, row_count, state "
                "FROM catalog.dataset_versions WHERE version_id = ANY(%s)",
                (ids,),
            )
            rows = {r[0]: r for r in cur.fetchall()}
            cur.execute(
                "SELECT count(*) FROM catalog.dataset_dependencies WHERE child_version_id = ANY(%s)",
                (ids,),
            )
            edges = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*), count(*) FILTER (WHERE passed) "
                "FROM catalog.quality_results WHERE version_id = ANY(%s)",
                (ids,),
            )
            quality, passed = cur.fetchone()
    wrong = [
        e.version_id
        for e in entries
        if e.version_id in rows
        and (rows[e.version_id][1], rows[e.version_id][2], rows[e.version_id][3])
        != (e.content_sha, e.uri, e.row_count)
    ]
    return {
        "role": "cks_preview_pipeline (read-only transaction)",
        "versions_expected": len(ids),
        "versions_present": len(rows),
        "content_uri_row_mismatches": len(wrong),
        "states": sorted({r[4] for r in rows.values()}),
        "dependency_edges": int(edges),
        "quality_results": int(quality),
        "quality_passed": int(passed),
    }


def _headline(comparison: dict[str, Any]) -> dict[str, Any]:
    forecasts = comparison["forecasts"]["columns"]
    states = comparison["team_states"]["columns"]["overall_rating"]
    offsets = comparison["offsets"]["columns"]["offset_margin"]
    calibration = comparison["coefficients_and_calibration"]["margin"]
    return {
        "team_states_changed": states["changed"],
        "team_states_over_threshold": states["over_threshold"],
        "team_states_max_abs": states["max_abs"],
        "final_rank_moves_over_5": comparison["final_ranks"]["overall_rating"][
            "over_threshold"
        ],
        "offsets_changed": offsets["changed"],
        "offsets_max_abs": offsets["max_abs"],
        "non_offense_team_games_changed": comparison["non_offense_points"]["columns"][
            "non_offense_for"
        ]["changed"],
        "forecast_margin_changed": forecasts["pred_margin"]["changed"],
        "forecast_margin_mean_abs": forecasts["pred_margin"]["mean_abs"],
        "forecast_margin_max_abs": forecasts["pred_margin"]["max_abs"],
        "forecast_total_mean_abs": forecasts["pred_total"]["mean_abs"],
        "forecast_total_max_abs": forecasts["pred_total"]["max_abs"],
        "max_coefficient_delta_margin": calibration["max_abs_coefficient_delta"],
        "calibration_variance_margin": calibration["calibration_variance"],
    }


def derive_receipt(context: StageContext) -> dict[str, Any]:
    run = PublishedRun(context)
    root = run.root
    plan = context.plan
    entries = catalog_publish.collect_entries(run.objects, run.read)
    attribution_raw = context.read_artifact(
        "attribution", f"rebuild/6a/{plan.run_id}/attribution/report.json"
    )
    comparison_raw = context.read_artifact(
        "published_comparison",
        f"rebuild/6a/{plan.run_id}/published_comparison/report.json",
    )
    attribution, comparison = json.loads(attribution_raw), json.loads(comparison_raw)
    main_plan = yaml.safe_load(context.read_input("main_plan"))
    eligibility = run.json("eligibility/summary.json")
    step5 = run.json("comparison/comparison.json")
    ratings = run.json("ratings/summary.json")
    forecast = run.json("forecast/summary.json")
    states = run.json("states_2026/summary.json")
    gold = run.json("gold/summary.json")
    silver_2026 = run.json("silver_2026/summary.json")
    parities = {
        name: run.json(f"{name}/parity.json")
        for name in ("measurements_parity", "ratings_parity")
    }
    residuals = attribution["residuals"]
    body = {
        "schema_version": SCHEMA,
        "kind": "stage_6a_exit_receipt",
        "production_activation_authorized": False,
        "identity": {
            "main_run_id": root["run_id"],
            "root_manifest": {
                "key": f"{run.prefix}root-manifest.json",
                "raw_sha256": _sha(context.read_input("root_manifest")),
                "embedded_checksum": root["manifest_sha256"],
            },
            "build_code_sha": root["code_sha"],
            "publisher_code_sha": root["publisher_code_sha"],
            "preflight_sha": root["preflight_sha"],
            "verify_sha": root["verify_sha"],
            "stage_manifests": dict(sorted(root["stages"].items())),
            "task4": {
                "run_id": plan.run_id,
                "plan_sha256": plan.plan_sha(),
                "code_sha": context.code_sha,
            },
            "storage_identity": plan.storage_identity,
        },
        "inputs": {
            "main_plan_pins": [
                {k: p[k] for k in ("name", "kind", "uri", "sha256")}
                for p in main_plan["inputs"]
            ],
            "task4_pins": [
                {"name": p.name, "kind": p.kind, "uri": p.uri, "sha256": p.sha256}
                for p in plan.inputs
            ],
            "decisions": dict(plan.decisions),
            "population_policy": main_plan["policies"],
        },
        "outputs": {
            "datasets": [
                {
                    "kind": e.kind,
                    "tier": e.tier,
                    "dataset": e.dataset,
                    "version_id": e.version_id,
                    "schema_version": e.schema_version,
                    "content_sha256": e.content_sha,
                    "uri": e.uri,
                    "row_count": e.row_count,
                }
                for e in entries
            ],
            "run_artifacts": {
                key: digest
                for key, digest in sorted(run.objects.items())
                if key.startswith(run.prefix)
            },
            "bundle_sha256": forecast["digests"]["bundle"],
            "states_2026_digests": states["digests"],
            "catalog": catalog_check(entries),
        },
        "coverage": {
            "games": eligibility["games"],
            "forecast_eligible": eligibility["forecast_eligible"],
            "measurement_usable": eligibility["measurement_usable"],
            "games_by_season": eligibility["by_season"],
            "dispositions": eligibility["dispositions"],
            "declared_missing_games": eligibility["declared_missing"],
            "admitted_ledger": step5["counts"],
            "gold_rows": {n: d["rows"] for n, d in gold["datasets"].items()},
            "rating_rows": ratings["rows"],
            "forecast_rows": forecast["rows"],
            "states_2026": {
                "completed_games": states["completed_games"],
                "scheduled_games": states["scheduled_games"],
                "cutoff_utc": states["cutoff_utc"],
                "rows": states["rows"],
            },
            "silver_2026": {
                "byplay_rows": silver_2026["ppa"]["rows"],
                "null_ppa": silver_2026["ppa"]["null_ppa"],
                "punt_return_flag_rows": silver_2026["punt_return_fix"]["rows"],
            },
        },
        "validation": {
            "step5_comparison": {"passed": step5["passed"], "checks": step5["checks"]},
            "parity": {
                n: {"passed": d["passed"], "checks": d["checks"]}
                for n, d in parities.items()
            },
            "gold_contract_problems": gold["contract_problem_count"],
            "attribution": {
                "epa_only_identity_gate": attribution["epa_only_identity_gate"],
                "combined_equals_published": attribution["published"][
                    "combined_equals_published"
                ],
                "report_sha256": _sha(attribution_raw),
            },
            "published_comparison": {
                "all_differences_explained": comparison["summary"][
                    "all_differences_explained"
                ],
                "control_matches_published": comparison["control_baseline_history"][
                    "matches_published"
                ],
                "report_sha256": _sha(comparison_raw),
            },
        },
        "attribution": {
            "arms": {n: a["digests"] for n, a in attribution["arms"].items()},
            "headline_vs_baseline": {
                n: _headline(c)
                for n, c in attribution["comparisons_vs_baseline"].items()
            },
            "interaction": attribution["interaction"],
            "thresholds": attribution["thresholds"],
        },
        "published_comparison": {
            "season": comparison["season"],
            "summary": comparison["summary"],
            "tables": {
                n: {
                    "cells_compared": t["cells_compared"],
                    "rows_with_a_difference": t["rows_with_a_difference"],
                    "differences_by_bucket": t["differences_by_bucket"],
                    "population": t["population"],
                }
                for n, t in comparison["tables"].items()
            },
            "control_rows_compared": comparison["control_baseline_history"][
                "team_rating_components"
            ]["rows_compared"],
            "explanations": comparison["explanations"],
            "not_compared": comparison["not_compared"],
        },
        "residuals_and_limits": {
            "measured": residuals,
            "limits": [
                "Historical Silver uses the Phase 2c normalized parents behind Step 5, not a re-normalization from Bronze.",
                "2026 scoring stays at baseline; no 2026 allocation has independent admission evidence.",
                "Population label differences (2 games) are reported, not gated.",
                "Test-suite, lint and contract gates are recorded in the session log, not in this receipt; the receipt carries only evidence re-derivable from published objects.",
                "Measurement denominators keep the legacy possession-eligibility flag; the Gold flag is narrower by design.",
            ],
        },
        "inputs_for_6b": {
            "artifacts": {
                f"{run.prefix}{rel}": run.objects[f"{run.prefix}{rel}"]
                for rel in SIX_B_ARTIFACTS
            },
            "selected_design": plan.policies["design"],
            "cutoff_2026": plan.cutoff_2026,
            "not_provided": list(NOT_PROVIDED),
        },
        "non_claims": list(NON_CLAIMS),
    }
    return signed_payload(body)


def render_markdown(receipt: dict[str, Any]) -> str:
    ident, cov = receipt["identity"], receipt["coverage"]
    attribution = receipt["attribution"]["headline_vs_baseline"]
    lines = [
        "# Stage 6A exit receipt",
        "",
        f"- Receipt checksum: `{receipt['manifest_sha256']}`",
        f"- Main run `{ident['main_run_id']}`: build `{ident['build_code_sha'][:8]}`, publisher `{ident['publisher_code_sha'][:8]}`",
        f"- Root manifest raw sha256 `{ident['root_manifest']['raw_sha256']}`",
        f"- Games {cov['games']} ({cov['forecast_eligible']} forecast-eligible, {cov['measurement_usable']} measurement-usable)",
        f"- Admitted ledger: {cov['admitted_ledger']}",
        "",
        "## Attribution versus baseline",
        "",
        "| Arm | Team states changed | Forecast margin changed | Mean abs margin change | Max abs margin change |",
        "|---|---|---|---|---|",
    ]
    for name, h in attribution.items():
        lines.append(
            f"| {name} | {h['team_states_changed']} | {h['forecast_margin_changed']} | "
            f"{h['forecast_margin_mean_abs']:.4f} | {h['forecast_margin_max_abs']:.3f} |"
        )
    lines += ["", "## Non-claims", ""] + [f"- {item}" for item in receipt["non_claims"]]
    return "\n".join(lines) + "\n"


def build(context: StageContext) -> StageOutput:
    receipt = derive_receipt(context)
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield (
            f"{prefix}receipt.json",
            json.dumps(receipt, indent=2, sort_keys=True).encode(),
        )
        yield f"{prefix}receipt.md", render_markdown(receipt).encode()

    return StageOutput(
        artifacts=artifacts(), metrics={"receipt_sha256": receipt["manifest_sha256"]}
    )


def verify(context: StageContext) -> list[str]:
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    staged = json.loads(context.read_artifact(stage, prefix + "receipt.json"))
    problems: list[str] = []
    verify_signed_payload(staged, label="receipt")
    rebuilt = derive_receipt(context)
    if rebuilt != staged:
        problems.append(
            "the receipt differs from a fresh derivation from the published sources"
        )
    if staged.get("production_activation_authorized") is not False:
        problems.append(
            "receipt must state that production activation is not authorized"
        )
    validation = staged["validation"]
    if (
        not validation["step5_comparison"]["passed"]
        or validation["gold_contract_problems"]
    ):
        problems.append("a recorded validation did not pass")
    if not validation["attribution"]["epa_only_identity_gate"]["passed"]:
        problems.append("the EPA-only identity gate did not pass")
    if not validation["published_comparison"]["control_matches_published"]:
        problems.append("the baseline-history control did not match")
    if (
        staged["outputs"]["catalog"]["versions_present"]
        != staged["outputs"]["catalog"]["versions_expected"]
    ):
        problems.append("not every dataset version is registered in the catalog")
    if staged["outputs"]["catalog"]["content_uri_row_mismatches"]:
        problems.append(
            "a registered dataset version differs from its published manifest"
        )
    if len(staged["non_claims"]) != len(NON_CLAIMS):
        problems.append("the non-claims were altered")
    return problems


__all__ = ["build", "verify", "derive_receipt", "GateError"]
