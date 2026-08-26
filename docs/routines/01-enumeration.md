# Routine 1 — Enumerate the sales photo library

**Runs first. No model calls, no vision, no cost beyond Graph reads.**
Its only job is to produce the manifest that becomes the work queue for tagging.

Implemented by `tools/enumerate_delta.py`. This file explains what it does and why; the
script is the contract.

```
python3 tools/enumerate_delta.py --out manifest/            # full enumeration
python3 tools/enumerate_delta.py --out manifest/ --resume   # only what changed since
```

## This replaces a recursive folder walk

The previous version of this routine was a prompt telling a model to walk the tree with
the MCP connector, recursing to the leaf and checkpointing after each top-level folder.
Most of that text existed to stop one specific failure: **several of the largest folders
hold no loose files at all, only subfolders**, so a walk that lists only immediate
children reports 69 GB of Drop Deck Trailers as empty — silently, and in a way that reads
like a finding rather than a bug.

Graph's `/delta` removes the failure mode rather than warning about it. It returns a
**flat list of every descendant** with each item's parent path attached. There is no
recursion to get wrong, so a folder that contains only subfolders is not a special case
and cannot be mistaken for an empty one.

Three further things fall out of using Graph instead of the connector:

- **Resume is a token, not a checkpoint scheme.** The last page carries a `deltaLink`;
  passing it back returns *only what changed*. The second run over a 200 GB+ library sees
  the handful of new files rather than re-reading the tree. `--resume` does this.
- **Richer records at no extra cost.** `file.hashes.quickXorHash` (dedup before ingest),
  `mimeType`, and `image.width`/`height` all come back in the same response.
- **No model in the loop at all.** The old routine needed a model because it was driving
  a connector conversationally. This pass is now a script, so there is nothing to
  misinterpret an instruction and nothing to pay per token.

## Scope the delta to the folder, not the drive

```
GET /drives/{driveId}/items/{libraryRootItemId}/delta
```

**Not** `/drives/{driveId}/root/delta`. The drive is the whole `Shared Documents` library
for `SalesMarketingTeam`; the project scope is `Sales/1. Trailer Photos` only. Delta works
on any folder, so scope it there and the enumeration cannot wander outside the agreed
boundary. The script also re-checks each item's `parentReference.path` against the library
prefix before recording it — belt and braces, since a scope leak here would be silent.

## What is recorded per file

Straight from Graph: `drive_id`, `item_id`, full path, filename, lowercased extension,
`size_bytes`, `last_modified`, `depth`, `quick_xor_hash`, `mime_type`, and `width`/
`height` where Graph has them.

`media_class` is set **from the extension alone** — `image`, `video`, `document`, `other`.
Videos are mixed in throughout (`Drone Items` is ~31 GB and mostly video; mp4s sit inside
`Auto Twist Lock Skels` and `Tag Trailers`), and filtering them here is what stops a
vision call dying on a 102 MB mp4 mid-batch.

> **`image.width`/`height` are DISPLAY dimensions, with EXIF rotation applied.** A file
> stored 4000x3000 with orientation 6 is reported by Graph as `3000x4000`. Use Graph's
> numbers when sizing a thumbnail crop box; using the stored pixel dimensions instead
> requests a landscape box for a portrait frame and `_Crop` discards half the trailer.
> See `04-graph-access.md`.

## What is parsed from the path, and never asked of a model

The tree encodes the taxonomy before any subfolder detail, so all of this is free:

- **`product_category`** — the level-1 folder name.
- **`variant`** — the level-2 folder name with any leading `N.` stripped. The numbering
  punctuation is inconsistent (`1. Semi Drop Deck Trailers` with a space,
  `2.Drop Deck Extendable` without), so the script strips `^\d+\.\s*` rather than matching
  literal strings.
- **`axle_config_from_path`** — only where a path segment states it, otherwise `unstated`.
  Never inferred from the product category. **A trailer with two axles is a Tandem.
  "bogie" is not Midland's word, appears in no enum, and must not appear in any output.**
- **`customer`, `build_date`, `job_numbers`** — from deeper folder names, e.g.
  `2025.08 - Team Transport (BH) Quad Skels - 3467, 3468`. **All** job numbers are
  recorded: more than one means the folder holds more than one trailer, which is what
  later makes "which trailer is in this frame" a real question.
- **`content_expectation`** — `competitor` for `z. Opposition Trailers`, `render` for
  `z.Creo Trailer Image Files`, `drawing` for `Trailer Drawings`, `brochure_or_document`
  for `Brochures` and `z.Tare Weights`, `component_detail` for
  `z.Close Up Photos of Trailer Parts` and `z.BiFold Ramps Photos`, `aerial` for
  `Drone Items`, `second_hand_or_misc` for `z Second Hand and Miscelaneous`, otherwise
  `midland_trailer`.

> `content_expectation` is a **prior, not a label.** The folder test found an
> `Auto Twist Lock Skels` subfolder that was entirely condition/warranty documentation of
> in-service trailers — rust, chipped coaming, a worker's hand in shot — under a path that
> says `midland_trailer`. The vision pass sets `content_purpose` per frame and never
> inherits this value.

## Shoot grouping

Within one folder, a run of consecutive camera-default filenames is normally one shoot of
one trailer. Each run gets a stable `shoot_group` id and a `shoot_group_position`.
Measured: **2,437 groups over 39,527 grouped files**, median 4 frames.

**"Consecutive" is enforced, not assumed.** A run breaks on a descriptive filename, a
change of filename prefix, a counter jump beyond ~10 frames, or a change of capture date.
Grouping every camera-default file in a folder instead — which is the obvious
implementation and the one written first here — put all 1,017 frames of
`Drone Items/143GOPRO`, spanning **seven separate dates**, into a single "shoot".

A **descriptive** filename breaks the run and gets no group — somebody naming one specific
thing is not part of a burst. `filename_is_descriptive` is worth carrying in its own right:
names like `Hills_Shire_council_Tandem_Axle_tag_trailer_1.jpg` state the answer, so they
are a free validation set. Tag them blind and check the output against the name. Measured,
that set is **~1,900 files, 4.6% of the library**.

> **The camera-default pattern list is load-bearing, and under-matching fails silently.**
> A first version covering only `IMG_`/`DSC`/`DSCN`/`P10…`/`YYYYMMDD_HHMMSS` classified
> **58%** of the library as descriptively named — including all 18,860 GoPro `G0012102`
> frames, which collapsed `Drone Items` from thousands of shoots into 2 and would have
> filled the validation set with camera counters. Neither failure announces itself. The
> list in `tools/enumerate_delta.py` was derived by clustering the library's real
> filenames and covers GoPro, DJI, WhatsApp, Android, iOS, Canon `MVI_`, bare counters and
> epoch-ms stamps, plus `(2)` / `- Copy` / `_resized` suffixes. **Re-cluster before
> trusting it on a folder it has not seen.**

**A shoot group is not permission to propagate tags across its members.** The folder test
established this the hard way: 13 of 30 frames in one folder could not be axle-counted at
all, and propagating a shoot-level value would have converted every one of them into a
confident number — right by luck there, wrong the moment a shoot contains two
configurations.

## Output

- `manifest.jsonl` — one record per file, each with `photo` and `path_derived` objects
  matching `schema/trailer-photo-tags.schema.json`.
- `_summary.json` and a printed table — per level-1 folder: file/image/video/document/other
  counts, total bytes, maximum depth, and distinct shoot groups.
- `_delta_token.json` — the resume token. Keep it; it is what makes the next run cheap.

Measured: a full run is **213 pages, ~4 minutes**. `--resume` immediately afterwards is
**1 page, 5 seconds**, reporting `0 changed, 0 deleted` and leaving all 41,421 records in
place. That ratio is the whole argument for delta over a folder walk.

> A resume run returns **only what changed**, so it must be folded into the existing
> manifest rather than written over it. Writing the delta result straight out would
> replace a 41,421-record work queue with however many files changed that day — zero, in
> the run above. `merge_with_existing()` upserts by `item_id` and applies deletions.

Writing to SharePoint is **not** part of this pass. The old routine uploaded checkpoints to
`Sales/_image-tagging/` because an unattended container was reclaimed after the run and
anything unwritten was lost. A local manifest plus a delta token is simpler and resumable,
so run this where the output persists, or copy the two files somewhere that does.

## The sanity check that used to matter

The old routine ended by asking for any folder where **image count is zero but total bytes
is large**, because that combination meant the walk had failed to recurse. The script still
reports it, and it should now never fire — delta has no recursion to fail. If it ever does,
the cause is a scope filter or an extension-classification bug, not a missed folder.

## Measured

See `findings/library-structure.md` for the enumeration's actual results — file counts per
folder, image-vs-video split, and how they compare against the folder byte totals recorded
when the library was first inspected.
