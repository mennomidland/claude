"""Behavioural test for replace-vs-union, run against the already-orphaned mediaId 50.

Those bytes are today's rendition of IMG_3908 1.jpg and are ALREADY stored, so every POST
here dedups onto an existing blob and creates nothing. The asset is scheduled for deletion
anyway, so tags written on it are disposable.
"""
import sys, os, json, hashlib
sys.path.insert(0, '/home/user/claude/tools')
import graph_check as g, ingest_library as il

DRIVE = 'b!kxUlnz9hTEGIP79tTDljrR9Yzea0cmdLraKjspDsTfIFN9XvZPm7RKua__mqYOLv'
ITEM  = '015HCHN4QC2Q4QR73WRNCZ6PE56UIDFYJ7'
GROUP = 'zztest:removal-semantics'
key = os.environ["MEDIA_INGEST_KEY"]

state = {}
ok, d = g.step2_token(state)
assert ok, d
img = il.fetch_bytes(state["token"], ITEM, 3024, 4032)
sha = hashlib.sha256(img).hexdigest()
print(f"bytes {len(img)} sha {sha[:16]}  (mediaId 50's blob -- must dedup, never create)\n")
b64 = il.base64.b64encode(img).decode()

def send(tags, label, extra=None):
    p = {"filename": "IMG_3908 1.jpg", "dataBase64": b64, "contentType": "image/jpeg",
         "tags": tags, "createMissingTags": True, "tagGroup": GROUP,
         "driveId": DRIVE, "itemId": ITEM}
    p.update(extra or {})
    st, r = il.post(p, key)
    assert r.get("isNew") is False and r.get("deduped") is True, \
        f"ABORT: expected dedup, got isNew={r.get('isNew')} deduped={r.get('deduped')}"
    print(f"--- {label}\n    sent {tags}" + (f" + {extra}" if extra else ""))
    print("    " + json.dumps(r))
    print()
    return r

send(["zztest:alpha", "zztest:beta"], "1. write two tags")
send(["zztest:alpha"],               "2. re-post with beta OMITTED  (replace -> beta gone)")
send(["zztest:alpha"],               "3. same again, with a removeTags field alongside",
     {"removeTags": ["zztest:beta"]})
