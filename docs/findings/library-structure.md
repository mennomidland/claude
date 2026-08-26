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
