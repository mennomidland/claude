#!/usr/bin/env python3
"""Enumerate the Midland sales photo library via Microsoft Graph /delta.

Replaces the recursive folder walk in routines/01-enumeration.md. Delta returns a flat
list of every descendant with its parent path, so there is no walk to get wrong and the
"folder looks empty because it only holds subfolders" failure mode cannot occur.

Read-only on SharePoint. Writes only to --out.

    python3 tools/enumerate_delta.py --out manifest/
    python3 tools/enumerate_delta.py --out manifest/ --resume    # only what changed

`--resume` reuses the stored delta token, so the second run over a 216 GB library sees
the handful of changed items rather than re-reading the tree.

Never asks a model for anything. Every derived field comes from the path.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from graph_check import GRAPH, DRIVE_ID, LIBRARY_ROOT, Blocked, request, step2_token

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".bmp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".m4v", ".mts", ".wmv", ".mpg", ".mpeg", ".3gp", ".mkv"}
DOC_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv"}

# Folder name -> what the frames in it are expected to be. Applied from the path only;
# the vision pass sets `content_purpose` per frame and never inherits this.
CONTENT_EXPECTATION = {
    "z. Opposition Trailers": "competitor",
    "z.Creo Trailer Image Files": "render",
    "Trailer Drawings": "drawing",
    "Brochures": "brochure_or_document",
    "z.Tare Weights": "brochure_or_document",
    "z.Close Up Photos of Trailer Parts": "component_detail",
    "z.BiFold Ramps Photos": "component_detail",
    "Drone Items": "aerial",
    "z Second Hand and Miscelaneous": "second_hand_or_misc",
}

# House vocabulary: two axles is a Tandem. "bogie" is not Midland's word and appears
# nowhere in this project's output. Single / Tandem / Tri / Quad.
AXLE_WORDS = [
    (re.compile(r"\bsingle\b", re.I), "single"),
    (re.compile(r"\btandem\b", re.I), "tandem"),
    (re.compile(r"\btri[- ]?axle\b|\btri\b", re.I), "tri"),
    (re.compile(r"\bquad\b", re.I), "quad"),
]
# "1. Semi..." and "2.Drop Deck..." alike. Deliberately 1-2 digits: `^\d+\.` would eat
# the year off a date-named folder and turn "2025.08 - Team Transport ..." into
# "08 - Team Transport ...".
NUM_PREFIX = re.compile(r"^\d{1,2}\.\s*")
JOB_NUMBERS = re.compile(r"\b(\d{4})\b")
BUILD_DATE = re.compile(r"\b(20\d{2})[.\-/](\d{2})\b")
# Camera defaults. A run of these in one folder is normally one shoot of one trailer.
#
# Derived from the actual library, not guessed: an earlier, shorter version of this list
# flagged 58% of the library as "descriptively named", including all 18,860 GoPro
# `G0012102` frames in Drone Items. That is not a cosmetic error -- a descriptive name
# breaks a shoot run and is treated as free ground truth, so under-matching here both
# destroys shoot grouping and poisons the validation set.
_DUP_SUFFIX = re.compile(
    r"(\s*\(\d+\)|[_-]\d{1,2}|-min|-Edit(ed)?|\s*-\s*Copy|_resized|"
    r"\.(jpe?g|png|heic|tiff?|mp4|mov))$", re.I)   # trailing ext: `DSC_0661.JPG.xmp` sidecars
CAMERA_PATTERNS = [
    r"(IMG|DSC|DSCN|MVI|VID|PXL|GOPR|DJI|PANO|MOV|SAM|FILE|PICT|CIMG|SDC)[_-]?\d{3,}",
    r"IMG[_-]\d{8}[_-]\d{6}",              # Android:  IMG_20151208_163118
    r"IMG[_-]\d{8}[_-]WA\d{3,}",           # WhatsApp: IMG-20240604-WA0001
    r"IMG[_-]\d{8}[_-]\d{3,}",             # IMG-20120608-00208
    r"G[XH]?\d{6,8}",                      # GoPro:    G0012102, GX010123
    r"P\d{7}",                             # Panasonic
    r"\d{8}[_-]\d{6,9}(_iOS)?",            # 20250123_164442, 20230905_232015650_iOS
    r"\d{1,13}",                           # bare counters and epoch-ms: 1.JPG, 1730318447042
    r"WhatsApp (Image|Video) \d{4}-\d{2}-\d{2} at [\d.]+ ?[AP]M",
]
CAMERA_DEFAULT = re.compile(r"^(?:%s)$" % "|".join(CAMERA_PATTERNS), re.I)


def is_descriptive(stem):
    """True when a filename carries real words rather than a camera counter.

    Strips a duplicate/edit suffix first, so `IMG_0435 (2)` and `DSC00204-min` are still
    recognised as the camera names they are.
    """
    return not bool(CAMERA_DEFAULT.match(_DUP_SUFFIX.sub("", stem).strip()))


def media_class(ext):
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in DOC_EXT:
        return "document"
    return "other"


def axle_from_path(segments):
    """Only where a path segment states it. Never inferred from product category."""
    for seg in segments:
        for pattern, value in AXLE_WORDS:
            if pattern.search(seg):
                return value
    return "unstated"


def parse_path(rel_segments):
    """Everything the folder tree already knows. Never pay a model for any of this."""
    product = rel_segments[0] if rel_segments else None
    # Level 2 is a numbered variant in some categories ("1. Semi Drop Deck Trailers",
    # "2. Tandem Axle Tag Trailer") but a date-named customer folder in others, where
    # Skel Trailers goes straight to "2025.08 - Team Transport (BH) Quad Skels - 3467".
    # A date folder is not a variant, so leave it null rather than inventing one.
    variant = None
    if len(rel_segments) > 1 and not BUILD_DATE.match(rel_segments[1]):
        variant = NUM_PREFIX.sub("", rel_segments[1]) or None

    deep = " / ".join(rel_segments[1:])
    date_hit = BUILD_DATE.search(deep)
    # Strip the build date before looking for job numbers: `\b\d{4}\b` matches the year in
    # "2025.08 - Team Transport (BH) Quad Skels - 3467, 3468" just as happily as it
    # matches 3467, and a phantom job 2025 would join to the wrong card.
    jobs = JOB_NUMBERS.findall(BUILD_DATE.sub(" ", deep))
    customer = None
    for seg in rel_segments[1:]:
        # "2025.08 - Team Transport (BH) Quad Skels - 3467, 3468" -> "Team Transport (BH) Quad Skels"
        parts = [p.strip() for p in seg.split(" - ")]
        if len(parts) >= 2 and BUILD_DATE.match(parts[0]):
            customer = parts[1] or None
            break

    return {
        "product_category": product,
        "variant": variant,
        "axle_config_from_path": axle_from_path(rel_segments),
        "customer": customer,
        "build_date": f"{date_hit.group(1)}.{date_hit.group(2)}" if date_hit else None,
        "job_numbers": sorted(set(jobs)),
        "content_expectation": CONTENT_EXPECTATION.get(product, "midland_trailer"),
        "folder_path": "/".join(rel_segments),
    }


TIMESTAMP_NAME = re.compile(r"(\d{8})[_-](\d{6})")
COUNTER_NAME = re.compile(r"^(.*?)(\d+)$")
COUNTER_GAP = 10       # frames; a burst numbers consecutively, a new shoot jumps
TIMESTAMP_GAP = 3 * 3600


def _sequence_key(record):
    """(prefix, ordinal) for ordering and gap detection within a folder."""
    stem = _DUP_SUFFIX.sub("", pathlib.Path(record["photo"]["filename"]).stem).strip()
    ts = TIMESTAMP_NAME.search(stem)
    if ts:
        d, t = ts.group(1), ts.group(2)
        seconds = int(t[0:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:6])
        return ("ts", int(d) * 86400 + seconds, True)
    m = COUNTER_NAME.match(stem)
    if m:
        return (m.group(1).lower(), int(m.group(2)), False)
    return (stem.lower(), 0, False)


def assign_shoot_groups(records):
    """Group each run of *consecutive* camera-default filenames within one folder.

    Consecutive is the operative word and it has to be enforced, not assumed. Grouping
    every camera-default file in a folder into one run put all 1,017 frames of
    `Drone Items/143GOPRO` -- spanning seven separate dates -- into a single "shoot".

    A run therefore breaks on any of: a descriptive filename (somebody naming one specific
    thing is not part of a burst), a change of filename prefix, a jump in the counter, or
    a change of capture date.
    """
    by_folder = {}
    for r in records:
        by_folder.setdefault(r["path_derived"]["folder_path"], []).append(r)

    for folder, items in by_folder.items():
        items.sort(key=lambda r: (_sequence_key(r), r["photo"]["filename"].lower()))
        group_index, position = 0, 0
        prev_key, prev_day = None, None
        for r in items:
            photo = r["photo"]
            if photo["filename_is_descriptive"]:
                photo["shoot_group"] = None
                photo["shoot_group_position"] = None
                group_index += 1          # a named file ends the run either side of it
                position, prev_key, prev_day = 0, None, None
                continue

            prefix, ordinal, is_ts = _sequence_key(r)
            day = (photo["last_modified"] or "")[:10]
            if prev_key is not None:
                gap = TIMESTAMP_GAP if is_ts else COUNTER_GAP
                if (prefix != prev_key[0] or ordinal - prev_key[1] > gap
                        or (day and prev_day and day != prev_day)):
                    group_index += 1
                    position = 0
            position += 1
            photo["shoot_group"] = f"{folder}#{group_index}"
            photo["shoot_group_position"] = position
            prev_key, prev_day = (prefix, ordinal), day


def enumerate_library(token, out_dir, resume):
    root_path = urllib.parse.quote(LIBRARY_ROOT)
    status, _, body = request(f"{GRAPH}/drives/{DRIVE_ID}/root:/{root_path}", token=token)
    if status != 200:
        raise SystemExit(f"cannot resolve {LIBRARY_ROOT}: {status} {body[:200]}")
    root = json.loads(body)
    prefix = f"/drives/{DRIVE_ID}/root:/{LIBRARY_ROOT}"

    token_file = out_dir / "_delta_token.json"
    url = None
    if resume and token_file.exists():
        url = json.loads(token_file.read_text()).get("deltaLink")
        print(f"resuming from stored delta token ({token_file})")
    if not url:
        # Scope delta to the library folder, not the drive root: the drive is the whole
        # Shared Documents library and the project scope is this folder only.
        url = f"{GRAPH}/drives/{DRIVE_ID}/items/{root['id']}/delta"

    records, pages, skipped_folders, deleted = [], 0, 0, []
    while url:
        status, _, body = request(url, token=token)
        if status != 200:
            raise SystemExit(f"delta failed on page {pages}: {status} {body[:300]}")
        page = json.loads(body)
        for item in page.get("value", []):
            if "deleted" in item:
                deleted.append(item["id"])
                continue
            if "folder" in item:
                skipped_folders += 1
                continue
            parent = (item.get("parentReference") or {}).get("path", "")
            if not parent.startswith(prefix):
                continue  # defensive: delta should stay in scope, but do not assume it
            rel = [s for s in parent[len(prefix):].strip("/").split("/") if s]
            rel = [urllib.parse.unquote(s) for s in rel]
            name = item["name"]
            ext = pathlib.Path(name).suffix.lower()
            image = item.get("image") or {}
            records.append({
                "photo": {
                    "drive_id": DRIVE_ID,
                    "item_id": item["id"],
                    "path": f"{LIBRARY_ROOT}/{'/'.join(rel)}/{name}" if rel else f"{LIBRARY_ROOT}/{name}",
                    "filename": name,
                    "extension": ext,
                    "media_class": media_class(ext),
                    "size_bytes": item.get("size", 0),
                    "last_modified": item.get("lastModifiedDateTime"),
                    "depth": len(rel),
                    "filename_is_descriptive": is_descriptive(pathlib.Path(name).stem),
                    "quick_xor_hash": ((item.get("file") or {}).get("hashes") or {}).get("quickXorHash"),
                    "mime_type": (item.get("file") or {}).get("mimeType"),
                    # Graph reports DISPLAY dimensions (EXIF applied). Use these for the
                    # thumbnail crop box -- the stored pixels may be transposed.
                    "width": image.get("width"),
                    "height": image.get("height"),
                    "shoot_group": None,
                    "shoot_group_position": None,
                },
                "path_derived": parse_path(rel),
            })
        pages += 1
        url = page.get("@odata.nextLink")
        if not url and page.get("@odata.deltaLink"):
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(json.dumps({"deltaLink": page["@odata.deltaLink"]}, indent=1))
        if pages % 25 == 0:
            print(f"  page {pages}, {len(records)} files so far", flush=True)

    return records, {"pages": pages, "folders": skipped_folders, "deleted": deleted}


def merge_with_existing(changed, deleted_ids, manifest_path):
    """A delta run returns only what changed, so fold it into the prior manifest.

    Without this, --resume would overwrite a full manifest with the handful of changed
    records and silently destroy the work queue.
    """
    prior = []
    if manifest_path.exists():
        with manifest_path.open() as fh:
            prior = [json.loads(line) for line in fh if line.strip()]
    by_id = {r["photo"]["item_id"]: r for r in prior}
    for r in changed:
        by_id[r["photo"]["item_id"]] = r
    for item_id in deleted_ids:
        by_id.pop(item_id, None)
    return list(by_id.values()), len(prior)


def summarise(records):
    per = {}
    for r in records:
        cat = r["path_derived"]["product_category"] or "(root)"
        s = per.setdefault(cat, {"files": 0, "image": 0, "video": 0, "document": 0,
                                 "other": 0, "bytes": 0, "max_depth": 0, "shoots": set()})
        s["files"] += 1
        s[r["photo"]["media_class"]] += 1
        s["bytes"] += r["photo"]["size_bytes"]
        s["max_depth"] = max(s["max_depth"], r["photo"]["depth"])
        if r["photo"]["shoot_group"]:
            s["shoots"].add(r["photo"]["shoot_group"])
    for s in per.values():
        s["shoot_groups"] = len(s.pop("shoots"))
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="manifest", help="output directory")
    ap.add_argument("--resume", action="store_true", help="use the stored delta token")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    state = {}
    ok, detail = step2_token(state)
    if not ok:
        raise SystemExit(f"auth failed: {detail}")

    changed, stats = enumerate_library(state["token"], out, args.resume)
    manifest_path = out / "manifest.jsonl"
    records, prior_count = merge_with_existing(changed, stats["deleted"], manifest_path)
    # Shoot runs are positional within a folder, so they are recomputed over the merged
    # set -- a file added mid-burst has to renumber the run it landed in.
    assign_shoot_groups(records)
    per = summarise(records)

    with manifest_path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    (out / "_summary.json").write_text(json.dumps(
        {"per_category": per, "pages": stats["pages"], "folders": stats["folders"],
         "deleted": len(stats["deleted"]), "changed_this_run": len(changed),
         "total_files": len(records)}, indent=1))

    if args.resume:
        print(f"\ndelta: {len(changed)} changed, {len(stats['deleted'])} deleted "
              f"-> manifest {prior_count} -> {len(records)} files")
    print(f"\n{len(records)} files over {stats['pages']} pages "
          f"({stats['folders']} folders, {len(stats['deleted'])} deleted)\n")
    print(f"{'folder':38s} {'files':>7s} {'images':>7s} {'video':>6s} {'doc':>5s} "
          f"{'other':>6s} {'GB':>7s} {'depth':>5s} {'shoots':>6s}")
    for cat in sorted(per, key=lambda c: -per[c]["bytes"]):
        s = per[cat]
        print(f"{cat[:37]:38s} {s['files']:7d} {s['image']:7d} {s['video']:6d} "
              f"{s['document']:5d} {s['other']:6d} {s['bytes']/1e9:7.1f} "
              f"{s['max_depth']:5d} {s['shoot_groups']:6d}")

    total = sum(s["bytes"] for s in per.values())
    images = sum(s["image"] for s in per.values())
    print(f"\ntotal {total/1e9:.1f} GB, {images} images "
          f"({sum(s['video'] for s in per.values())} videos excluded from tagging)")

    # A folder with real bytes but no images is the signature of a walk that failed to
    # recurse. Delta should make this impossible; report it if it ever appears.
    suspect = [c for c, s in per.items() if s["image"] == 0 and s["bytes"] > 1e9]
    if suspect:
        print(f"\nWARNING zero images but >1GB: {suspect}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Blocked as b:
        raise SystemExit(f"BLOCKED[{b.kind}] {b.detail}")
