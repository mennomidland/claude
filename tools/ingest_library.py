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
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import graph_check as g
from tag_vocabulary import tags_for, VISION_NAMESPACE, STATE_NAMESPACE

INGEST = "https://qm3staging.midlandind.com.au/api/media/ingest"
PROMPT_VERSION = "v4.1"
MODEL = "claude-opus-5"
MAX_B64_MB = 40


class DuplicateGuard(Exception):
    """Raised instead of creating a second blob for an occurrence already ingested."""


# --- tag removal -------------------------------------------------------------------
# A re-tag has to be able to RETRACT, not only add. The endpoint unions tag sets per
# (asset, tagGroup), so a tag written once cannot currently be taken off from here -- see
# `docs/routines/03-media-library-api.md` for the probe that establishes there is no field,
# no sibling route and no `-tag` prefix that does it.
#
# What this tool does about that, in order:
#
# 1. It KEEPS the tag set it wrote, per namespace, in the ledger -- not just a hash of it.
#    A hash tells you something changed; only the set itself tells you WHICH tags are now
#    wrong. Without this, removal is not computable even once the server supports it.
# 2. Every run diffs prior against current and records `prior - current` as pending
#    removals in a work list beside the ledger. That list is the exact, per-asset,
#    per-namespace set of tags to strike -- so the manual UI cleanup is a finite job of
#    known size rather than a hunt, and it survives the container.
# 3. When the server grows a removal route, set the two constants below. Nothing else has
#    to change: the diff is already being computed and the backlog is already recorded.
#    `tools/probe_tag_removal.py --phase 0` reports which values to use.
#
# The builder can ship removal in either of two shapes, and they are switched on
# differently, so both are supported rather than guessing which arrives:
#
#   "field"    an explicit list of tags to take off, e.g. `removeTags: [...]`. Set
#              REMOVAL_FIELD to the field name. The diff is sent alongside the additions.
#   "replace"  a re-POST replaces that namespace's whole set, as originally specified.
#              Removal is then implicit in the `tags` already being sent, and the only
#              thing to change is that the pending backlog may be considered cleared.
#
# One caveat that neither shape fixes on its own, and it is the important one: if removal
# still requires `dataBase64`, it does NOT unblock re-tagging. Graph re-encodes renditions
# across days, so there are no matching bytes left to send and every re-POST orphans a
# blob. Removal has to land on a route that identifies the asset without its bytes.
REMOVAL_MODE = None     # None | "field" | "replace"
REMOVAL_FIELD = None    # e.g. "removeTags" -- only read when REMOVAL_MODE == "field"


OVERSIZE = 6000   # larger than any original in the library; Graph clamps to native
RETRIES = 4       # the media host (*.svc.ms) resets connections intermittently


def _retry(fn, what):
    """Transient resets from the rendition host are common and are not failures."""
    last = None
    for attempt in range(RETRIES):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{what} failed after {RETRIES} attempts: {last}")


def _aspect_from_thumbnail(token, item_id):
    """Aspect ratio from the `large` thumbnail, scaled up past native resolution."""
    status, _, raw = g.request(
        f"{g.GRAPH}/drives/{g.DRIVE_ID}/items/{item_id}/thumbnails?select=large&expand=large",
        token=token)
    if status != 200:
        raise RuntimeError(f"cannot recover dimensions: thumbnails {status}")
    sets = json.loads(raw).get("value") or []
    large = (sets[0].get("large") if sets else None) or {}
    w, h = large.get("width"), large.get("height")
    if not (w and h):
        raise RuntimeError("no dimensions available from item or thumbnail")
    if w >= h:
        return OVERSIZE, max(1, round(OVERSIZE * h / w))
    return max(1, round(OVERSIZE * w / h)), OVERSIZE


def fetch_bytes(token, item_id, width, height):
    """The full-resolution, auto-oriented rendition. THE ONLY BYTE SOURCE -- see module doc.

    The crop box is derived from Graph's `image` facet, which reports DISPLAY dimensions
    with EXIF rotation already applied. Using the stored pixel dimensions instead would
    request a landscape box for a portrait frame and `_Crop` would discard half the trailer.
    """
    if not (width and height):
        # Graph returns an empty `image` facet for some real JPEGs. Recover the ASPECT
        # from a standard thumbnail and request an oversized box in that ratio: Graph
        # clamps to the native resolution, so this still yields the full-size rendition.
        # Guessing a square box instead would make `_Crop` discard half the frame.
        width, height = _retry(lambda: _aspect_from_thumbnail(token, item_id),
                               f'dimension recovery for {item_id}')
    spec = f"c{width}x{height}_Crop"

    def meta():
        status, _, raw = g.request(
            f"{g.GRAPH}/drives/{g.DRIVE_ID}/items/{item_id}/thumbnails?select={spec}&expand={spec}",
            token=token)
        if status != 200:
            raise RuntimeError(f"thumbnails {status}: {raw[:200]}")
        sets = json.loads(raw).get("value") or []
        thumb = (sets[0].get(spec) if sets else None) or {}
        if not thumb.get("url"):
            raise RuntimeError(f"rendition {spec} not honoured")
        return thumb["url"]

    url = _retry(meta, f"rendition metadata for {item_id}")
    return _retry(lambda: g.request(url)[2], f"rendition bytes for {item_id}")


def load_ledger(path):
    return json.loads(path.read_text()) if path.exists() else {}


def check_and_record(ledger, drive_id, item_id, sha, dry_run=False, photo=None):
    """Refuse a second blob for an occurrence already ingested with different bytes.

    `photo` carries the SOURCE file's own fingerprint (`quick_xor_hash`, `last_modified`).
    When the bytes differ but that fingerprint has not, the source photo did not change and
    Graph simply re-generated the rendition to different JPEG bytes -- which it does, see
    the rendition-stability finding in `docs/routines/03-media-library-api.md`. That is a
    completely different situation from someone replacing the file, and the operator has to
    be told which one they are looking at.
    """
    key = f"{drive_id}|{item_id}"
    prior = ledger.get(key)
    photo = photo or {}
    if prior and prior["sha256"] != sha:
        if prior.get("quick_xor_hash") is None:
            # Ledger written before source fingerprints were recorded. Say so rather than
            # guessing: "the file was replaced" and "Graph re-encoded the rendition" call
            # for opposite responses, and there is no evidence here to choose between them.
            cause = ("This ledger entry predates source fingerprinting, so the cause CANNOT "
                     "be told\n    apart from here. Re-check the source file's "
                     "quickXorHash against whatever\n    recorded it, or accept the "
                     "rendition as current with --force.")
        elif (prior["quick_xor_hash"] == photo.get("quick_xor_hash")
              and prior.get("last_modified") == photo.get("last_modified")):
            cause = ("The SOURCE FILE IS UNCHANGED (same quickXorHash and lastModified), so "
                     "this is\n    Graph re-generating the rendition, not a new photo. "
                     "Re-uploading would orphan\n    the existing blob for no gain. This is "
                     "what makes a tag-only update route\n    mandatory rather than merely "
                     "cheaper -- there is no way to re-send matching bytes.")
        else:
            cause = ("The source file's own hash has ALSO changed, so the photo in "
                     "SharePoint was replaced.\n    Decide which version the library should "
                     "hold, delete the superseded asset, then\n    remove this key from the "
                     "ledger.")
        raise DuplicateGuard(
            f"occurrence already ingested with different bytes\n"
            f"    was {prior['sha256'][:16]}… via {prior.get('source')} "
            f"(mediaId {prior.get('media_id')})\n"
            f"    now {sha[:16]}…\n"
            f"    {cause}")
    if not dry_run:
        ledger[key] = {**(prior or {}), "sha256": sha, "source": "graph_rendition",
                       "quick_xor_hash": photo.get("quick_xor_hash"),
                       "last_modified": photo.get("last_modified")}
    return prior is not None


def diff_tags(prior_sets, current_sets):
    """Per namespace: what this run adds, and what it must retract."""
    out = {}
    for ns, now in current_sets.items():
        was = set(prior_sets.get(ns) or [])
        out[ns] = {"add": sorted(set(now) - was), "remove": sorted(was - set(now))}
    return out


def record_removals(path, key, entry, removals, dry_run=False):
    """Append pending removals to the work list, keyed by occurrence and namespace.

    Pending removals ACCUMULATE across runs and are only cleared when something actually
    removes them. Two corrections in a row must not lose the first one's retraction just
    because the second run diffed against a ledger that already had it applied.
    """
    book = json.loads(path.read_text()) if path.exists() else {}
    rec = book.get(key) or {"pending": {}}
    changed = False
    for ns, tags in removals.items():
        if not tags:
            continue
        merged = sorted(set(rec["pending"].get(ns) or []) | set(tags))
        if merged != rec["pending"].get(ns):
            rec["pending"][ns] = merged
            changed = True
    if not changed:
        return 0
    rec.update({"filename": entry.get("filename"), "path": entry.get("path"),
                "media_id": entry.get("media_id")})
    book[key] = rec
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(book, indent=1, sort_keys=True))
    return sum(len(v) for v in rec["pending"].values())


def clear_removals(path, key, namespaces, dry_run=False):
    """Drop pending removals for namespaces the server has now actually retracted."""
    if not path.exists():
        return
    book = json.loads(path.read_text())
    rec = book.get(key)
    if not rec:
        return
    for ns in namespaces:
        rec["pending"].pop(ns, None)
    if not rec["pending"]:
        book.pop(key)
    if not dry_run:
        path.write_text(json.dumps(book, indent=1, sort_keys=True))


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
    ap.add_argument("--removals", help="pending-removal work list "
                                       "(default: alongside the ledger)")
    ap.add_argument("--force", action="store_true",
                    help="re-POST a namespace even when its tag set is unchanged")
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
    removals_path = pathlib.Path(args.removals or
                                 ledger_path.with_name(ledger_path.stem + "_removals.json"))

    state = {}
    ok, detail = g.step2_token(state)
    if not ok:
        raise SystemExit(f"graph auth failed: {detail}")
    tok = state["token"]

    seen_sha, done, skipped, failed, retracted = {}, 0, 0, 0, 0
    for rec in records:
        item_id = rec["item_id"]
        entry = by_item.get(item_id)
        if not entry:
            print(f"SKIP  {item_id} not in manifest"); skipped += 1; continue
        photo, pd = entry["photo"], entry["path_derived"]
        name = photo["filename"]

        # Compare tags BEFORE fetching bytes: if nothing changed there is no reason to
        # pull a multi-megabyte rendition only to discard it. The cost of this shortcut is
        # that a silently REPLACED source file with identical tags goes unnoticed here --
        # that is the enumeration delta's job (it watches lastModified), not this tool's.
        record = {"schema_version": "4.1", "vision": rec["vision"],
                  "audit": rec.get("audit", {}), "path_derived": pd}
        sets = tags_for(record, PROMPT_VERSION, MODEL)
        hashes = {ns: hashlib.sha256("\n".join(sets[ns]).encode()).hexdigest()
                  for ns in (VISION_NAMESPACE, STATE_NAMESPACE)}
        led_entry = ledger.get(f"{g.DRIVE_ID}|{item_id}") or {}
        prior_tags = led_entry.get("tag_hashes") or {}
        todo = [ns for ns in (VISION_NAMESPACE, STATE_NAMESPACE)
                if args.force or prior_tags.get(ns) != hashes[ns]]

        # What this run RETRACTS. Computed from the stored tag sets, not their hashes, and
        # computed before the unchanged-tags shortcut -- a namespace whose tag set is
        # unchanged retracts nothing, but a corrected one usually does, and that is the
        # whole point of re-tagging.
        deltas = diff_tags(led_entry.get("tags") or {}, sets)
        removals = {ns: d["remove"] for ns, d in deltas.items() if d["remove"]}
        if removals:
            pending = record_removals(removals_path, f"{g.DRIVE_ID}|{item_id}",
                                      {**led_entry, "filename": name,
                                       "path": photo["path"]}, removals, args.dry_run)
            for ns, tags in removals.items():
                print(f"RETRACT {name} [{ns.split(':')[-1]}]: {', '.join(tags)}")
            retracted += sum(len(t) for t in removals.values())
            if REMOVAL_MODE is None:
                print(f"      ^ recorded as pending ({pending} on this asset); the endpoint "
                      f"has no removal route, so these stay until struck in the UI")

        if not todo and led_entry.get("media_id"):
            print(f"SAME  {name}: tags unchanged, no bytes fetched or uploaded")
            skipped += 1
            continue

        try:
            img = fetch_bytes(tok, item_id, photo["width"], photo["height"])
            sha = hashlib.sha256(img).hexdigest()

            # Two different files with identical bytes is a real library duplicate --
            # worth surfacing, but not this script's to resolve.
            if sha in seen_sha and seen_sha[sha] != item_id:
                print(f"WARN  {name}: identical bytes to {seen_sha[sha]} (library duplicate)")
            seen_sha[sha] = item_id

            was_known = check_and_record(ledger, g.DRIVE_ID, item_id, sha, args.dry_run,
                                         photo)
        except DuplicateGuard as e:
            print(f"BLOCK {name}: {e}"); failed += 1; continue
        except Exception as e:
            print(f"FAIL  {name}: {type(e).__name__}: {e}"); failed += 1; continue

        if args.dry_run:
            print(f"DRY   {name}: {len(sets[VISION_NAMESPACE])} search / "
                  f"{len(sets[STATE_NAMESPACE])} state, {len(img)/1e6:.1f} MB"
                  f"{' (re-tag)' if was_known else ''}")
            done += 1
            continue

        entry = ledger[f"{g.DRIVE_ID}|{item_id}"]
        media_id = entry.get("media_id")
        for ns in todo:
            payload = {
                "filename": name, "dataBase64": base64.b64encode(img).decode(),
                "contentType": photo.get("mime_type") or "image/jpeg",
                "tags": sets[ns], "createMissingTags": True, "tagGroup": ns,
                "caption": rec.get("caption", ""), "sourcePath": photo["path"],
                "driveId": g.DRIVE_ID, "itemId": item_id,
            }
            if REMOVAL_MODE == "field" and deltas[ns]["remove"]:
                payload[REMOVAL_FIELD] = deltas[ns]["remove"]
            status, d = post(payload, key)
            if status != 200:
                print(f"FAIL  {name} [{ns}]: HTTP {status} {str(d)[:120]}"); failed += 1; break
            media_id = d.get("mediaId")
        else:
            # Store the SETS as well as their hashes. The hash answers "did anything
            # change"; only the set answers "which tags are now wrong", which is what a
            # retraction needs. ~1.4 KB per photo, ~56 MB across the library -- the price
            # of being able to correct the library at all.
            entry.update({"media_id": media_id, "filename": name, "path": photo["path"],
                          "bytes": len(img), "tag_hashes": hashes,
                          "tags": {ns: sets[ns] for ns in sets}})
            # "replace" retracts by omission -- the full current set was just sent, so
            # anything absent from it is gone. "field" retracts explicitly. Either way
            # only the namespaces actually POSTed in this run are cleared.
            if REMOVAL_MODE:
                clear_removals(removals_path, f"{g.DRIVE_ID}|{item_id}", todo, args.dry_run)
            saved = "" if len(todo) == 2 else f", {2 - len(todo)} namespace unchanged"
            print(f"OK    {name}: mediaId={media_id} "
                  f"{len(sets[VISION_NAMESPACE])}/{len(sets[STATE_NAMESPACE])} tags"
                  f"{' (re-tag, deduped)' if was_known else ''}{saved}")
            done += 1

    if not args.dry_run:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True))
    print(f"\n{done} ingested, {skipped} skipped, {failed} failed, "
          f"{retracted} tags retracted. Ledger holds {len(ledger)} occurrences.")
    if removals_path.exists():
        book = json.loads(removals_path.read_text())
        outstanding = sum(len(t) for r in book.values() for t in r["pending"].values())
        if outstanding:
            verb = ("still applied on the asset and must be struck in the UI"
                    if REMOVAL_MODE is None else "queued")
            print(f"{outstanding} retracted tags across {len(book)} assets are {verb}: "
                  f"{removals_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
