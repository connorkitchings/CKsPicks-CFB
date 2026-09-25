#!/usr/bin/env python3
"""Run one reviewed V5 weekly component; no automatic scheduling or promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.ops.v5_cycle import (
    ORDER,
    CycleSpec,
    apply_component,
    preflight,
)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "apply", "status"))
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--component", choices=ORDER)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    spec = CycleSpec.load(args.descriptor)
    if (args.season, args.week, args.environment, args.cycle_id) != (
        spec.season,
        spec.week,
        spec.environment,
        spec.cycle_id,
    ):
        parser.error("CLI identity differs from the cycle descriptor")
    if args.action != "status" and (not args.component or not args.evidence):
        parser.error("preflight/apply require --component and --evidence")
    if args.action == "preflight":
        print(
            json.dumps(preflight(spec, args.component, args.evidence), sort_keys=True)
        )
    elif args.action == "apply":
        conn_url = resolve_runtime_target(spec.environment).database_url
        context = apply_component(spec, args.component, args.evidence, conn_url)
        print(json.dumps({"pipeline_run_id": context.pipeline_run_id}, sort_keys=True))
    else:
        conn_url = resolve_runtime_target(spec.environment).database_url
        with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pipeline_run_id, state, error_detail FROM ops.pipeline_runs "
                "WHERE pipeline_run_id LIKE %s ORDER BY started_at",
                (f"v5-cycle-{spec.cycle_id}-%",),
            )
            states = {
                run_id: {"state": state, "error": error}
                for run_id, state, error in cur.fetchall()
            }
        progress = {
            component: states.get(
                spec.pipeline_id(component), {"state": "pending", "error": None}
            )
            for component in ORDER
            if component in spec.components
        }
        first_blocker = next(
            (name for name, value in progress.items() if value["state"] != "succeeded"),
            None,
        )
        print(
            json.dumps(
                {
                    "cycle_id": spec.cycle_id,
                    "components": progress,
                    "first_blocker": first_blocker,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
