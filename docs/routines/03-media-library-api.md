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

### Could NOT be verified: replace vs. union

`x-media-key` authorises **only** `/api/media/ingest` — `GET` on it returns `405`, and every
other route tried (`/api/media/{id}`, `/api/media/{id}/tags`, `/api/media/search`,
`/api/media/occurrences`) returns `401`. There is no read-back.

So the claim that a re-POST is **PUT-replace per (asset, namespace)** could not be tested.
A re-POST with a deliberately smaller corrected set (5 tags, down from 49) returned
`200 … tags=5`, which is consistent with replace *and* with union — the response only
echoes what was sent.

**This is the single most important thing left to confirm**, because the whole correction
story rests on it: if tags union instead of replacing, a corrected `axle:not_visible` never
displaces the wrong `axle:tandem`, and every re-tag after a prompt revision leaves stale
wrong tags behind forever. Ask the builder to confirm, or to expose a read endpoint the
ingest key can reach.

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
