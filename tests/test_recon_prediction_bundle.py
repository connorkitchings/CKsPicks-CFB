"""Which inference bundle the 6B replay applies: the plan's pinned one, else the 6A refit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from cks_picks_cfb.rebuild.recon_forecast import prediction_bundle

REPO = Path(__file__).resolve().parents[1]


def _context(pinned: bytes | None):
    inputs = [SimpleNamespace(name="root_manifest_6a")]
    if pinned is not None:
        inputs.append(SimpleNamespace(name="inference_bundle"))
    return SimpleNamespace(
        plan=SimpleNamespace(inputs=inputs),
        read_input=lambda name: pinned if name == "inference_bundle" else b"?",
    )


class _Run:
    def run_key(self, relative: str) -> str:
        return f"rebuild/6a/run-x/{relative}"

    def read(self, key: str) -> bytes:
        assert key == "rebuild/6a/run-x/forecast/bundle.json"
        return b'{"from": "6a"}'


def test_a_plan_without_the_input_keeps_the_6a_refit_and_its_reference():
    raw, ref = prediction_bundle(_context(None), _Run())
    assert raw == b'{"from": "6a"}'
    assert ref == (
        "rebuild/6a/run-x/forecast/bundle.json#sha256="
        + hashlib.sha256(raw).hexdigest()
    )


def test_a_plan_with_the_input_applies_exactly_those_bytes():
    pinned = b'{"from": "pinned"}'
    raw, ref = prediction_bundle(_context(pinned), _Run())
    assert raw == pinned
    assert ref == "inference_bundle#sha256=" + hashlib.sha256(pinned).hexdigest()


def _pins(plan: str) -> dict[str, dict]:
    doc = yaml.safe_load((REPO / "conf/rebuild" / plan).read_text())
    return {pin["name"]: pin for pin in doc["inputs"]}, doc


def test_the_corrected_plan_pins_the_committed_bundle_and_declares_it_to_predictions():
    pins, doc = _pins("6b_w5_v2.yaml")
    pin = pins["inference_bundle"]
    raw = (REPO / pin["uri"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
    provenance = json.loads(
        (REPO / "conf/rebuild/bundle_b2_w5_v1.provenance.json").read_text()
    )
    assert provenance["bundle_raw_sha256"] == pin["sha256"]
    stage = next(s for s in doc["stages"] if s["name"] == "predictions")
    assert "inference_bundle" in stage["inputs"]
    assert json.loads(raw)["schema_version"] == "v5_inference_bundle_v1"


def test_the_earlier_plans_do_not_name_a_bundle_so_they_still_reproduce():
    for plan in ("6b_v1.yaml", "6b_w5_v1.yaml"):
        pins, _ = _pins(plan)
        assert "inference_bundle" not in pins
