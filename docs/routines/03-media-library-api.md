# Media library ingest — integration notes

**Status: API in build. No client written yet, deliberately.** These are notes to feed
into the build while it is still cheap to change.

```
POST https://qm3staging.midlandind.com.au/api/media/ingest
Header: x-media-key: <MEDIA_INGEST_KEY>
Body (JSON, one asset per call):
  { filename, dataBase64, contentType?, tags?: string[], createMissingTags?=true,
    tagGroup?, trailer?, job?, caption?, entityType?, entityId?, albumName? }
Returns: { mediaId, isNew, deduped, sha256, kind, appliedTags, skippedTags, albumId }
```

What is already right: `sha256` + `deduped` gives content-addressed dedupe, so a retried
or resumed run will not create duplicate assets. `appliedTags` / `skippedTags` makes each
call self-verifying. `job` and `trailer` as first-class fields are exactly the right
shape — photo folder names already carry job numbers, so `job` populates from the path
for free.

## Three things to fix while it is in build

### 1. This environment cannot reach the host at all

```
POST https://qm3staging.midlandind.com.au/api/media/ingest
  -> curl: (56) CONNECT tunnel failed, response 403
proxy status -> connect_rejected: "gateway answered 403 to CONNECT
                (policy denial or upstream failure)"
                host: qm3staging.midlandind.com.au:443
```

The environment's network policy denies outbound to that host. A routine running here
will fail the same way — and it will fail *after* the expensive tagging work, at the
write step. The host has to be added to the environment's allowed egress (and later the
production host too). See
https://code.claude.com/docs/en/claude-code-on-the-web for how the network policy is set.

Worth deciding now whether tagging and ingest are one routine or two: if ingest is
blocked, a single routine loses the tagging work with it. Writing tags to
`Sales/_image-tagging/` first and posting from a second step makes the expensive half
recoverable.

### 2. `dataBase64` is required, which makes re-tagging cost a re-upload

The endpoint ingests **bytes plus tags together**. Two consequences:

**No byte path from SharePoint.** The Microsoft 365 connector returns images rendered for
a model to look at, not raw bytes — `downloadUrl` came back `null` on every search
result. So there is currently no way for the routine to produce `dataBase64` for a file
that lives in SharePoint. Either the library needs a `sourceUrl` ingest mode (server-side
fetch, with whatever auth SharePoint needs), or the routine needs Graph credentials of
its own to download.

**Re-tagging means re-posting the bytes.** Tags will be revised — that is the whole point
of the Thursday iteration loop, and prompt versions will change after that. With ingest as
the only write path, every revision re-uploads ~250 GB of images to change a handful of
strings. What is missing is a tags-only update keyed on something stable:

```
PATCH /api/media/{mediaId}/tags        or keyed on sha256
  { tags: [...], replaceGroup?: "vision-v2", createMissingTags: false }
```

If that exists, the whole re-tag cycle costs nothing but the model calls.

### 3. `createMissingTags` defaults to true, which mints junk tags on a typo

With the default on, one malformed tag string becomes a permanent vocabulary entry, and
nothing surfaces the mistake. Better: pre-register the vocabulary, then run with
`createMissingTags: false` in production so a typo lands in `skippedTags` and is visible
in the response instead of silently polluting the tag list.

`tools/tag_vocabulary.py` generates the full vocabulary **from the schema**, so the two
cannot drift:

```
$ python3 tools/tag_vocabulary.py
791 tags to pre-register
```

Convention is `namespace:value`, lowercase, hyphenated — `axle:tri`,
`purpose:non-marketing`, `use:hero`, `defect:people-visible`. Per-trailer tags carry a
unit prefix: `t1:axle:tri`, `t2:axle:not-visible`.

**Rule that must survive into the tag store:** `unknown` and `not-visible` are always
emitted, never omitted. In a flat tag bag an absent tag is indistinguishable from an
unknown one, and that distinction is the only thing stopping a model inventing values.

## Open questions

1. **Can one asset carry more than one `tagGroup`?** This decides the per-trailer
   encoding. 6 × 119 per-trailer tags is what inflates the vocabulary to 791; if a
   second call (or a PATCH) can attach another tag group to an existing `mediaId`, then
   one group per trailer collapses that to ~119 + frame tags and reads far better.
   If not, the `t1:` / `t2:` prefix convention above stands.
2. **Is there any read side?** The routine needs to ask *what is already tagged, and at
   which prompt version*, to skip completed work on a resumed run. Without it every run
   starts from the first image — the original routine's most expensive defect.
3. **Provenance fields.** Right now `prompt_version` and `model` are smuggled in as
   `promptver:v2` / `model:haiku-4-5` tags. Real fields would be better, and are what let
   you find and re-tag only records written under an old prompt.
4. **Human overrides.** Someone will fix a tag by hand. Does the store distinguish
   human-set from model-set tags, so the next automated pass will not clobber it?
5. `trailer`, `entityType`, `entityId` — do these take ids, or strings the API resolves?
6. Max request size and rate limits — decides batch pacing over ~250 GB.
7. Does `skippedTags` mean "did not exist and `createMissingTags` was false", or is it
   also used for rejected/duplicate tags?

## Further questions from the folder test

These come out of tagging a real folder end to end, not from reading the spec. Roughly
most-likely-to-bite first.

### Does the tag store preserve `:` in tag names?

The entire vocabulary convention is `namespace:value` — `axle:tri`, `t2:axle:not-visible`.
If the tag store rejects colons, strips them, or normalises them to something else, all
791 tags collapse into ambiguity and it will not be obvious that it happened. If colons
are not safe, say so now and the separator changes to `-` or `.` before anything is
registered. Same question for the digit-prefixed `t1:` form.

### Re-POSTing an asset with revised tags: union or replace?

This is the one with a correctness consequence. Tags **will** be revised — the whole
Thursday iteration loop exists to revise them, and prompt versions will change after
that. If a second write unions its tags with what is already stored, then a corrected
value coexists with the wrong one:

> During the folder test I tagged one frame `axle:tandem` at high confidence. It was a
> miscount of a tri-axle group cropped at the frame edge. The corrected value is
> `axle:not-visible`. Under union semantics that asset now carries **both**
> `axle:tandem` and `axle:not-visible`, and any query for tandem trailers returns it
> forever.

What is needed is replace-within-scope: a write that carries `tagGroup: "vision-v2"`
should *replace* every tag previously written under that group for that asset, leaving
human-set and other-source tags alone. If `tagGroup` already means this, that resolves
both this and the per-trailer question above.

### On `deduped: true`, is new metadata merged or discarded?

Dedupe is by `sha256`, and exact duplicate files across folders are very likely in a
tree this size. But the *path context differs per copy* — the same photo filed under
`Tag Trailers` and under `Customised Trailers` yields different `category:` tags, and
possibly a different `job`. If a deduped write silently discards the incoming tags,
albums and `job`, the second folder's context is lost and the loss is invisible. Merging
is almost certainly the right behaviour; either way the routine needs to know, because it
changes whether a duplicate is worth posting at all.

### Filenames are not unique and carry no meaning

`IMG_0356`, `DSC02846`, `20241010_083353.jpg` — camera defaults, repeating across dozens
of folders. `filename` cannot be an identity or a display label. The full source path
needs to be a first-class stored field (an `externalId` or `sourcePath`), not folded into
`caption`, so that provenance is recoverable and a re-run can find the asset it already
created. This also gives the read-side lookup a natural key.

### Body size: base64 inflates by a third, and some files are large

Individual JPEGs here run 3–4 MB, so ~5 MB per request once base64-encoded. That is fine.
Video is not: one mp4 in the test folder is 102 MB, which becomes roughly a 136 MB JSON
body. If video is ever ingested through this endpoint, `dataBase64` is the wrong
transport — multipart, or a presigned-upload handshake, would be better. Worth knowing
the maximum accepted body size either way.

### Tag search needs prefix matching, or per-trailer tags are unqueryable

With per-trailer tags carried as `t1:axle:tandem` … `t6:axle:tandem`, the question
"show me every photo containing a tandem trailer" requires matching **any** unit
position. If tag search is exact-match only, that question needs six OR'd terms and
silently misses a seventh unit. Prefix or wildcard matching on tag names (`*:axle:tandem`)
makes it one query. This is the strongest argument for `tagGroup` supporting one group per
trailer instead.

### Expect a large, legitimately untagged video population

About 30% of the test folder was video (13 of 43 files), and `Drone Items` is 31 GB and
named for a video medium. The tagging pipeline deliberately excludes video — a vision
model cannot tag an mp4. So the library will hold a substantial number of assets with no
vision tags, and that is correct, not a failed run. Whatever reports on tagging coverage
should count against images, not all assets.

### Two smaller ones

- **Does ingest normalise EXIF orientation?** At least one file in the test folder is
  stored rotated 90 degrees. Tags are written as if the image is upright, on the
  understanding that the viewer corrects it — so the stored asset should be normalised
  (or the viewer's correction must be reliable), otherwise tags and pixels disagree.
- **Does `albumName` auto-create albums?** If so it carries the same junk-creation risk
  as `createMissingTags`, and a typo mints a permanent empty album.

## What is built and waiting

- `tools/tag_vocabulary.py` — vocabulary generator and the record → `tags[]` flattener.
  Both derive from `docs/schema/trailer-photo-tags.schema.json`.
- No HTTP client yet. It is a thin wrapper once the questions above are settled, and
  writing it before then would bake in guesses.
