"""Offline evidence review, including all database fields and write timestamps.

Usage: uv run python docs/plans/2026-10-10/adjusted-row-investigation/verify-evidence.py
Outputs go to a new exclusive review directory; failed runs remain intact.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
KEY = ("season", "as_of_week", "team", "role", "measurement_id")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def main():
    inputs = {}
    snapshots = {}
    for environment in ("preview", "production"):
        folder = BASE / f"{environment}-final"
        raw = (folder / "receipt.json").read_bytes()
        inputs[f"{environment}-final/receipt.json"] = digest(raw)
        receipt = json.loads(raw)
        signature = receipt.pop("receipt_sha256")
        assert digest(canonical(receipt)) == signature
        assert receipt["status"] == "passed" and receipt["unresolved_count"] == 0
        for name, expected in receipt["outputs"].items():
            assert digest((folder / name).read_bytes()) == expected, name
        snapshots[environment] = json.loads((folder / "snapshot.json").read_bytes())
        explanations = json.loads((folder / "source-explanations.json").read_bytes())
        assert len(explanations) == 95
        assert all(
            e["classification"] == "supported_exclusion_recommendation"
            for e in explanations
        )
        assert all(
            e["legacy_row_reproduced"] and e["current_disposition"] == "unchanged"
            for e in explanations
        )
    a, b = [
        {tuple(row[k] for k in KEY): row for row in snapshots[env]["rows"]}
        for env in ("preview", "production")
    ]
    assert a.keys() == b.keys() and len(a) == 2611
    differences = []
    for key in sorted(a):
        assert a[key].keys() == b[key].keys()
        for field in a[key]:
            if a[key][field] != b[key][field]:
                assert field == "updated_at", (key, field)
                differences.append(
                    {
                        **dict(zip(KEY, key, strict=True)),
                        "field": field,
                        "preview": a[key][field],
                        "production": b[key][field],
                        "disposition": "operational_metadata",
                        "evidence": "Business fields identical to verified historical snapshot or corrected candidate; environment-specific upsert sets updated_at=NOW(). See matchup_data.upsert_sql and publication snapshot.",
                    }
                )
    assert snapshots["preview"]["game_names"] == snapshots["production"]["game_names"]
    output = BASE / "review-final"
    output.mkdir(exist_ok=False)
    path = output / "metadata-differences.csv"
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(KEY)
            + ["field", "preview", "production", "disposition", "evidence"],
        )
        writer.writeheader()
        writer.writerows(differences)
    result = {
        "status": "passed",
        "inputs": inputs,
        "code_sha256": digest(Path(__file__).read_bytes()),
        "shared_keys": len(a),
        "metadata_differences": len(differences),
        "outputs": {path.name: digest(path.read_bytes())},
    }
    result["receipt_sha256"] = digest(canonical(result))
    with (output / "receipt.json").open("xb") as stream:
        stream.write(canonical(result))
    print(
        f"Verified final receipts, outputs, exact keys and all fields; {len(differences)} explained timestamp differences."
    )


if __name__ == "__main__":
    main()
