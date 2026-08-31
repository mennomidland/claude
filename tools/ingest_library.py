#!/usr/bin/env python3
"""The ONE path from the photo library into the QM3 media library.

Supersedes the ad-hoc ingest scripts. Everything goes through here, because the duplicate
that appeared in staging was caused by two scripts fetching bytes two different ways:
`20251029_153352.jpg` went in once from `/content` (3.0 MB original) and once from the
full-resolution rendition (784 KB). Same photo, same `(driveId,itemId)` occurrence,
different SHA -- so the library correctly stored two blobs and the gallery showed the
image twice.

Two mechanisms stop that recurring, and they are deliberately not optional:

1. **One byte source, not a parameter.** `fetch_bytes()` always returns the
   full-resolution Graph rendition. There is no flag to switch it back to `/content`.
   Same pixels, ~4x smaller, auto-oriented, and it stays under the 40 MB base64 cap.
2. **An occurrence ledger.** Every successful ingest records `(driveId,itemId) -> sha256`.
   Re-ingesting the same occurrence with DIFFERENT bytes is refused before the POST. Same
   bytes are allowed through, because re-tagging an unchanged asset is a normal operation
   and dedups server-side.

    python3 tools/ingest_library.py --records records.json [--ledger manifest/_ingested.json]
                                    [--dry-run]

`records.json` is a list of {item_id, caption, vision, audit} -- the tag records. Paths,
dimensions and `path_derived` come from the enumeration manifest, not from the record.
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import graph_check as g
from tag_vocabulary import tags_for, VISION_NAMESPACE, STATE_NAMESPACE

INGEST = "https://qm3staging.midlandind.com.au/api/media/ingest"
PROMPT_VERSION = "v4.0"
MODEL = "claude-opus-5"
MAX_B64_MB = 40


class DuplicateGuard(Exception):
    """Raised instead of creating a second blob for an occurrence already ingested."""


def fetch_bytes(token, item_id, width, height):
    """The full-resolution, auto-oriented rendition. THE ONLY BYTE SOURCE -- see module doc.

    The crop box is derived from Graph's `image` facet, which reports DISPLAY dimensions
    with EXIF rotation already applied. Using the stored pixel dimensions instead would
    request a landscape box for a portrait frame and `_Crop` would discard half the trailer.
    """
    if not (width and height):
        raise ValueError("Graph reported no image dimensions; cannot size the rendition")
    spec = f"c{width}x{height}_Crop"
    status, _, raw = g.request(
        f"{g.GRAPH}/drives/{g.DRIVE_ID}/items/{item_id}/thumbnails?select={spec}&expand={spec}",
        token=token)
    if status != 200:
        raise RuntimeError(f"thumbnails {status}: {raw[:200]}")
    sets = json.loads(raw).get("value") or []
    thumb = (sets[0].get(spec) if sets else None) or {}
    if not thumb.get("url"):
        raise RuntimeError(f"rendition {spec} not honoured")
    _, _, img = g.request(thumb["url"])
    return img


def load_ledger(path):
    return json.loads(path.read_text()) if path.exists() else {}


def check_and_record(ledger, drive_id, item_id, sha, dry_run=False):
    """Refuse a second blob for an occurrence already ingested with different bytes."""
    key = f"{drive_id}|{item_id}"
    prior = ledger.get(key)
    if prior and prior["sha256"] != sha:
        raise DuplicateGuard(
            f"occurrence already ingested with different bytes\n"
            f"    was {prior['sha256'][:16]}… via {prior.get('source')} "
            f"(mediaId {prior.get('media_id')})\n"
            f"    now {sha[:16]}…\n"
            f"    Ingesting would create a SECOND blob for the same photo. If the byte "
            f"source has deliberately changed, delete the old asset first, then remove "
            f"this key from the ledger.")
    if not dry_run:
        ledger[key] = {**(prior or {}), "sha256": sha, "source": "graph_rendition"}
    return prior is not None


def post(payload, key):
    body = json.dumps(payload).encode()
    mb = len(body) / 1e6
    if mb > MAX_B64_MB:
        # The API reports this as 400 "Invalid JSON body" -- a size limit wearing a parser
        # error's clothes. Fail here instead, where the message is true.
        raise RuntimeError(f"payload {mb:.1f} MB exceeds the {MAX_B64_MB} MB cap")
    status, _, resp = g.request(INGEST, method="POST", data=body,
                                headers={"Content-Type": "application/json",
                                         "x-media-key": key})
    return status, json.loads(resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--manifest", default="manifest/manifest.jsonl")
    ap.add_argument("--ledger", default="manifest/_ingested.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("MEDIA_INGEST_KEY")
    if not key and not args.dry_run:
        raise SystemExit("MEDIA_INGEST_KEY not set")

    records = json.loads(pathlib.Path(args.records).read_text())
    by_item = {}
    with open(args.manifest) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                by_item[r["photo"]["item_id"]] = r
    ledger_path = pathlib.Path(args.ledger)
    ledger = load_ledger(ledger_path)

    state = {}
    ok, detail = g.step2_token(state)
    if not ok:
        raise SystemExit(f"graph auth failed: {detail}")
    tok = state["token"]

    seen_sha, done, skipped, failed = {}, 0, 0, 0
    for rec in records:
        item_id = rec["item_id"]
        entry = by_item.get(item_id)
        if not entry:
            print(f"SKIP  {item_id} not in manifest"); skipped += 1; continue
        photo, pd = entry["photo"], entry["path_derived"]
        name = photo["filename"]
        try:
            img = fetch_bytes(tok, item_id, photo["width"], photo["height"])
            sha = hashlib.sha256(img).hexdigest()

            # Two different files with identical bytes is a real library duplicate --
            # worth surfacing, but not this script's to resolve.
            if sha in seen_sha and seen_sha[sha] != item_id:
                print(f"WARN  {name}: identical bytes to {seen_sha[sha]} (library duplicate)")
            seen_sha[sha] = item_id

            was_known = check_and_record(ledger, g.DRIVE_ID, item_id, sha, args.dry_run)
        except DuplicateGuard as e:
            print(f"BLOCK {name}: {e}"); failed += 1; continue
        except Exception as e:
            print(f"FAIL  {name}: {type(e).__name__}: {e}"); failed += 1; continue

        record = {"schema_version": "4.0", "vision": rec["vision"],
                  "audit": rec.get("audit", {}), "path_derived": pd}
        sets = tags_for(record, PROMPT_VERSION, MODEL)
        if args.dry_run:
            print(f"DRY   {name}: {len(sets[VISION_NAMESPACE])} search / "
                  f"{len(sets[STATE_NAMESPACE])} state, {len(img)/1e6:.1f} MB"
                  f"{' (re-tag)' if was_known else ''}")
            done += 1
            continue

        media_id = None
        for ns in (VISION_NAMESPACE, STATE_NAMESPACE):
            status, d = post({
                "filename": name, "dataBase64": base64.b64encode(img).decode(),
                "contentType": photo.get("mime_type") or "image/jpeg",
                "tags": sets[ns], "createMissingTags": True, "tagGroup": ns,
                "caption": rec.get("caption", ""), "sourcePath": photo["path"],
                "driveId": g.DRIVE_ID, "itemId": item_id,
            }, key)
            if status != 200:
                print(f"FAIL  {name} [{ns}]: HTTP {status} {str(d)[:120]}"); failed += 1; break
            media_id = d.get("mediaId")
        else:
            ledger[f"{g.DRIVE_ID}|{item_id}"].update(
                {"media_id": media_id, "filename": name, "path": photo["path"]})
            print(f"OK    {name}: mediaId={media_id} "
                  f"{len(sets[VISION_NAMESPACE])}/{len(sets[STATE_NAMESPACE])} tags"
                  f"{' (re-tag, deduped)' if was_known else ''}")
            done += 1

    if not args.dry_run:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True))
    print(f"\n{done} ingested, {skipped} skipped, {failed} failed. "
          f"Ledger holds {len(ledger)} occurrences.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
