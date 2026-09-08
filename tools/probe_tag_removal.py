#!/usr/bin/env python3
"""Probe /api/media/ingest for ANY route that removes a tag.

Why this exists: re-POSTing tags to an existing (asset, namespace) unions rather than
replaces, so a wrong tag written once can only be cleared by hand in the UI. Before
accepting that as the state of the world, establish whether the endpoint already has a
removal or replace parameter that the earlier probe never tested. That probe only listed
field names it happened to SEND, and the schema is non-strict -- an unknown key is accepted
and silently dropped -- so absence of an error is not absence of the feature only if you
sent the name in the first place.

Phase 1 is safe by construction: every candidate is sent with a deliberately wrong type
(an integer where an array/bool/string/enum is expected), so a validator that recognises
the name answers 422 and stores NOTHING. A name that draws no error is either unknown or
happens to accept integers -- phase 2 disambiguates the few that matter.

    python3 tools/probe_tag_removal.py --phase 1
    python3 tools/probe_tag_removal.py --phase 2 --item-id <id> --drive-id <id>

Phase 2 writes. It is opt-in, it targets one asset you name, and it prints the tag sets it
sends so the effect can be read back in the UI.
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import graph_check as g
import ingest_library as il

INGEST = il.INGEST

# Every plausible spelling of "take these tags off" or "make this the whole set".
# Cheap to test, and missing one costs a permanent-tags conclusion that is simply wrong.
CANDIDATES = [
    "replaceTags", "removeTags", "clearTags", "deleteTags", "untag", "untagAll",
    "tagsToRemove", "tagsToAdd", "removedTags", "setTags", "overwriteTags",
    "replaceExisting", "replaceTagGroup", "clearTagGroup", "purgeTags", "resetTags",
    "syncTags", "exclusiveTags", "tagMode", "tagStrategy", "tagOperation", "tagsMode",
    "mode", "op", "operation", "replace", "merge", "append", "strategy",
    "deleteMissingTags", "removeMissingTags", "pruneTags",
]

# Known-good field names, included as a positive control: if these do NOT come back as
# errors then the probe is not reaching the validator and a null result means nothing.
CONTROLS = ["tags", "createMissingTags", "tagGroup", "filename"]


# Phase 1b: if the ingest payload has no removal field, maybe a sibling route does.
# Every id used here is deliberately absurd, so a route that exists and honours the method
# still has nothing to act on. 404/405 vs 401 is the signal: 405 means the path is real.
ROUTES = [
    ("OPTIONS", "/api/media/ingest"),
    ("GET", "/api/media/ingest"),
    ("DELETE", "/api/media/ingest"),
    ("PATCH", "/api/media/ingest"),
    ("PUT", "/api/media/ingest"),
    ("GET", "/api/media/999999999"),
    ("DELETE", "/api/media/999999999"),
    ("PATCH", "/api/media/999999999"),
    ("GET", "/api/media/999999999/tags"),
    ("PUT", "/api/media/999999999/tags"),
    ("DELETE", "/api/media/999999999/tags"),
    ("POST", "/api/media/tags"),
    ("POST", "/api/media/retag"),
    ("POST", "/api/media/untag"),
    ("POST", "/api/media/ingest/tags"),
    ("GET", "/api/media"),
    ("GET", "/api/tags"),
]

HOST = "https://qm3staging.midlandind.com.au"


def phase1b(key):
    print(f"{'method':8s} {'path':34s} status  body")
    for method, path in ROUTES:
        data = b"{}" if method in ("POST", "PUT", "PATCH") else None
        status, _, body = g.request(HOST + path, method=method, data=data, follow=False,
                                    headers={"Content-Type": "application/json",
                                             "x-media-key": key})
        snippet = (body or b"")[:110].decode("utf-8", "replace").replace("\n", " ")
        print(f"{method:8s} {path:34s} {status:6d}  {snippet}")


def phase0(key):
    """Has removal landed yet, and what should ingest_library's constants be set to?

    Run this after the builder ships. It answers the only two questions that matter --
    which field name the validator now accepts, and whether the route still demands bytes.
    """
    hits = phase1(key)
    print()
    if hits:
        print(f"REMOVAL HAS LANDED. Set in tools/ingest_library.py:")
        print(f'    REMOVAL_MODE  = "field"')
        print(f'    REMOVAL_FIELD = "{hits[0]}"')
        if len(hits) > 1:
            print(f"    (validator also recognises {', '.join(hits[1:])} -- check which is "
                  f"the real one before choosing)")
    else:
        print("No removal field yet. If the builder shipped REPLACE semantics instead --")
        print("a re-POST replacing the namespace's whole set -- there is no field to")
        print("detect: confirm it in the UI (an asset should stop showing the older")
        print('promptver: tag) and then set REMOVAL_MODE = "replace".')

    print()
    print("Does the route still demand bytes? -- the question that decides whether removal")
    print("actually unblocks re-tagging:")
    for missing in ("dataBase64",):
        status, resp = il.post({"filename": "probe.jpg", "tags": [], "tagGroup": "zzprobe"},
                               key)
        msg = json.dumps(resp)[:160]
        print(f"    POST without {missing}: HTTP {status}  {msg}")
    print("    A 422 here means bytes are still mandatory, so a re-tag STILL cannot be")
    print("    performed -- Graph re-encodes renditions across days and there are no")
    print("    matching bytes left to send. Removal without a byte-free route is not enough.")
    return hits


def probe(key, names):
    payload = {n: 12345 for n in names}
    payload["dataBase64"] = 12345
    status, resp = il.post(payload, key)
    return status, resp


def field_names(resp):
    """Pull whatever field paths the validator names out of its error body."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            for k in ("path", "field", "name"):
                v = node.get(k)
                if isinstance(v, str):
                    out.add(v)
                elif isinstance(v, list) and v:
                    out.add(".".join(str(x) for x in v))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(resp)
    return out


def phase1(key):
    status, resp = probe(key, CANDIDATES + CONTROLS)
    print(f"HTTP {status}")
    print(json.dumps(resp, indent=1)[:4000])
    named = field_names(resp)
    text = json.dumps(resp)
    recognised = sorted(n for n in CANDIDATES + CONTROLS if n in named or f'"{n}"' in text)
    ctl = [n for n in CONTROLS if n in recognised]
    print("\n--- controls recognised:", ctl or "NONE -- probe did not reach the validator")
    if not ctl:
        raise SystemExit("inconclusive: the validator did not name known-good fields")
    hits = [n for n in recognised if n in CANDIDATES]
    print("--- removal/replace candidates recognised:", hits or "NONE")
    return hits


def phase2(key, drive_id, item_id, filename, tags, tag_group, extra, ledger_path):
    """Send one real, minimal tag set to an existing asset and report the response.

    Goes through the SAME duplicate guard as a real ingest. The first version of this probe
    did not, and created an orphaned second blob (mediaId 50) for a photo already in the
    library, because Graph had re-generated the rendition to different bytes since the
    ledger was written. A probe that can create duplicates is not an acceptable probe --
    the guard is the whole defence and nothing may route around it.
    """
    state = {}
    ok, detail = g.step2_token(state)
    if not ok:
        raise SystemExit(f"graph auth failed: {detail}")
    ledger = il.load_ledger(pathlib.Path(ledger_path))
    st, _, raw = g.request(f"{g.GRAPH}/drives/{drive_id}/items/{item_id}"
                           "?select=name,image,file,lastModifiedDateTime",
                           token=state["token"])
    if st != 200:
        raise SystemExit(f"item lookup {st}: {raw[:200]}")
    meta = json.loads(raw)
    im = meta.get("image") or {}
    photo = {"quick_xor_hash": ((meta.get("file") or {}).get("hashes") or {}).get("quickXorHash"),
             "last_modified": meta.get("lastModifiedDateTime")}
    img = il.fetch_bytes(state["token"], item_id, im.get("width"), im.get("height"))
    sha = il.hashlib.sha256(img).hexdigest()
    il.check_and_record(ledger, drive_id, item_id, sha, dry_run=True, photo=photo)
    b64 = il.base64.b64encode(img)
    payload = {
        "filename": filename, "dataBase64": b64.decode(), "contentType": "image/jpeg",
        "tags": tags, "createMissingTags": True, "tagGroup": tag_group,
        "driveId": drive_id, "itemId": item_id,
    }
    payload.update(extra)
    print("sending tags:", tags, "extra:", extra)
    status, resp = il.post(payload, key)
    print(f"HTTP {status}")
    print(json.dumps({k: resp.get(k) for k in
                      ("mediaId", "isNew", "deduped", "appliedTags", "skippedTags")},
                     indent=1)[:2000])
    return status, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--drive-id")
    ap.add_argument("--item-id")
    ap.add_argument("--filename")
    ap.add_argument("--tag-group", default="trailer-photo:probe")
    ap.add_argument("--tags", default="")
    ap.add_argument("--extra", default="{}", help="JSON of extra top-level fields to send")
    ap.add_argument("--ledger", default="docs/test-run/goldset40-ledger.json",
                    help="occurrence ledger the duplicate guard checks against")
    args = ap.parse_args()

    key = os.environ.get("MEDIA_INGEST_KEY")
    if not key:
        raise SystemExit("MEDIA_INGEST_KEY not set")

    if args.phase == 0:
        phase0(key)
    elif args.phase == 1:
        phase1(key)
    elif args.phase == 11:
        phase1b(key)
    else:
        tags = [t for t in args.tags.split(",") if t]
        phase2(key, args.drive_id, args.item_id, args.filename, tags,
               args.tag_group, json.loads(args.extra), args.ledger)


if __name__ == "__main__":
    main()
