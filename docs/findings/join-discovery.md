# Finding: the spec join is available directly from SharePoint

> **STATUS: PARKED.** Scope was narrowed to the sales photo library only
> (`Sales/1. Trailer Photos/`). Spec joining against job cards is out of scope at
> this stage. Kept because the finding stands and the join is cheap when wanted.

Date: 2026-08-26. Verified by direct inspection via the Microsoft 365 connector.

## The question this answers

Handover open question 1 — *"Do the spec DB job numbers match the photo folder job
numbers?"* — was flagged as the highest-value unanswered question. It is now
answered: **yes**, and there is a better join source than the Power BI dashboard.

## What was verified

Photo folders carry job numbers such as `2025.08 - Team Transport (BH) Quad Skels -
3467, 3468` and `3373`. Those are the same identifiers as the job folders under the
jobs site:

| Photo folder token | Job folder | Confirmed |
|---|---|---|
| `3467, 3468` | `sites/jobs/Completed Jobs/3467/01/` | yes |
| `3373` | `sites/jobs/Completed Jobs/3373/01/` | yes |

Every job folder carries `.../{job}/01/JOB CARD/{job} Manufacturing Job Card*.pdf`
and, in most cases, the same card as **`.xlsx`**. The xlsx reads cleanly through
`read_resource` as tab-separated cell values — no OCR, no vision, no Power BI export.

## What the job card actually contains

Read of `Completed Jobs/3467/01/JOB CARD/Archive/3467 Manufacturing Job Card (2380).xlsx`
(224 rows x 115 columns, single `JOB CARD` sheet) returned, exactly:

- **Identity** — JOB NO. `3467-01`, QUOTE NO. `3467v1`, VIN `6K9049865SP947529`
- **Customer** — `BROWN & HURLEY (TEAM TRANSPORT) - JOHN COLE`, phone, email
- **Configuration** — `15.0m`, `QUAD AXLE`, `SKELETAL`, `SEMI TRAILER`
- **Geometry** — length 15000mm, deck width 2490mm, mainbeam centres 1010mm,
  kingpin location 1350mm, suspension location 10075mm, suspension spread 3825mm
- **Running gear** — axles `BPW 22.5" 10 STUD DRUM BRAKE 285 PCD`, axle 4 self-steer,
  suspension `BPW OT SERIES HD 220mm RH`, brake kit, boosters and slack adjuster
  lengths per axle, booster location `BL-18`
- **Coupling** — kingpin `JOST 50mm BOLT-IN`, CTA `024156`, 5th wheel `JOST JSK 37 CX`
- **Coaming & floor** — coaming size / height / rope rail / floor material, all `N/A`
  on this skel
- **Ramps, load restraint, accessories** — front/rear ramps, load racks, chain
  anchor points, gates, toolboxes, tyre carrier (all `N/A` here)
- **Colours** — chassis `FLAME RED`, and per-component colour rows
- **Ratings** — ATM `50.00 T`, GTM `33.0 T`
- **Plant** — fabrication `KYNETON`, fitout `PARKES`
- **Sign-off** — engineer `SATVIR SINGH`, date

## Why this beats the Power BI dashboard as the join source

1. **Same connector, same tenant, no export step.** The photos and the specs are in
   the same SharePoint. No Power BI extract to schedule or refresh.
2. **It is the source, not a rendering.** The dashboard's truncated column labels
   (`Er...`, `Cus...`, `Pro...`) are a display artefact of the dashboard. The job
   card has the real field names, so handover open question 2 largely dissolves.
3. **Wider field set.** The job card carries VIN, CTA numbers, ATM/GTM, per-axle
   brake detail, plant split and colours per component — beyond the dashboard columns
   listed in the handover.
4. **Per-unit granularity.** See the join key note below.

The dashboard's known data-quality problems (`Over Slung` vs `OVERSLUNG`, `1010` vs
`1010mm`, `11001430`, five spellings of null) are worth re-testing against the job
cards rather than assumed. This card returned `1010mm` with the unit suffix present
and used a single `N/A` spelling throughout, which suggests at least some of that
mess is introduced downstream of the job card, not present in it.

## The join key is job number + unit, not job number alone

Job numbers subdivide: `3467-01`, and elsewhere `Active Jobs/4130/02/`. One job number
can carry several built units. Photo folders frequently name **two or more** jobs in a
single folder (`3467, 3468`) — meaning that folder contains photos of more than one
trailer, and the folder path alone cannot say which trailer is in a given frame.

That is the real remaining job for a vision model, and it is much smaller than
spec extraction.

## Consequence: the vision task shrinks, and so does the model tier

The handover split spec fields into "vision-taggable" and "join-only". With the job
card join available, **almost everything in the vision-taggable list is also
join-available, and exactly so.** What is left that genuinely needs a look at the
pixels:

- **Which trailer** — disambiguating a frame within a multi-job folder
- **Shot type** — three-quarter front, side elevation, detail, interior, underside
- **Build state** — finished, part-built, unpainted, render vs photograph
- **Marketing usability** — is this frame actually publishable
- **A small audit set** — a few fields kept deliberately redundant with the join
  (axle count, body type, chassis colour) purely to detect a mis-keyed folder

None of that is spec extraction. It is classification of a photograph, which is
Haiku-shaped work, not Fable-shaped. Fable's sanctioned allowance is better spent on
the gold-set labelling pass and the hard cases than on the long tail.

## Reproducing the join

Photo path -> job token(s) by regex on the folder name -> `sharepoint_folder_search`
on the token, preferring `sites/jobs/{Active,Completed} Jobs/{token}/` -> read
`{token}/{unit}/JOB CARD/*.xlsx` via `read_resource`, preferring the highest REV and
the non-`Archive` copy -> map cells to fields.

Caveat: `sharepoint_search` for `3467` returned 25 results and folder search for
`3373` returned 267, including unrelated matches (`3373-CHASSIS.Ord` in the
ProductionTeam library). Filter results to the `sites/jobs` drive and to an exact
folder-name match on the token before accepting a join. Do not accept a fuzzy match.
