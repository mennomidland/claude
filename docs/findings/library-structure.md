# Sales photo library — structure as inspected

Scope confirmed with the user: **only** the sales photo library.

Root: `https://midlandind.sharepoint.com/sites/SalesMarketingTeam/Shared Documents/Sales/1. Trailer Photos/`
Drive id: `b!kxUlnz9hTEGIP79tTDljrR9Yzea0cmdLraKjspDsTfIFN9XvZPm7RKua__mqYOLv`
Read as: `file:///{driveId}/Sales/1. Trailer Photos` (the `Shared Documents` segment is
omitted in `read_resource` URIs — paths are relative to the drive root).

## Top level, with folder sizes

| Folder | Size |
|---|---|
| Drop Deck Trailers | 69.0 GB |
| Tag Trailers | 41.0 GB |
| Drone Items | 31.4 GB |
| Dog Trailers | 28.6 GB |
| Skel Trailers | 15.3 GB |
| Flat Tops Trailers | 11.3 GB |
| z Second Hand and Miscelaneous | 6.7 GB |
| Road Trains | 2.8 GB |
| Brochures | 2.7 GB |
| Customised Trailers | 2.4 GB |
| Hay Spec Trailers | 1.8 GB |
| Skip Bin Transfer Trailers | 736 MB |
| Tipping Trailers | 529 MB |
| Steel Mezz Deck Trailers | 505 MB |
| Auto Twist Lock Skels | 324 MB |
| Dollies | 257 MB |
| z.Close Up Photos of Trailer Parts | 249 MB |
| z. Opposition Trailers | 226 MB |
| z.BiFold Ramps Photos | 198 MB |
| z.Show Trailers | 190 MB |
| Skel - Retractable | 151 MB |
| Trailer Drawings | 135 MB |
| z.R&D | 124 MB |
| z.Creo Trailer Image Files | 29.7 MB |
| Pole Jinker Trailers | 2.1 MB |
| z.Tare Weights | 6.8 MB |

Roughly **250 GB** in total. Sizes are the cost estimate to plan against, not the file
counts — file counts require the recursive walk below.

> **Superseded by a full enumeration, 2026-08-26.** The byte totals above are confirmed
> exactly; the file counts and the video assumption are now measured rather than guessed.
> See "Enumerated" at the foot of this file. The eyeballed ~250 GB is really **216.7 GB**.

## Enumeration must recurse. This is not optional.

Several of the largest folders hold **no loose files at all** — only subfolders.
Verified: `Drop Deck Trailers` contains exactly `1. Semi Drop Deck Trailers` (68.97 GB)
and `2.Drop Deck Extendable` (37.3 MB), and nothing else.

A walk that lists only the immediate children of each product folder therefore sees
zero images in the library's biggest collections, while correctly counting the folders
that keep images loose at the top level (`Customised Trailers`, `Skel Trailers`,
`z.Close Up Photos of Trailer Parts`). The failure is silent and it looks like a
finding — "that folder is empty" — rather than like an error.

Recurse to the leaf, and record depth so the manifest can be sanity-checked against
these byte totals.

## What the path already tells us, for free

The tree encodes taxonomy in two layers before any subfolder-level detail:

- **Level 1 — product category**: `Drop Deck Trailers`, `Tag Trailers`, `Skel Trailers`,
  `Dog Trailers`, `Tipping Trailers`, `Dollies`, `Road Trains`, ...
- **Level 2 — numbered variant or axle configuration**: `1. Semi Drop Deck Trailers`,
  `2.Drop Deck Extendable`, and in Tag Trailers the axle split
  `1. Single Axle` / `2. Tandem Axle Tag Trailer` / `3. Tri Axle`.
- **Deeper** — customer, build date and job number, per the handover
  (`2025.08 - Team Transport (BH) Quad Skels - 3467, 3468`).

Note the numbering prefixes are inconsistently punctuated (`1. Semi...` with a space,
`2.Drop Deck Extendable` without). Strip `^\d+\.\s*` when parsing; do not match on the
literal string.

Never pay a model to infer any of this. Parse the path.

## Filenames are not uniformly camera-default

The handover recorded camera-default names (`IMG_0356`-`IMG_0395`, `P1050077`+,
`DSC02846`+, `DSCN7332`+), and those dominate. But some files are already descriptive —
e.g. `Hills_Shire_council_Tandem_Axle_tag_trailer_1.jpg` through `_4.jpg`, and
`close up of BPW axle hub.JPG`.

Two consequences: descriptive filenames are a free source of customer and
configuration, and a set of them covering the same trailer is a free validation set —
tag them blind and check the output against the name.

## Hazards to handle before spending anything

- **Video is mixed in.** `Drone Items` at 31.4 GB is named for a medium that is mostly
  video, and mp4s are known to sit inside `Auto Twist Lock Skels` and `Tag Trailers`.
  Filter on extension during enumeration, not during tagging.
- **Non-photographic content is filed alongside photographs.** `Trailer Drawings`,
  `z.Creo Trailer Image Files` (3D renders), `Brochures` (document pages) and
  `z.Tare Weights` (weighbridge documentation) are all images of things that are not
  trailers-in-the-world.
- **`z. Opposition Trailers` is competitor equipment.** 226 MB of it. A tagger that
  labels these as Midland product creates a real risk of a competitor's trailer being
  published as Midland's own work. The schema must carry an explicit
  `is_midland_product` field, and this folder is a required member of the Thursday
  hard-case set.

## Enumerated — 2026-08-26

`tools/enumerate_delta.py` over Graph `/delta`, scoped to the library folder.
**41,421 files, 40,452 images, 216.7 GB, 213 delta pages, max depth 8.**

Every folder byte total above reproduced **exactly** — Drop Deck 69.0 GB, Tag Trailers
41.0, Drone Items 31.4, Dog Trailers 28.6, Skel 15.3, Flat Tops 11.3. That agreement is
the check that the walk was complete, and it is the reason to trust the counts below. No
folder came back with large bytes and zero images.

| Folder | files | images | video | doc | GB |
|---|---|---|---|---|---|
| Drop Deck Trailers | 5,984 | 5,755 | 152 | 1 | 69.0 |
| Tag Trailers | 4,889 | 4,772 | 86 | 11 | 41.0 |
| **Drone Items** | **19,234** | **19,138** | **43** | 0 | 31.4 |
| Dog Trailers | 4,273 | 4,211 | 50 | 0 | 28.6 |
| Skel Trailers | 1,404 | 1,363 | 33 | 4 | 15.3 |
| Flat Tops Trailers | 1,241 | 1,206 | 28 | 0 | 11.3 |
| z Second Hand and Miscelaneous | 1,774 | 1,701 | 0 | 42 | 6.7 |
| Brochures | 483 | 285 | 0 | 169 | 2.7 |
| Customised Trailers | 592 | 578 | 14 | 0 | 2.4 |
| Road Trains | 108 | 100 | 6 | 0 | 2.8 |
| Hay Spec Trailers | 354 | 341 | 13 | 0 | 1.8 |
| *(19 smaller folders)* | 1,085 | 1,002 | 16 | 63 | 2.7 |

### CORRECTED — `Drone Items` is not mostly video

The hazard note above reads *"`Drone Items` at 31.4 GB is named for a medium that is
mostly video."* **It is not.** It holds **19,138 images and 43 videos** — 47% of every
image in the library, in one folder. It is GoPro burst photography: 23 subfolders named
`143GOPRO`, `174GOPRO`, `175GOPRO` … each holding about 1,000 frames named `G0012102.JPG`.

This changes the shape of the job. Nearly half the tagging volume sits in one folder of
near-identical aerial bursts, which is exactly where `duplicate_group` earns its place and
exactly the population to sample rather than tag exhaustively. It is also the strongest
argument for the cheap model tier: 19,000 frames of one subject at Fable prices is the
whole budget.

### Video is 1% of files but 36% of bytes

**441 videos, 77.6 GB.** So the extension filter is worth far more than the file count
suggests — it keeps 36% of the library's bytes out of vision calls entirely. The largest
single file is a **3.76 GB** `DJI_0208.MP4`; the folder test's "102 MB mp4 that would have
killed a run mid-batch" was one of the smaller ones.

Coverage should be denominated by **images (40,452)**, never by all files, or the
legitimately untagged video population makes coverage read broken.

### Filenames: 4.6% descriptive, not 58%

Only **1,894 files** carry real words (`Internal Tie Down Point.JPG`,
`Midland Trailer Brochure V4 OP.pdf`, the `Hills_Shire_council_…` set). Everything else is
a camera counter.

Getting this right took a second pass and is worth recording, because the first attempt
was wrong in a way that looked fine: a shorter camera-default pattern list flagged **58%**
of the library as descriptively named, including all 18,860 GoPro `G0012102` frames. Both
consequences are silent — a descriptive name *breaks* a shoot run, so grouping collapsed
in the largest folder (19,234 files fell into 2 groups), and descriptive names are treated
as free ground truth, so the validation set would have been poisoned with camera counters.
The patterns now in `tools/enumerate_delta.py` were derived by clustering the real
filenames, not guessed: GoPro, DJI, WhatsApp, Android, iOS, Canon `MVI_`, bare counters and
epoch-ms stamps, plus `(2)` / `- Copy` / `_resized` suffixes.

### Shoot groups: ~2,400, and "consecutive" has to be enforced

**2,437 shoot groups over 39,527 grouped files** — median 4 frames, mean 16.

The word *consecutive* in "a run of consecutive camera-default filenames" is load-bearing,
and a first implementation that grouped every camera-default file in a folder into one run
looked plausible while being wrong: all 1,017 frames of `Drone Items/143GOPRO`, **spanning
seven separate dates**, came out as a single shoot. A run now breaks on a descriptive
filename, a change of filename prefix, a counter jump beyond ~10 frames, or a change of
capture date. That folder resolves into 12 single-date groups.

Large groups are not automatically wrong. `Drone Items/175GOPRO` is one group of 999 and
should be: single date, counter `G0018481` → `G0019479`, **zero gaps**. That is a
continuous time-lapse, and it is precisely the population `duplicate_group` exists for.

A caution for anything that keys off capture dates: several GoPro folders carry a default
camera clock (`2012-01-03` across all 999 frames of `175GOPRO`), so the date is reliable
for *splitting* a run but not for dating the trailer. Build date comes from the folder
name, not from file metadata.
