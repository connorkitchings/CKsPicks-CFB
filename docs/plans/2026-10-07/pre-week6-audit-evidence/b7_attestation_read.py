import hashlib, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from cks_picks_cfb.data.storage.base import StorageSettings
from cks_picks_cfb.rebuild.targets import R2ObjectStore
P="2026w5-v5repair-20260929-p2"
out={}
for env,sha in (("preview","9b3d04f3c72448aa712b9814a0a1aadedcc709946108d15cf1622b17452d31f6"),("production","9f0224181c02865e125ef8a00cbcf518ae7f1bcb194365564bd5d90b5dd472d7")):
    try:
        s=StorageSettings.from_env(environment=env)
        st=R2ObjectStore(bucket=s.bucket,account_id=s.account_id,access_key=s.access_key,secret_key=s.secret_key,endpoint=s.endpoint)
        key=f"artifacts/prospective/v5/environment={env}/season=2026/week=5/{P}/legacy-attestation-v1-{sha}.json"
        raw=st.read(key); d=json.loads(raw)
        out[env]={"bucket_identity":st.identity,"raw_sha256":hashlib.sha256(raw).hexdigest(),"filename_sha_matches":hashlib.sha256(raw).hexdigest()==sha or "differs (raw bytes vs canonical payload hash; compare payload_sha below)","freeze_pipeline_null":d.get("freeze_pipeline") is None,"limitations":d.get("limitations"),"attested_at":d.get("attested_at"),"decision_ref":d.get("decision_ref")}
    except Exception as e:
        out[env]={"error":type(e).__name__+": "+str(e)[:200]}
print(json.dumps(out,indent=1,default=str))
