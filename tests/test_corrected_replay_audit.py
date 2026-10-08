import json

import pytest

from scripts.pipeline.audit_corrected_replay_chain import ReadOnlyEvidence, audit


@pytest.mark.parametrize("weeks", [[], ["0"], [str(w) for w in range(7)]])
def test_audit_refuses_incomplete_or_expanded_c2_scope(tmp_path, weeks):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"market_sources": dict.fromkeys(weeks, {})}))
    with pytest.raises(ValueError, match="exactly Weeks"):
        audit(
            object(),
            lock_path=lock,
            release_tag="test",
            bridge_uri="bridge",
            rating_uri="ratings",
            expected_bundle_sha="a" * 64,
        )


def test_evidence_wrapper_has_no_write_interface():
    assert not hasattr(ReadOnlyEvidence(object()), "write_bytes")
