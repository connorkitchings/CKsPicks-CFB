# Candidate Definitions

Each `*.yaml` file in this directory defines one research candidate for the
ratings laboratory. Candidates are loaded automatically by the lab CLI at
startup and merged into the code registry before any command runs.

## Schema

```yaml
candidate_id: exposure_k8_rho06_v1   # unique versioned identifier (required)
type: parameterized_exposure          # registered type (required; currently only this type)
k: 8.0                                # equivalent prior exposure in possessions (float > 0)
rho: 0.60                             # season-to-season carryover decay (0 < rho <= 1.0)
mode: incremental                     # "incremental" or "cumulative"
```

## Rules

- `candidate_id` must be unique across all YAML files and must not clash with
  any code-registered candidate (e.g. `carryover_only_rho_0_60_v1`).
- YAML files that fail parsing or validation raise an error at CLI startup.
- Add a version suffix (e.g. `_v1`) to candidate IDs so future sweeps do not
  collide with archived results.

## Adding a new candidate

1. Create a new `*.yaml` file here with the schema above.
2. Run `uv run python scripts/research/ratings_lab.py validate` to confirm
   the config loads without error.
3. Pass `--candidate <candidate_id>` to the `replay` and `evaluate` commands.

## Current files

| File | candidate_id | k | rho | mode |
|---|---|---|---|---|
| `exposure_k4_rho06_v1.yaml`  | `exposure_k4_rho06_v1`  | 4.0  | 0.60 | incremental |
| `exposure_k8_rho06_v1.yaml`  | `exposure_k8_rho06_v1`  | 8.0  | 0.60 | incremental |
| `exposure_k12_rho06_v1.yaml` | `exposure_k12_rho06_v1` | 12.0 | 0.60 | incremental |
| `exposure_k8_rho05_v1.yaml`  | `exposure_k8_rho05_v1`  | 8.0  | 0.50 | incremental |
| `exposure_k8_rho07_v1.yaml`  | `exposure_k8_rho07_v1`  | 8.0  | 0.70 | incremental |

`exposure_k8_rho06_v1` matches the V5 baseline hyperparameters (k=8, rho=0.60)
and can be used as a sanity-check reference under the common bridge.
