"""Read-only B6: re-hash the published 6B root and every object it lists (GET only)."""
import hashlib, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from cks_picks_cfb.data.storage.base import StorageSettings
from cks_picks_cfb.rebuild.targets import R2ObjectStore
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

RUN = "6b-replay-20261005-r1"
s = StorageSettings.from_env(environment="preview")
assert s.backend == "r2" and s.bucket, "preview r2 not configured"
store = R2ObjectStore(bucket=s.bucket, account_id=s.account_id, access_key=s.access_key,
                      secret_key=s.secret_key, endpoint=s.endpoint)
out = {"storage_identity": store.identity}
root_key = f"rebuild/6b/{RUN}/root-manifest.json"
raw = store.read(root_key)
out["root_key"] = root_key
out["root_raw_sha256"] = hashlib.sha256(raw).hexdigest()
root = json.loads(raw)
verify_signed_payload(root, label="6B root")
out["root_signature_ok"] = True
out["root_manifest_sha256"] = root["manifest_sha256"]
out["code_sha"] = root["code_sha"]; out["publisher_code_sha"] = root["publisher_code_sha"]
out["verify_sha"] = root["verify_sha"]; out["stages"] = len(root["stages"])
bad, n = [], 0
for key, digest in root["objects"].items():
    n += 1
    if hashlib.sha256(store.read(key)).hexdigest() != digest:
        bad.append(key)
out["objects_listed"] = n; out["objects_mismatched"] = bad
print(json.dumps(out, indent=1))
