# Media library ingest — integration state

```
POST https://qm3staging.midlandind.com.au/api/media/ingest
Header: x-media-key: <MEDIA_INGEST_KEY>     (env var; never committed)
Body (JSON, one asset per call):
  { filename, dataBase64, contentType?, tags?: string[], createMissingTags?=true,
    tagGroup?, trailer?, job?, caption?, entityType?, entityId?, albumName? }
Returns: { mediaId, isNew, deduped, sha256, kind, appliedTags, skippedTags, albumId }
```

Status: **API in build.** Migration 125 is being re-cut with the occurrence split below.
No client written yet — deliberately, until the last few shapes settle.

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

- **`tools/tag_vocabulary.py` drops from primary to fallback.** It exists to flatten the
  typed schema into a keyword bag; with structured attributes the schema *is* the
  contract. Keep it for the flat `tags[]` path and in case a controlled vocabulary needs
  pre-registering, but it is no longer the main route.
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
