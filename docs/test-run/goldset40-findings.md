# 40-photo test — schema v4 end to end

Date: 2026-08-31. 40 photographs, 38 distinct folders, tagged by looking at each frame and
ingested to staging as `mediaId` 8–47. Records: `goldset40-records.json`. Ledger:
`goldset40-ledger.json`. Distributions: `goldset40-summary.json`.

**Result: 40 ingested, 0 skipped, 0 failed. 52 trailers tagged across 40 frames.
12 frames flagged `needs_human_review`.**

## The duplicate cannot recur — verified, not asserted

The staging library had two copies of `20251029_153352.jpg` because two scripts fetched
bytes two different ways: once from `/content` (3.0 MB) and once from the rendition
(784 KB). Same occurrence, two SHAs, so the library correctly stored two blobs.

Three checks on this run:

| Check | Result |
|---|---|
| `mediaId` range | 8–47, **40 distinct** — one asset per photo |
| Distinct SHAs | **40 of 40** — no accidental collisions |
| Byte sources in the ledger | **`graph_rendition` only** — one source, not a parameter |
| Re-running 3 already-ingested photos | returned **mediaId 8, 9, 10 unchanged**, marked `(re-tag, deduped)` |

That last row is the important one: re-tagging is a normal operation and must stay cheap,
while a *different-bytes* re-ingest is refused before the POST. Both behaviours are in
`tools/ingest_library.py` and neither is optional.

## What the spread of 40 exposed

### Schema gaps worth closing

1. **`axle_count` cannot express a dog trailer.** A super dog is one axle at the front and
   a tandem at the rear — recorded as `tri`, which reads as a tri *group* and is wrong.
   Three frames hit this. **`axle_count` should be per axle group, not per trailer**, or
   gain a companion `axles_per_group` list.
2. **No combination value for a ute-and-gooseneck.** Frame 26 is a Ford F-450 towing a
   gooseneck flat top; every `combination_type` value assumes a truck or prime mover.
   Recorded `unknown` rather than forced.
3. **No `mesh_grating` deck material.** Frame 25's mezz deck is open steel mesh —
   recorded `other`.
4. **`body_type` has no open-frame/bolster value.** The four blue units in frame 35 have
   cross-braced frames, no deck and no twist locks. Recorded `other`; likely Midland's
   steel spec, worth confirming.
5. **The tag/pig geometric boundary is still unresolved** (research §6.2). Frame 8 is a
   drawbar plant trailer behind a rigid truck whose group sits between centre and rear —
   `combination_type` left `unknown` because no sourced test separates the two.

### Misfiled photos — confirmed, and the audit block caught them

- **Frames 27 and 28 are photographs in `z.Creo Trailer Image Files`**, the 3D render
  folder. Daylight, cast shadows, cobwebs, a Landcruiser in the background. Both flagged
  `provenance_conflict: true`.
- **Frame 30 is a photograph in `Brochures`** — that folder mixes source imagery with
  document scans, so this is looser than a true misfiling.

This is the concrete case for treating `path_derived` as a hypothesis. Tagging blind is
what let vision disagree with the folder at all.

### One frame that must never be published

**Frame 37** was shot at a Brown & Hurley dealership. **Krueger, Schmitz Cargobull and
Hercules** signage is legible across the shed behind the subject. Tagged
`competitor_branding_present: in_background`, `defects: [competitor_branding_visible]`,
`marketing_usability: reject`, and the subject's manufacturer left `unknown` — there is no
Midland marking on it either. This is exactly the costly failure the schema exists to
prevent, and the flag is what catches it.

### The orientation finding needs qualifying

**Frame 31 came back rotated 90 degrees despite being fetched as a rendition.** Frame 32
is the same trailer, same session, same plate — and is upright.

So the earlier conclusion that "Graph renditions are auto-oriented" holds only where the
file carries an **EXIF orientation flag**. A file stored rotated with no flag cannot be
corrected by the rendition, the viewer, or anything downstream. That is a re-shoot or a
manual fix, and it is worth counting across the library.

### Where the positive-only discipline held

- **`suspension_type` is `not_visible` on 51 of 52 trailers.** The single `spring_leaf` is
  frame 22, an underside shot where the leaf packs are unmistakable. That ratio is the
  field behaving correctly, not failing — mudguards hide the suspension in almost every
  marketing angle.
- **`is_midland_product` is `unknown` on 31 of 52.** Only 21 carry a legible Midland decal.
  A folder-trusting tagger would have said "Midland" on all 52.
- **`deck_material` is `not_visible` on 43 of 52**, with 3 confident `checker_plate` reads.
- Frame 34's lead trailer is a B-double lead by geometry, but the tail section is not
  resolvable, so **`rear_fifth_wheel` was not claimed**.

### Things the run got right that v3 could not express

`super_dog` (frame 12, single front axle + tandem rear, textbook side elevation),
`converter_dolly` as a first-class unit (frames 15, 18, 39), `trade_plate` on 4 frames
— unregistered pre-delivery units, which is exactly the population marketing wants —
`engineering_drawing` (frame 29, whose CAD callouts independently confirm flip-over ramps,
rope rails, water tank and removable loadrack), and `duplicate_group` on the three
near-identical GoPro field-day frames plus the two Creo-folder chassis shots.

## Cost signal for the full run

Search-namespace tags averaged **38 per photo** (range 20–70), state-namespace **18**.
Rendition bytes averaged well under the 40 MB cap with the largest at 3.6 MB. At 40,452
images the tagging pass is the cost, not the transport.
