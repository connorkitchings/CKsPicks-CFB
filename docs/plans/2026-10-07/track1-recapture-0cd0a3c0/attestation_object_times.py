"""Read-only: HEAD the two Week 5 attestation objects and report when R2 recorded them."""

import json
import sys

sys.path.insert(0, "src")
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from cks_picks_cfb.data.storage.base import StorageSettings  # noqa: E402
from cks_picks_cfb.rebuild.targets import R2ObjectStore  # noqa: E402

RUN = "2026w5-v5repair-20260929-p2"
OBJECTS = {
    "preview": "9b3d04f3c72448aa712b9814a0a1aadedcc709946108d15cf1622b17452d31f6",
    "production": "9f0224181c02865e125ef8a00cbcf518ae7f1bcb194365564bd5d90b5dd472d7",
}
s = StorageSettings.from_env(environment="preview")
store = R2ObjectStore(
    bucket=s.bucket,
    account_id=s.account_id,
    access_key=s.access_key,
    secret_key=s.secret_key,
    endpoint=s.endpoint,
)
out = {}
for env, sha in OBJECTS.items():
    key = (
        f"artifacts/prospective/v5/environment={env}/season=2026/week=5/{RUN}/"
        f"legacy-attestation-v1-{sha}.json"
    )
    head = store.client.head_object(Bucket=store.bucket, Key=key)
    out[env] = {
        "last_modified": head["LastModified"].isoformat(),
        "content_length": head["ContentLength"],
        "etag": head["ETag"],
    }
print(json.dumps(out, indent=1))
