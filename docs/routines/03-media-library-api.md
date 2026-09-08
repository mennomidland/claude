# Media library ingest — integration state

```
POST https://qm3staging.midlandind.com.au/api/media/ingest
Header: x-media-key: <MEDIA_INGEST_KEY>     (env var; never committed)
Body (JSON, one asset per call):
  { filename, dataBase64, contentType?, tags?: string[], createMissingTags?=true,
    tagGroup?, trailer?, job?, caption?, entityType?, entityId?, albumName? }
Returns: { mediaId, isNew, deduped, sha256, kind, appliedTags, skippedTags, albumId }
```

Status: **live and tested end to end, 2026-08-27.** Three assets ingested into staging
from real library files via Graph. See "End-to-end test" below for what is confirmed
working, what turned out not to be implemented yet, and the one semantic that could not be
verified from outside.

## End-to-end test — 2026-08-27

Graph bytes → schema-v2 tag record → `POST /api/media/ingest`. Three assets created in
staging (`mediaId` 4, 5, 6), plus re-POSTs of the first to exercise dedup and correction.

### Confirmed working

| | Evidence |
|---|---|
| Full pipeline | `HTTP 200`, 49 tags applied, 0 skipped |
| **Occurrence split** | `occurrenceId` returned — 1, 2, 3 across three files |
| SHA dedup | Re-POST of identical bytes → `isNew=false, deduped=true`, occurrence preserved |
| `driveId` / `itemId` / `sourcePath` | Accepted as first-class fields, as promised |
| `createMissingAlbum` guard | Unknown album name → `skippedTags:["album:…"]`, `albumId:null`. **A typo 404s rather than spawning a junk album** |
| Per-trailer flat tags | `t1:axle:not-visible`, `t2:midland:midland` etc. all applied |

### Not implemented yet — and it fails *silently*

Probing the validator with deliberately wrong types returns errors for exactly these
fields: `filename`, `dataBase64`, `contentType`, `tags`, `createMissingTags`, `tagGroup`,
`trailer`, `job`, `caption`, `entityType`, `albumName`, `createMissingAlbum`, `sourcePath`,
`driveId`, `itemId`.

**`attributes`, `model`, `promptVersion` and `taggedAt` are not among them**, and neither
is a deliberately bogus field. The schema is **non-strict**: unknown keys are accepted
without error and dropped. So the structured `attributes.trailers[]` model can be sent, and
the call returns `200`, and nothing is stored. Nothing tells you.

Two consequences:

- **`tools/tag_vocabulary.py` is the PRIMARY path, not the fallback this file called it.**
  Until `attributes` lands, the flat `tags[]` bag is the only route that stores anything,
  which is exactly why the `unknown` / `not_visible` distinction must be emitted
  explicitly — an absent tag and an unknown one are indistinguishable in a flat bag.
- **Set-level provenance is not available.** `model` / `promptVersion` / `taggedAt` must
  travel as tags (`model:claude-opus-5`, `promptver:v2.0`), which `tags_for()` already does.

### Re-tagging costs a full re-upload — the highest-value API change to ask for

**`dataBase64` is mandatory and nothing substitutes for it.** Verified against the live
endpoint: omitting it gives `422 expected string, received undefined`; an empty string is
explicitly rejected with `dataBase64 is required`; and neither `sha256` nor `mediaId` is
accepted in its place — both still demand the bytes.

So **there is no tag-only update path.** Correcting a single tag on a photo already in the
library requires re-uploading the entire image, base64-encoded, once per namespace. The
server dedups it correctly and no second blob is created, but the bytes still cross the
wire.

What that costs at library scale, using rendition sizes measured in this project
(originals compress ~3.6x into full-resolution renditions):

| | |
|---|---|
| Library images | 136.1 GB |
| As full-resolution renditions | 37.8 GB |
| Base64 on the wire, one namespace | 50.4 GB |
| **A full re-tag, both namespaces** | **~101 GB** |
| The tags themselves | **~53 MB** (~1.4 KB/photo) |

**About 1,900x more data than the information being updated.** And a re-tag is not a rare
event: every prompt revision during the Thursday iteration, every schema change, and every
correction after review is one.

**The ask:** a tag-only route that takes `(driveId, itemId)` or `mediaId` plus `tags` and
`tagGroup`, with no `dataBase64`. Everything needed to identify the asset is already
first-class in the current payload; only the bytes requirement is in the way.

> The cost argument below was superseded on 2026-09-08 by a much harder one: Graph
> renditions are not byte-stable across days, so a re-tag cannot re-send matching bytes at
> any price. See "Graph renditions are NOT byte-stable". This route is a prerequisite, not
> an optimisation.

**Mitigation implemented meanwhile.** `tools/ingest_library.py` stores a hash of each
namespace's tag set in the occurrence ledger and compares it **before fetching bytes**:

- Tags unchanged in both namespaces → nothing fetched, nothing uploaded. A no-op re-run of
  three photos takes 1.3 seconds.
- Only the search namespace changed → one POST instead of two, halving the transfer.
- `--force` re-posts regardless, for when server-side state is in doubt.

The cost of that shortcut, stated plainly: a source file silently REPLACED with identical
tags is not noticed here. Catching that is the enumeration delta's job — it watches
`lastModified` — not this tool's.

### ANSWERED: tags UNION, they do not replace — 2026-08-31

**Confirmed from the media library UI, which is the read-back the API does not give us.**
`Midland Trailors CivicCast 13.jpg` displays BOTH prompt versions at once:

```
promptver:v2.0-e2e-rendition     (sent in the early size-cap ingest)
promptver:v3.0-features          (sent later, same asset, same namespace)
```

Two re-POSTs to the same `(asset, namespace)`, and the earlier tag set is still there. So
the documented **PUT-replace per (asset, namespace) is not what the endpoint does** — it
unions.

**This is the bad answer, and it blocks correction at scale:**

- A corrected tag never displaces the wrong one. `axle:not_visible` sent after
  `axle:tandem` leaves both, and a search for tandem still returns the frame.
- Every prompt revision layers another `promptver:` on top, so provenance stops meaning
  "this is how this record was made" and becomes "these are all the passes that ever ran".
- Nothing the tagging pass writes can ever be retracted by writing again. The only removal
  route is the `x` on each tag in the UI, by hand, per asset.

That changes the Thursday protocol: iterate the prompt against the gold set WITHOUT
ingesting, and only write tags once the schema is frozen. Writing during iteration bakes in
every intermediate answer.

**The ask, now the highest priority of the two:** make a re-POST to an existing
`(asset, namespace)` replace that namespace's tag set, as originally specified. Paired with
the tag-only route above, that makes correction possible at all.

### The search for a removal route — three ways, all negative — 2026-09-08

"Treat every tag as permanent" was the working conclusion, and it was tested rather than
assumed. `tools/probe_tag_removal.py` reproduces all three probes.

**1. No removal field in the payload.** The earlier field-name probe only reported on names
it happened to SEND, and the schema is non-strict — an unknown key is accepted and silently
dropped — so a field never sent looks identical to a field that does not exist. 31 candidate
spellings were sent with deliberately wrong types (`replaceTags`, `removeTags`, `clearTags`,
`deleteTags`, `untag`, `tagsToRemove`, `setTags`, `overwriteTags`, `replaceExisting`,
`purgeTags`, `resetTags`, `syncTags`, `tagMode`, `tagStrategy`, `tagOperation`, `mode`,
`op`, `replace`, `merge`, `strategy`, `pruneTags`, and the rest). The validator named
**none** of them. It did name all four known-good controls in the same request —
`filename`, `dataBase64`, `tags`, `createMissingTags`, `tagGroup` — so the probe reached the
validator and the null result means something.

**2. No sibling route reachable with `x-media-key`.** `/api/media/ingest` answers `405` to
GET, PUT, PATCH and DELETE, so it is POST-only. Every other path under `/api/media/*` —
`/api/media/{id}`, `/api/media/{id}/tags`, `/api/media/tags`, `/api/media/retag`,
`/api/media/untag`, `/api/tags` — answers **`401`** to the media key, on every method. The
key authorises exactly one route. Whether those paths exist at all cannot be told from
outside, and does not matter: they are not reachable from the tagging pass.

**3. No removal syntax inside `tags[]`.** Sent with `createMissingTags: false`, so an
unrecognised string is reported rather than created:

```
appliedTags  ["defect:none"]                                        <- positive control
skippedTags  ["-defect:none", "!defect:none", "~defect:none",
              "remove:defect:none"]
```

`defect:none` already exists in the library and was applied, so "skipped" here means "this
string was looked up as a tag name and not found" — the prefixes are not parsed.

**Conclusion: removal is not achievable from the ingest API as it stands.** It has to be
built server-side.

### What the tagger does about it meanwhile

The user's requirement is that a re-tag can *remove* erroneous tags, not merely add correct
ones. The half of that which does not need the server is now built:

- **`ingest_library.py` stores the tag SETS it wrote**, per namespace, in the ledger — not
  just their hashes. A hash says something changed; only the set says *which tags are now
  wrong*. Without this, removal is not computable even after the server supports it.
- **Every run diffs prior against current** and records `prior - current` as pending
  removals in a work list beside the ledger (`*_removals.json`), accumulating across runs so
  a second correction cannot lose the first one's retraction.
- **`tools/removal_report.py` renders that list as a per-asset checklist**, so the manual UI
  cleanup is a finite job of known size instead of a hunt.
- **`REMOVAL_FIELD` in `ingest_library.py` is the switch.** Set it to whatever field name
  the endpoint grows and retractions go out with the same POST, and the backlog clears
  itself. Nothing else changes — the diff is already computed and already recorded.

The backlog this produced for the two corrections already made (`category:` → `folder:`,
and the DJI_0270 combination fix) is **72 tags across all 40 gold-set assets** —
`docs/test-run/goldset40-removals.md`. Every asset carries a `category:`/`variant:` tag
asserting a classification that the folder only ever hypothesised.

### Graph renditions are NOT byte-stable — this breaks re-ingest entirely — 2026-09-08

Re-fetching the gold set eight days after it was ingested: **8 of 8 renditions returned
different bytes** for the same item at the same crop spec.

It is not the source files and not the crop spec:

| | |
|---|---|
| Source files last modified | 2014, 2018, 2022, 2023, 2024, 2025-12 — all long before the run |
| `quickXorHash` on the source | unchanged |
| Crop spec | identical (`c{displayW}x{displayH}_Crop`, from the same `image` facet) |
| Same spec fetched 3x today, plus a fresh token | **identical every time** |

So the rendition is stable within a session and regenerated across days — Microsoft
re-encodes it, and JPEG re-encoding is not reproducible.

**The consequence is severe.** Library dedup is keyed on the SHA of the bytes. A re-tag that
re-uploads therefore creates a **new blob per photo** — 40,452 orphaned blobs on a full
re-tag pass, none of which can be deleted, because there is no delete route either.

This was found the hard way: a probe that bypassed the duplicate guard produced
**`mediaId` 50, an orphaned second blob of `IMG_3908 1.jpg`** (already in the library as
`mediaId` 40). One asset, needing deletion in the UI. The probe now routes through the same
guard as a real ingest and cannot do it again.

**The guard is what saves the bulk run**, and it holds: `check_and_record` refuses to POST
when the freshly-fetched bytes do not match the ledger, and now records the source file's
own `quickXorHash` and `lastModified` so it can name the cause:

```
BLOCK IMG_3908 1.jpg: occurrence already ingested with different bytes
    was 03602ef996877ceb… via graph_rendition (mediaId 40)
    now 16e74912396b06aa…
    The SOURCE FILE IS UNCHANGED (same quickXorHash and lastModified), so this is
    Graph re-generating the rendition, not a new photo.
```

**This promotes the tag-only route from an optimisation to a hard prerequisite.** The
earlier argument was cost — ~101 GB to move ~53 MB of tags. The real argument is that
**re-tagging by re-upload is not possible at all**: it is not merely expensive to re-send
the bytes, there are no matching bytes left to send. Correct tagging of this library depends
on a route that identifies the asset by `(driveId, itemId)` or `mediaId` and carries no
`dataBase64`.

### The two asks, as a specification

Both are one endpoint. Suggested shape, matching the fields already first-class:

```
POST /api/media/tags
  { driveId, itemId }  or  { mediaId }        -- identify, no bytes
  tagGroup: string                            -- the namespace to operate on
  tags: string[]                              -- the tag set this namespace should now hold
  mode: "replace" | "merge"                   -- default "replace"
  removeTags?: string[]                       -- explicit retraction, for mode "merge"
  createMissingTags?: boolean
Returns: { mediaId, appliedTags, removedTags, skippedTags }
```

`mode: "replace"` alone satisfies both asks: it retracts by omission, and it needs no bytes.
`removeTags` is the smaller, surgical version for callers that do not hold the whole set.
`removedTags` in the response is what lets the caller clear its own backlog with confidence
rather than assuming.

### The size cap bites on the payload, and reports itself as a JSON error

The documented cap is 40 MB. It applies to the **base64 payload**, not the raw file, and
base64 inflates by 4/3.

`Midland Trailors CivicCast 13.jpg` — 36.4 MB, the largest image in the library — becomes a
**48.6 MB** payload and is rejected with:

```
HTTP 400  {"success":false,"message":"Invalid JSON body"}
```

That message is misleading: the body is truncated by a size limit before it is parsed, so a
size failure presents as a malformed-payload bug. A routine would log it in the wrong place.

**Exactly 1 image of 40,452 exceeds the cap** — but see the fix below, which removes the
problem rather than special-casing it.

### Ingest the full-resolution rendition, not `/content`

Re-fetching that same file as a full-resolution Graph thumbnail (`c8256x5504_Crop`) gives
**3.6 MB at identical resolution — 10x smaller** — and it ingests cleanly:

```
payload 4.9 MB (was 48.6 MB)  ->  HTTP 200  mediaId=6 occurrenceId=3 isNew=true
```

This should be the default for the whole run, for four reasons:

1. **It removes the size-cap failure** without special-casing anything.
2. **It is auto-oriented**, so EXIF-rotated files store upright.
3. **Wire volume.** 136.1 GB of originals is ~181 GB once base64-encoded. Renditions cut
   that by roughly 4x on typical frames and 10x on the largest.
4. Same pixels, same legibility — verified in `04-graph-access.md`.

The one thing it gives up is byte-exact originals. If the library must hold the true
original file, that is a reason to build the multipart or presigned path rather than to
push 181 GB through base64.

### Pick one byte source and never change it mid-run

Re-ingesting `20251029_153352.jpg` from the **rendition**, having first ingested it from
**`/content`**, produced a **new `mediaId` (7) against the same `occurrenceId` (2)**.

That is both halves of the design working exactly as intended, and a trap:

- The occurrence is keyed on `(driveId, itemId)`, so it correctly stayed the same file.
- Dedup is keyed on the SHA of the bytes, and rendition bytes are not original bytes, so
  the library correctly stored a second blob.

Net effect: `mediaId` 5 is now an orphaned blob of the same photograph. Re-running the
library with a different byte source would orphan a blob **per image** — 40,452 of them.

Confirmed by the control case in the same run: re-ingesting the CivilCast frame from the
rendition, having also ingested it from the rendition, returned `mediaId 6` unchanged and
deduped. Same bytes dedup; different bytes do not.

**Decide `/content` vs. rendition before the bulk run, not during it.** The recommendation
above is rendition, for size, orientation and the 40 MB cap.

## Egress: confirmed, but only from the `Midland` environment

| Environment | id | Reaches the host |
|---|---|---|
| `Midland` | `env_0175ZY9ro2ikpeDDEHXq7R4t` | **yes** — `front_door=401`, tunnel opens, TLS completes, server answers |
| `Default` | `env_01TaRfDf28pGgr7uWXtDLfFn` | no — `CONNECT ... 403 policy denial` |

A 401 at the root is the expected shape: the host is up and wants authentication. It says
nothing about `/api/media/ingest`.

**Every routine that writes to the media library must be configured against
`env_0175ZY9ro2ikpeDDEHXq7R4t`.** A routine left on `Default` does all the expensive
tagging work and only then fails at the write step — the worst place to find a
misconfiguration. This is now the most important single line of pipeline config.

Two related facts:

- Network policy is bound when a container starts. A *running* session never picks up an
  egress change, so verification always needs a freshly started session.
- Confirm **"Also include default list of common package managers"** is ticked on
  `Midland`. Unticked, a `Custom` allowlist permits only the listed hosts, so npm, PyPI
  and `raw.githubusercontent.com` are refused too — and that fails mid-run, not at
  startup.

## Settled with the builder

| Question | Answer |
|---|---|
| Are `:` safe in tag names? | Yes — the store does `trim()` only, no lowercasing or punctuation stripping, via `applyExistingTag`/`createLibraryTag`. Moot under the structured model anyway |
| Re-POST: union or replace? | **PUT-replace per (asset, namespace)**, where namespace is `tagGroup`. A corrected `axle:not_visible` overwrites the wrong `axle:tandem` cleanly — no forever-match |
| Protecting human corrections | Human edits go in a separate namespace; overlay human-over-model on read. A model re-run of its own namespace never touches them |
| `deduped:true` losing path context | Was a real defect, being fixed: blob stays SHA-deduped in `tbl_QM3_Media`, new `tbl_QM3_MediaOccurrences` maps `(driveId,itemId)` → mediaId + sourcePath, **tag sets key on the occurrence, not the blob** |
| Per-trailer queryability | Structured `attributes.trailers[]` ordered array — "any photo with a tandem" is one predicate over the array, no `t1:…t6:` OR-chain and no missed 7th unit |
| Source path | First-class: `occurrences.SourcePath`, plus `(driveId,itemId)` as natural key. Never folded into `caption` |
| Video via base64 | Endpoint is photos-only, 40 MB cap. Video goes multipart or presigned — not built into the base64 path |
| Coverage denominator | No API change; noted for whoever builds the report — denominate by **images**, not all assets, or a legitimately untagged 31 GB video population makes coverage read broken |
| `albumName` typo risk | Adding `createMissingAlbum` (default false), so a typo 404s instead of spawning a junk album |
| Resume / skip query | Ships now. Attribute-value search over the JSON is a follow-up read endpoint via `OPENJSON` |

**Confirmed to the builder:** tags keyed on the `(driveId,itemId)` occurrence, human
corrections in a separate namespace. Yes to both, plus `sourcePath` and
`createMissingAlbum`.

## The structured model changes our side for the better

`attributes.trailers[]` as an ordered array is **exactly** the shape schema v2 already
has — `vision.trailers[]`, one entry per trailer visible in the frame, each with its own
`axle_count` and `confidence`. So the mapping is 1:1 and no translation layer is needed:

```
vision.trailers[1].axle_count = "not_visible"   ->   trailers[1].axle = "not_visible"
```

Two consequences worth noting:

- ~~**`tools/tag_vocabulary.py` drops from primary to fallback.**~~ **Not yet — see the
  end-to-end test above.** `attributes` is not in the API's validator, so the flat `tags[]`
  bag remains the only route that actually stores anything. This reverts to fallback only
  once `attributes` ships and a read-back confirms it persists.
- **The `unknown` / `not_visible` distinction is now safe.** That was the thing most at
  risk in a flat tag bag, where an absent tag and an unknown one are indistinguishable.
  In a typed field it survives, and it is the mechanism that stops a model inventing
  values.

## Two things still open

### EXIF: read the `md` rendition, but confirm its long edge first

The stored original keeps its EXIF orientation as-is; `thumb.webp` / `md.webp` are
auto-oriented via `sharp().rotate()`. Given the choice offered — read `md`, or add
auto-orient-on-orig — **read `md`.** Preserving original bytes untouched is correct, and
a vision pass wants a downscaled rendition anyway: the originals here are 3–4 MB each and
full resolution is wasted tokens on a classification task.

One caveat that decides it, though: **what is `md`'s long edge?** The folder test showed
that legible text carries real weight — container numbers separated individual units
within a four-unit combination, the auto twist lock control panel's instruction text was
the whole point of several frames, and **VIN plates and chassis-marked job numbers are
the only real identity signals** (registration plates are not: Midland uses trade plates,
which move between units). VIN and stamped compliance plates are small and fine-grained —
harder to read than a rego plate — so the resolution requirement is if anything tighter
than it first appeared. If `md` is around 1024px that detail starts to go, and with it the
`visible_text` field and the ability to say *which* trailer is in shot. If `md` is
1600px+ on the long edge it is fine. If it is smaller, either a larger rendition or
auto-orient-on-orig is the better answer.

### Namespace naming, and set-level provenance

Proposing `trailer-photo:vision` for model output and `trailer-photo:human` for
corrections. Since sets already carry a `source` marker, the natural home for provenance
is the set rather than smuggled tags: **`model`, `promptVersion`, `taggedAt` as set-level
fields.** That also makes the resume query far more useful — if it returns
`promptVersion` per occurrence, a re-tag after a prompt revision can select only the
records written under the old version instead of re-running everything.

### RESOLVED — bytes come from Graph

Settled: the routine uses Microsoft Graph directly rather than waiting on a server-side
`sourceUrl` fetch. `GET /drives/{driveId}/items/{itemId}/content` supplies the bytes for
`dataBase64`, so the library does not need a fetch mode.

Setup, permissions and the additional egress hosts this requires are in
`04-graph-access.md`. The short version: ask for `Sites.Selected` rather than
`Files.Read.All`, and remember that a Graph content request **302s to a storage host** —
so `graph.microsoft.com` alone in the allowlist is not enough and fails at the redirect,
after auth has already succeeded.
