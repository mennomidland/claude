# Routine 1 — Enumerate the sales photo library

**Runs first. No model calls, no vision, no cost beyond connector reads.**
Must run as a routine, not in a chat session: a single folder listing here can be
150+ lines and enumerating the whole tree in chat would exhaust the context before
it finished.

Its only job is to produce the manifest that becomes the work queue for tagging.

## Configuration

- Library root: `Sales/1. Trailer Photos` on drive
  `b!kxUlnz9hTEGIP79tTDljrR9Yzea0cmdLraKjspDsTfIFN9XvZPm7RKua__mqYOLv`
  (site `SalesMarketingTeam`; the `Shared Documents` segment is omitted from
  `read_resource` URIs).
- Output location: `Sales/_image-tagging/` — a **sibling** of the photo library, not
  inside it, so nothing this project writes is ever mistaken for photo content.
  Create it if absent.
- Tools required: `mcp__Microsoft_365__read_resource`,
  `mcp__Microsoft_365__sharepoint_create_folder`,
  `mcp__Microsoft_365__sharepoint_upload_file`. **These must be in the routine's
  allowed-tools list.** The original routine's allowlist was
  `Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch` with no `mcp__*` entries,
  which is how an unattended run ends up unable to read SharePoint at all.

## The prompt

> Enumerate the Midland sales photo library and write a manifest. Do not tag anything,
> do not call any vision model, and do not look at the contents of any image. This pass
> is a directory walk and nothing else.
>
> **Read-only on the photo library.** Do not modify, move, rename, retag or delete
> anything under `Sales/1. Trailer Photos`. The only writes you make are the manifest
> files described below, into `Sales/_image-tagging/`.
>
> 1. Start at `file:///{driveId}/Sales/1. Trailer Photos` and walk it **recursively to
>    the leaf**. Recursion is the whole point of this pass: several of the largest
>    folders contain no loose files at all, only subfolders — `Drop Deck Trailers`
>    (69 GB) holds only `1. Semi Drop Deck Trailers` and `2.Drop Deck Extendable`. A
>    walk that lists only immediate children reports those folders as empty. If you
>    find a folder with no files, recurse into its subfolders before recording
>    anything about it.
>
> 2. For every file, record: `drive_id`, `item_id`, full path, filename, lowercased
>    extension, `size_bytes`, `last_modified`, and `depth` (folder levels below the
>    library root).
>
> 3. Set `media_class` from the extension alone: `image` for jpg/jpeg/png/heic/tif/tiff/
>    webp/bmp, `video` for mp4/mov/avi/m4v/mts/wmv, `document` for pdf/docx/xlsx/pptx,
>    `other` for anything else. Videos are mixed in throughout — `Drone Items` is 31 GB
>    and mostly video, and mp4s sit inside `Auto Twist Lock Skels` and `Tag Trailers`.
>    Excluding them here is what stops a vision call failing mid-run later.
>
> 4. Derive `path_derived` for each file by parsing the path only — never by opening the
>    image:
>    - `product_category`: the level-1 folder name.
>    - `variant`: the level-2 folder name with any leading `N.` stripped. The numbering
>      punctuation is inconsistent (`1. Semi Drop Deck Trailers` with a space,
>      `2.Drop Deck Extendable` without), so strip the pattern `^\d+\.\s*` rather than
>      matching literal strings.
>    - `axle_config_from_path`: only where a path segment states it. **A trailer with
>      two axles is a Tandem. Never write "bogie" — it is not Midland's word and it is
>      not permitted anywhere in this project's output.** Where the path does not state
>      an axle count, emit `unstated`. Do not infer it from the product category.
>    - `customer`, `build_date`, `job_numbers`: from deeper folder names where present,
>      e.g. `2025.08 - Team Transport (BH) Quad Skels - 3467, 3468` gives build date
>      `2025.08`, customer `Team Transport`, job numbers `["3467","3468"]`. Record
>      **all** job numbers found — more than one means the folder holds more than one
>      trailer, which later matters for knowing which trailer is in a given frame.
>    - `content_expectation`: `competitor` for anything under `z. Opposition Trailers`,
>      `render` for `z.Creo Trailer Image Files`, `drawing` for `Trailer Drawings`,
>      `brochure_or_document` for `Brochures` and `z.Tare Weights`, `component_detail`
>      for `z.Close Up Photos of Trailer Parts` and `z.BiFold Ramps Photos`, `aerial`
>      for `Drone Items`, `second_hand_or_misc` for `z Second Hand and Miscelaneous`,
>      otherwise `midland_trailer`.
>
> 5. Group shoots. Within a single folder, a run of consecutive camera-default
>    filenames (`IMG_nnnn`, `DSC_nnnn`, `DSCN_nnnn`, `P10nnnnn`, `YYYYMMDD_HHMMSS`) is
>    normally one photo shoot of one trailer. Assign a stable `shoot_group` id per run
>    and a `shoot_group_position` within it. Also set `filename_is_descriptive` false
>    for those patterns and true for names carrying real words — some files are already
>    named things like `Hills_Shire_council_Tandem_Axle_tag_trailer_1.jpg`, and those
>    are worth knowing about because they can validate the tagger for free.
>
> 6. **Checkpoint per top-level folder.** After finishing each level-1 folder, upload
>    `Sales/_image-tagging/manifest/{folder-slug}.json` immediately. Do not hold the
>    whole library in memory and write once at the end — the container is reclaimed
>    after the run, so anything unwritten is lost. If a checkpoint file already exists
>    when you start, skip that folder: that is what makes this pass resumable rather
>    than restarting from the first folder every time.
>
> 7. When all folders are done, write `Sales/_image-tagging/manifest/_summary.json`
>    containing, per level-1 folder: file count, image count, video count, other count,
>    total bytes, maximum depth reached, and the count of distinct shoot groups.
>
> 8. Report back: the totals per folder, and any folder where **image count is zero but
>    total bytes is large** — that combination means the walk failed to recurse, not
>    that the folder is empty, and it must be re-run rather than reported as a finding.
>    Sanity-check your byte totals against these known folder sizes: Drop Deck 69.0 GB,
>    Tag Trailers 41.0 GB, Drone Items 31.4 GB, Dog Trailers 28.6 GB, Skel Trailers
>    15.3 GB, Flat Tops 11.3 GB. A total far below these means an incomplete walk.
>
> Do not proceed to tagging. Do not schedule follow-up work. Stop when the manifest and
> summary are written, and say plainly what failed or what you had to guess at.

## Why each of these is here

| Instruction | Defect it closes |
|---|---|
| Recurse to leaf, and the zero-images-but-large-bytes check | A top-level-only walk silently reports the biggest folders as empty |
| Checkpoint per folder, skip existing | No resume state — every run re-doing the same first N files |
| Output to `Sales/_image-tagging/` | Output location previously undefined; container-local writes vanish |
| `mcp__*` in the allowlist | SharePoint reads denied outright in an unattended run |
| `media_class` by extension | A vision call dying on a 41 MB mp4 mid-run |
| Never "bogie" | House vocabulary. A general model reaches for it constantly on Australian trailer photos |
