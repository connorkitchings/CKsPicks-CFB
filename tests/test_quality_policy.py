import json
from pathlib import Path

import pytest

from cks_picks_cfb.quality.checks import run_stage
from cks_picks_cfb.quality.policy import load_required_policy

POLICY = Path(__file__).resolve().parents[1] / "conf/quality/repair_v1.json"


def test_repair_policy_registers_stage_requirements_and_blocks_absent_evidence():
    policy = load_required_policy(POLICY)
    assert policy["ingest"] and policy["silver"] and policy["gold"]
    assert run_stage("gold", {}, required_checks=policy["gold"]).blocked


def test_policy_refuses_unknown_or_wrong_stage_check(tmp_path):
    value = json.loads(POLICY.read_text())
    value["stages"]["ingest"].append("silver.points_identity")
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="wrong-stage"):
        load_required_policy(path)
