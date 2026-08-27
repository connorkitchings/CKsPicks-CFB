#!/usr/bin/env python3
"""Close the exact full-corpus R1 Silver ref set from immutable manifests."""

from __future__ import annotations

import argparse
import json

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.successor_history import (
    R1_REQUIRED_DATASETS,
    derived_history_ref_set,
)


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable successor-v2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview", "production"), required=True)
    parser.add_argument(
        "--season-lineage-policy",
        default="conf/ratings/successor_v2_season_lineage.yaml",
    )
    parser.add_argument("--source-set-uri", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 R1 ref sets are Preview-only")
    policy = load_season_lineage_policy(args.season_lineage_policy)
    if not args.output_uri.startswith(f"{policy.research_prefix}/"):
        raise ValueError("Successor-v2 output must use the isolated research prefix")
    storage = get_storage(environment="preview")
    source_set = json.loads(storage.read_bytes(args.source_set_uri).decode())
    if (
        source_set.get("contract_version") != "successor-history-source-set-v2"
        or source_set.get("state") != "complete"
        or source_set.get("seasons") != list(policy.historical_development_seasons)
        or not source_set.get("manifest_sha256")
    ):
        raise ValueError("R1 ref set requires one complete full-corpus source set")
    root = args.source_set_uri.rsplit("/", 1)[0]
    refs: dict[tuple[int, str], DatasetRef] = {}
    for season in policy.historical_development_seasons:
        for dataset in R1_REQUIRED_DATASETS:
            uri = (
                f"{root}/derived/{season}/rating-input-ref-set.json"
                if dataset in {"byplay", "drives", "source_reconciliation"}
                else f"{root}/refs/{dataset}-{season}.json"
            )
            if dataset == "reconciled_team_game":
                uri = f"{root}/refs/reconciled_team_game-{season}.json"
            if dataset in {"byplay", "drives", "source_reconciliation"}:
                raw = json.loads(storage.read_bytes(uri).decode())
                if raw.get("schema_version") != "rating_input_ref_set_v1":
                    raise ValueError(f"Invalid R1 derived input ref set: {uri}")
                refs[(season, dataset)] = DatasetRef(**raw["outputs"][dataset])
            else:
                refs[(season, dataset)] = _ref(storage, uri)
    ref_set = derived_history_ref_set(
        policy,
        refs,
        source_set_uri=args.source_set_uri,
        source_set_sha256=str(source_set["manifest_sha256"]),
        identity=source_set.get("identity", {}),
    )
    _immutable_write(
        storage,
        args.output_uri,
        json.dumps(ref_set, indent=2, sort_keys=True).encode(),
    )
    print(json.dumps({"output_uri": args.output_uri, **ref_set}, sort_keys=True))


if __name__ == "__main__":
    main()
