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
| good | 12 | | tandem | 1 |
| usable | 3 | | not_visible | 12 |
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

**3. Shoot-level propagation of `axle_count` would be actively wrong.**
`20251029_152010.jpg` is a **Tandem** unit in the same combination, same shoot, same
minute as the tri-axle units either side of it — and `20251029_153354.jpg` shows a tri
group and a tandem group in one frame. The schema already forbids propagating per-frame
attributes, but axle count reads like a shoot-level attribute and is not one. Worth
stating explicitly in the enumeration doc.

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

- **Plates are a better identity key than shoot groups.** `YO 56BA` appears in both the
  Oct 2024 and Oct 2025 shoots — the same trailer, a year apart, in two different
  `shoot_group`s. Plates and container numbers in `visible_text` link frames that
  filename grouping cannot.
- **Near-duplicates are common.** `153333`, `153337` and `153339` are three frames of
  one framing, all hero-grade. Marketing wants one. Worth a `duplicate_group` so the
  best of a run surfaces and the rest stay findable.

## Recommended schema changes before sign-off

| Change | Why |
|---|---|
| Add `subject_scope`: `single_unit` / `combination` / `unknown` | Recovers axle data on 23% of frames |
| Add `subject_type`: `partial_view_cropped` | Real, common, currently unrepresentable |
| Add `content_purpose`: `marketing_photography` / `condition_or_warranty_record` / `delivery_record` / `build_record` / `unknown` | The single highest-value field this test produced |
| Add `defects`: `image_rotated` | Observed, and will recur |
| Add `duplicate_group` | Three hero near-duplicates in 30 frames |

## Caveat on this test

This was not a blind run: the folder path was known while tagging, so
`audit.category_agreement` reading `agree` across every trailer frame is weak evidence.
The Thursday protocol tags blind for exactly this reason. What the test does establish is
the extension filter, the recursion requirement, the enum coverage, and the five gaps
above — none of which depend on blindness.
