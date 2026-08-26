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

**CORRECTED: an allowlist change reaches a running session.** This file previously said
network policy is bound at container start and needs a fresh session to verify. It does
not — `*.sharepoint.com` was added mid-session on 2026-08-26 and went live with no
restart. Re-probe the host rather than restarting. **Environment variables are the
opposite**: they are inherited at process start and genuinely cannot arrive mid-session,
so a newly added variable needs a fresh session. See `routines/04-graph-access.md`.

Allowlist state as measured 2026-08-26 (`python3 tools/graph_check.py` re-measures):

```
login.microsoftonline.com   allowed (302)
*.sharepoint.com            allowed (HTTP 403 = tunnel open, server wants auth)
graph.microsoft.com         STILL BLOCKED -- reported added, but refusing CONNECT
                            throughout a 10-minute poll. Verify the entry saved.
```

A reference point for how long an edit should take: `*.sharepoint.com` went live within
about two minutes. Ten minutes with no change means the entry did not take, not that it
is still propagating.

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

As of 2026-08-26 all four are **absent from the container** — checked against PID 1's
environment, so they were never passed in, rather than merely unset in a shell. Because
variables bind at process start, they need a **fresh session** after being added to the
environment config. `tools/graph_check.py` reports which are missing by name, never by
value.

## Do these next, in this order

Steps 1-6 are read-only and create nothing, and are automated:

```
python3 tools/graph_check.py          # runs 1-6, stops at the first failure
```

It never prints a credential or a token, and it does **not** do step 7. Full detail in
`routines/04-graph-access.md`.

1. Confirm egress: `https://qm3staging.midlandind.com.au/` → expect `401`, not `000`. **PASSING.**
2. Graph token from `login.microsoftonline.com` — proves credentials + first egress host.
   **Blocked: the three `GRAPH_*` variables are not in the container.**
3. `GET /sites/{...}/drives` — proves `Sites.Selected` was actually granted on the site.
4. `GET /drives/{driveId}/items/{itemId}` on one known file — proves item access.
5. `GET .../content` — **most likely step to fail**, because it 302s to a storage host.
   Read the real redirect host from the `Location` header before adding allowlist entries.
6. `GET .../thumbnails` at a large custom size — settles whether the vision pass can read
   an auto-oriented rendition instead of a full-resolution original. Check VIN plates and
   chassis-marked job numbers are still legible. The script asserts a **≥1600px** long
   edge, per the open question below.
7. Only then one end-to-end ingest of a single asset into staging. **Not automated, and
   not to be run without saying so first** — it is the first step that writes anything.

After 1-4 pass: rewrite `routines/01-enumeration.md` around Graph `/delta`, which is
strictly better than the folder-walk checkpoint scheme and removes the
"folder looks empty because it only holds subfolders" hazard entirely.

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

- `md` rendition long edge — is it ≥1600px? Decides whether the vision pass reads a
  rendition or a full original (Graph thumbnails may make this moot; step 6).
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
