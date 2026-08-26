# Full-folder tagging test — `Auto Twist Lock Skels`

Every image in one real folder, tagged end to end against
`schema/trailer-photo-tags.schema.json`. Records: `auto-twist-lock-skels.json`.

## What was in the folder

| | |
|---|---|
| Files total | 43 |
| **Images tagged** | **30** |
| Videos excluded by extension | 13 (30% of the folder) |
| Subfolders | 1 — `Matt Tasman Videos and Pictures` |
| Images living in that subfolder | 11 (37% of all images) |
| Distinct shoots | 3 — Oct 2024, Oct 2025, Mar 2026 |

Two design decisions paid off immediately. **Extension filtering** kept 13 videos out of
vision calls, one of them a 102 MB mp4 that would have killed a run mid-batch.
**Recursion** found 37% of the folder's images; a top-level-only walk would have tagged
19 and reported the folder done.

## Output distribution

| Usability | n | | Axle count | n |
|---|---|---|---|---|
| hero | 5 | | tri | 10 |
| good | 12 | | not_visible (corrected) | 13 |
| usable | 3 | 
| record_only | 5 | | unknown | 7 |
| reject | 5 | | | |

18 of 30 frames carried at least one defect; 5 were flagged `needs_human_review`.
Nothing was tagged with an invented specification, and no field fell back to a guess —
which is what the `unknown` / `not_visible` split is for.

## Six things the test found that the schema review did not

**1. `axle_count` is undefined for a combination.** 7 of 30 frames (23%) show a
multi-unit A-double or road train where "how many axles does the trailer have" has no
single answer. All 7 were forced to `unknown`, which loses real information — the frames
plainly show tri and tandem groups. Needs a `subject_scope` (single unit vs combination)
so axle count can attach to the primary unit rather than being abandoned.

**2. No value for a cropped view of a whole trailer.** `20241010_084259.jpg` is a side
crop of a loaded skel: not a component, not a complete trailer, not a partial build.
Tagged `component_detail` under protest. Add `partial_view_cropped`.

**3. CORRECTED — and the correction is itself the finding.** This section first claimed
a Tandem unit sat in the same combination as tri-axle units, citing
`20251029_152010.jpg`. That was wrong. Re-read at full resolution, that frame's axle
group is **cropped at the frame edge**, and the same rig reads tri-axle throughout in
`153352` and `153354`. It was a miscount of a partial tri group, tagged `tandem` with
*high* confidence — the exact failure mode this schema is supposed to prevent, produced
by the schema's own author.

The no-propagation rule survives on better grounds. The real hazard is not that units
differ within a combination (in this folder they do not — every unit is tri). It is that
**a cropped frame cannot be counted at all**, and propagating a shoot-level value would
paper over precisely those frames with a confident number. 13 of 30 frames here are
`not_visible` on axle count. Propagation would have converted all 13 into confident
`tri` — right by luck in this folder, and wrong the moment a shoot contains two
configurations.

It also says something about confidence calibration: `high` was recorded on a frame
whose subject was partly out of shot. Cropping should cap confidence, and that belongs
in the prompt.

**4. Folder-level content expectation is unreliable, and dangerously so.** The
subfolder is not marketing photography at all — it is **condition/warranty
documentation** of in-service trailers: rust streaking on a mainbeam, chipped coaming,
scuffed and dirty surfaces, a worker's hand in frame. `path_derived.content_expectation`
called the whole folder `midland_trailer`, which is true and useless. All 5 `reject`
frames and 4 of 5 `record_only` frames come from this one subfolder. A tagger that
trusted the folder would have offered Midland's marketing team photographs of their own
product rusting. Needs a `content_purpose` field the vision pass sets per frame.

**5. Competitor branding appears inside Midland's own product photos.**
`3.26.14 PM.jpeg` has a **Krueger**-branded trailer in the background behind the Midland
unit. `is_midland_product` is correctly `midland` — the subject is Midland's — so the
provenance check does not fire; it was caught only by the `competitor_branding_visible`
defect. That defect flag is therefore load-bearing, not cosmetic, and needs to be
checked before anything is published.

**6. One file is stored rotated 90 degrees.** `20251029_150916.jpg` comes back sideways
— EXIF orientation is not applied by the read path. Tagged `reject`, low confidence.
Add an `image_rotated` defect value, and expect this class across the library.

## Two smaller observations

- **CORRECTED — plates are not an identity key.** This originally read *"plates are a
  better identity key than shoot groups"*, on the basis that `YO 56BA` appeared in both
  the Oct 2024 and Oct 2025 shoots and therefore showed the same trailer a year apart.
  That is wrong: **`YO 56BA` is most likely a trade plate** — Midland's own transferable
  plate, moved between units. So a shared plate across two frames does not mean one
  trailer, and quite often means two different ones. The inference was exactly backwards.
  Identity comes from the VIN plate or a chassis-marked job/build number, both of which
  are permanent and unit-specific. Container numbers are no better — they belong to the
  container, so they can separate one unit from another *within* a frame but cannot link
  frames.

  There is a useful signal left over, though, worth confirming: a trade plate means the
  unit is unregistered and being moved or photographed — which usually means a new build
  pre-delivery. That correlates with exactly the frames marketing wants. So the plate is
  worth reading for what it says about the trailer's *state*, never its identity.

- **Near-duplicates are common.** `153333`, `153337` and `153339` are three frames of
  one framing, all hero-grade. Marketing wants one. Worth a `duplicate_group` so the
  best of a run surfaces and the rest stay findable.

## Schema changes agreed and applied (v2)

| Change | Decision |
|---|---|
| `vision.trailers[]` — one tagged entry per trailer in frame, each with its own `axle_count`, `body_type`, loading and `confidence` | Applied. Replaces the single averaged subject. A four-unit road train now produces four tag groups |
| `subject_type`: `partial_view_cropped` | Applied |
| `content_purpose` incl. `non_marketing`, plus `non_marketing_reason` | Applied. The library will hold more than marketing, so this is set per frame, never inherited from the folder |
| `competitor_branding_present` promoted to its own field, with `competitor_names` | Applied. Was only a defect flag; the subject can be Midland's while a competitor sits in the background |
| `image_rotated` defect | **Not** added — orientation is handled in the viewer, so frames are tagged as if upright. `150916` re-tagged on its content |
| `duplicate_group` | Applied |
| Confidence must be capped where the subject is cropped | Prompt rule, not a schema change |

Worked example of the per-trailer structure on a real two-unit frame:
`v2-worked-example.json`.

## Caveat on this test

This was not a blind run: the folder path was known while tagging, so
`audit.category_agreement` reading `agree` across every trailer frame is weak evidence.
The Thursday protocol tags blind for exactly this reason. What the test does establish is
the extension filter, the recursion requirement, the enum coverage, and the five gaps
above — none of which depend on blindness.
