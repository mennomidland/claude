# Writing tags into the media library API

The media library that will host the photos is being amended to expose an API so a
routine can load tags straight in. This is the right destination — it removes the
manifest-files-in-SharePoint workaround, which only ever existed because the container
is reclaimed after a run.

Until the API exists, the enumeration and tagging routines write to
`Sales/_image-tagging/`. That write step should be the only thing that changes.

## What the routine needs from the API

Listed so it can be built in rather than bolted on. Roughly in order of how much pain
its absence causes:

1. **Idempotent upsert keyed on something stable.** A run will be retried, resumed after
   a checkpoint, and re-run after a prompt revision. The same image must not accumulate
   duplicate tag rows. A natural key of `(drive_id, item_id)` or the library's own asset
   id, with `PUT`-style replace semantics, is what makes re-running safe. Without this,
   every schema iteration pollutes the library.
2. **Batch writes.** Per-image round trips over ~250 GB of library is the difference
   between a run that finishes in a window and one that does not. 100–500 records per
   request is a reasonable target.
3. **A cursor or "already tagged" query.** The routine needs to ask *what has been tagged
   already, and at which prompt version*, so a resumed run skips completed work. This is
   the single biggest cost control in the whole project — without it, every run re-tags
   from the beginning.
4. **A version or provenance field per tag set.** Store `prompt_version`, `model` and
   `tagged_at` alongside the tags. When the schema changes, this is what lets you find
   and re-tag only the records written under the old prompt.
5. **Tolerant of unknowns.** Every enum in the schema admits `unknown`, and roughly a
   third of real frames legitimately use it. The API must accept and store `unknown`
   rather than rejecting the record or coercing it to a default — a coerced default is
   an invented value, which is the failure this whole schema is built to avoid.
6. **Repeated tag groups per asset.** One image can describe several trailers. The tag
   store needs to hold an *ordered list* of trailer tag groups per asset, not one flat
   row — a four-unit road train produces four sets of axle/body/loading tags against one
   image. If the API can only take flat key–value tags, the trailer index has to be
   folded into the key (`trailer.2.axle_count`), which works but is worth deciding
   deliberately rather than discovering late.
7. **A human-override flag that a re-run will not clobber.** Someone will correct a tag
   by hand. That correction must survive the next automated pass — so either a
   `source: human|model` marker the routine refuses to overwrite, or a separate override
   layer.

## What I need to know to write the integration

- Base URL, and how the routine authenticates (a token in the environment is fine; it
  must not be a browser-interactive flow, since routines run unattended)
- The asset identity: does the library keep the SharePoint `item_id`, or mint its own id
  the routine must look up by path or filename?
- Endpoint shapes for: list/query assets, read existing tags, upsert tags
- Whether tags are free-form strings or a controlled vocabulary that must be
  pre-registered — if controlled, the enums in `trailer-photo-tags.schema.json` need to
  be created in the library first, and that list should be generated from the schema
  rather than typed twice
- Rate limits and maximum request size

## One design note worth raising early

If the library's tag model is free-text keywords only, most of this schema's value is
lost — `axle_count: unknown` and no `axle_count` tag at all become indistinguishable,
and the distinction between "not visible in this frame" and "unknown" disappears. Those
two states are what stop a model inventing values. Worth asking whoever is amending the
library for **typed fields with an explicit null/unknown state**, not just a keyword bag.
