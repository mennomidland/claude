# HANDOVER — Midland media library tagging

Read this first, then `docs/README.md`. Work continues on branch
`claude/continue-with-this-tef77k`.

## What this is

Tagging Midland's sales photo library so marketing and sales can find images, and
loading the tags into the QM3 media library via its ingest API. Filenames are mostly
camera defaults and carry no meaning.

**Scope: `sites/SalesMarketingTeam/Shared Documents/Sales/1. Trailer Photos` only.**
Drive id `b!kxUlnz9hTEGIP79tTDljrR9Yzea0cmdLraKjspDsTfIFN9XvZPm7RKua__mqYOLv`.
~250 GB, ~26 top-level product folders. Job-card/spec joining is **parked** —
see `findings/join-discovery.md`, do not restart it.

## House vocabulary — non-negotiable

A trailer with two axles is a **Tandem**. Never "bogie". Midland's own folders read
`2. Tandem Axle Tag Trailer`. A general model reaches for "bogie" constantly on
Australian trailer photos, so the prohibition is explicit in every prompt and the word
appears in no enum. Single / Tandem / Tri / Quad.

## Environment and network — the config line that fails late

Routines and sessions that write to the media library **must** run in the `Midland` cloud
environment, `env_0175ZY9ro2ikpeDDEHXq7R4t`. `Default`
(`env_01TaRfDf28pGgr7uWXtDLfFn`) cannot reach the host — `CONNECT ... 403`. A routine on
`Default` completes all the expensive tagging and only then fails at the write step.

Egress confirmed from `Midland`: `https://qm3staging.midlandind.com.au/` → **401**
(tunnel opens, TLS completes, server answers wanting auth).

**CORRECTED: config changes reach a running session — do not restart to pick them up.**
This file previously said network policy is bound at container start and needs a fresh
session. It does not: `*.sharepoint.com` was added mid-session on 2026-08-26 and went
live within ~2 minutes, no restart. The same turned out to be true of **environment
variables** — all four credentials arrived mid-session in that same session. Re-probe;
do not restart. See `routines/04-graph-access.md`.

Allowlist state as measured 2026-08-26 (`python3 tools/graph_check.py` re-measures):

```
login.microsoftonline.com     allowed
graph.microsoft.com           allowed
*.sharepoint.com              allowed -- /content redirects here
*.svc.ms                      MISSING -- thumbnails come from
                              australiaeast1-mediap.svc.ms. Blocks step 6.
```

An edit lands in about two minutes. If a host has not opened by then the entry did not
take — check it is a **bare hostname**. `graph.microsoft.com` was entered as
`*.graph.microsoft.com` and refused CONNECT for ten minutes; a leading `*.` does not
match the bare host.

Package managers are fine — pypi/npm reach via the proxy's `noProxy` bypass and
`raw.githubusercontent.com` returns 301.

Note the two 403s mean opposite things: a **CONNECT 403** is the gateway refusing the
tunnel (not allowlisted); a plain **HTTP 403** means the tunnel opened and the server
answered. Do not read the second as a policy failure.

## Credentials — read from env, never commit

| Variable | Purpose |
|---|---|
| `MEDIA_INGEST_KEY` | `x-media-key` header for the ingest API |
| `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` | Graph client credentials |

Check with `[ -n "$VAR" ] && echo set` — **never echo a value.** Cloud environment
variables have no secrets store and are readable by anyone using the environment, so
these want short expiries or certificate credentials. `MEDIA_INGEST_KEY` was pasted into
a chat transcript at one point and should be rotated.

As of 2026-08-26 all four are **present and working** — step 2 acquires a Graph token, so
the client credentials are valid.

**Do not test for them with `/proc/1/environ`.** The runner injects variables into the
agent process, not container init, so they never appear there even when they are working
— a check that reported them absent while they were in fact usable. Test the shell's own
environment, as `tools/graph_check.py` does; it names missing variables, never values.

## Do these next, in this order

Steps 1-6 are read-only and create nothing, and are automated:

```
python3 tools/graph_check.py          # runs 1-6, stops at the first failure
```

It never prints a credential or a token, and it does **not** do step 7. Full detail in
`routines/04-graph-access.md`.

1. Confirm egress: `https://qm3staging.midlandind.com.au/` → expect `401`, not `000`. **PASSING.**
2. Graph token from `login.microsoftonline.com` — proves credentials + first egress host.
   **PASSING** — token acquired, so the client credentials are valid.
3. `GET /sites/{...}/drives` — **PASSING.** 2 drives, documented drive id present, so
   `Sites.Selected` is granted on `SalesMarketingTeam`.
4. `GET /drives/{driveId}/items/{itemId}` — **PASSING.** Resolves a real 4000x3000 image.
5. `GET .../content` — **PASSING.** 302s to `midlandind.sharepoint.com` and fetches
   3.15 MB. The predicted redirect trap is resolved: for this tenant the storage host is
   covered by the existing `*.sharepoint.com` entry.
6. `GET .../thumbnails` at a large custom size — **FAILING, one allowlist entry short.**
   The custom size is honoured (1600x1200, aspect-preserved, auto-oriented) but the URL
   is on `australiaeast1-mediap.svc.ms`, which is blocked. **Add `*.svc.ms`.**
7. End-to-end ingest — **DONE, 2026-08-27.** Three assets in staging (`mediaId` 4, 5, 6).
   Pipeline works: occurrence split, SHA dedup and the `createMissingAlbum` guard all
   confirmed. Three things came out of it that change the routine design:

   - **`attributes` is not in the API validator yet, and unknown fields are dropped
     silently** — a structured payload returns `200` and stores nothing. So
     `tools/tag_vocabulary.py` is still the **primary** path, not the fallback, and
     provenance travels as `model:` / `promptver:` tags.
   - **Ingest the full-resolution Graph rendition, not `/content`.** It is ~4x smaller
     (10x on the largest file), auto-oriented, and identical in resolution. Via `/content`
     the library is ~181 GB of base64 over the wire, and the single largest image
     (36.4 MB → 48.6 MB encoded) is rejected as `400 "Invalid JSON body"` — a size limit
     wearing a parser error's clothes.
   - **Replace-vs-union is still unverified** and it is the one that matters. See
     `routines/03-media-library-api.md`.

**Enumeration is done.** `routines/01-enumeration.md` is rewritten around Graph `/delta`
and implemented in `tools/enumerate_delta.py`; a full run over the library completed and
its results are in `findings/library-structure.md`. Headline numbers to plan against:

```
41,421 files   40,452 images   441 videos   216.7 GB
```

Three things it found that change the plan:

- **`Drone Items` is 19,138 images — 47% of every image in the library**, in one folder of
  GoPro bursts. It was documented as "mostly video"; it holds 43 videos. Nearly half the
  tagging volume is near-identical aerial frames, so that folder wants sampling and
  `duplicate_group`, not exhaustive tagging.
- **Video is 1% of files but 36% of bytes** (77.6 GB, largest single file 3.76 GB), so the
  extension filter is worth much more than its file count suggests. Denominate coverage by
  **images**, never all files.
- **Only 4.6% of filenames are descriptive**, so the free-validation-set idea is real but
  small — about 1,900 files.

## Settled — do not re-litigate

- **Per-trailer tagging.** One tag group per trailer visible in a frame, each with its own
  axle count and confidence. Never one averaged entry, never copied across units.
  Schema v2's `vision.trailers[]` maps 1:1 onto the API's `attributes.trailers[]`.
- **Ingest semantics**, confirmed with the API builder: PUT-replace per
  (asset, namespace); tags key on the `(driveId,itemId)` **occurrence**, not the
  SHA-deduped blob; human corrections live in a separate namespace and are overlaid on
  read; `sourcePath` is first-class; `createMissingAlbum` defaults false; endpoint is
  photos-only with a 40 MB cap, video goes multipart/presigned.
- **Replace-per-namespace means always write the complete set**, never a partial update,
  or the rest is silently wiped.
- **`Sites.Selected`**, not `Files.Read.All` / `Sites.Read.All`. Read only.
- **Rotation is not a tag defect** — handled downstream. Tag content as if upright.
- **`content_purpose` is per frame, never inherited from the folder.** The library holds
  more than marketing.
- **`unknown` and `not_visible` are always emitted, never omitted**, and `not_visible`
  (confidently out of frame) is distinct from `unknown` (in frame, cannot judge).

## Corrections already made — do not reintroduce

- **Plates are not identity.** Midland uses **trade plates**, which move between units, so
  the same plate in two frames often means two different trailers. Identity is the VIN
  plate or a chassis-marked job/build number. Container numbers separate units *within* a
  frame but cannot link frames. A trade plate does signal an unregistered unit — usually a
  new build pre-delivery — so read it for **state**, never identity.
- **There is no confirmed Tandem in the 2025 Tasman combination.** An earlier finding said
  so; it was a miscount of a tri-axle group cropped at the frame edge, tagged at high
  confidence. Cropping must cap confidence. The no-propagation rule stands on the grounds
  that 13 of 30 frames cannot be counted at all.

## Still open

- ~~`md` rendition long edge~~ — **settled, and the old guess was wrong.** Checked by eye:
  at 1600px *and* at 2048px the auto twist lock control panel text is an illegible smear;
  only a full-resolution rendition reads. So use **two tiers** — 1600px (~160 KB) for
  scene-level classification, full resolution (~724 KB) for `visible_text`, identity and
  component detail. Graph's full-res rendition is 4.3x smaller than the original with the
  same legibility, and is auto-oriented, so prefer it over `/content` outright. Details in
  `routines/04-graph-access.md`.
- Namespace naming — proposed `trailer-photo:vision` and `trailer-photo:human`.
- Set-level provenance fields `model` / `promptVersion` / `taggedAt`, and whether the
  resume query returns `promptVersion` so a re-tag can select only stale records.

## Reference

- `findings/library-structure.md` — the library map, folder sizes, hazards
- `schema/trailer-photo-tags.schema.json` — v2, the tag contract
- `routines/01-enumeration.md` — free first pass (pre-Graph; due for rewrite)
- `routines/02-thursday-iteration.md` — 40-image gold set, how the schema gets frozen
- `routines/03-media-library-api.md` — ingest API state and settled answers
- `routines/04-graph-access.md` — Graph permissions, egress, test order
- `test-run/` — a real full-folder tag run over `Auto Twist Lock Skels` (30 images,
  13 videos excluded) plus what it found. This is a usable gold set; do not re-run it
  from scratch.
- `tools/tag_vocabulary.py` — flat-tag fallback only; the structured path is primary
