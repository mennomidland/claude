# Thursday — schema iteration, not volume

**Run this interactively.** An unattended 09:00 failure costs a quarter of the
Thu–Sun budget before anyone is awake to see it. Thursday is for making the schema
and prompt right; Fri–Sun is for volume.

The method is the point: **a fixed set of ~40 images, tagged repeatedly.** Same images
every pass, so a prompt change produces a measurable difference rather than an
impression. Three to four passes. The cost of the whole day is roughly 4 × 40 images.

## Step 0 — pin the set (once, then never change it)

Select 40 images from the manifest and write the list to
`Sales/_image-tagging/goldset/goldset-v1.json` as explicit drive+item ids. Pin it.
If the set drifts between passes, nothing measured on Thursday means anything.

Composition — deliberately weighted to hard cases, because the easy frames are not
where the schema breaks:

| n | Drawn from | Tests |
|---|---|---|
| 8 | Drop Deck, Tag, Skel, Dog Trailers — complete trailers | The ordinary case, incl. axle counting |
| 4 | `z. Opposition Trailers` | Competitor detection. The costly failure |
| 4 | `z.Creo Trailer Image Files` | Render vs photograph |
| 3 | `Trailer Drawings` | Drawing vs photograph |
| 3 | `Brochures`, `z.Tare Weights` | Document/screenshot, text-heavy frames |
| 4 | `z.Close Up Photos of Trailer Parts`, `z.BiFold Ramps Photos` | Component detail with no whole trailer in frame |
| 4 | `Drone Items` (images only) | Aerial and top-down perspective |
| 3 | `Customised Trailers` | Part-built, unpainted, workshop clutter |
| 3 | Any folder naming two or more job numbers | Which trailer is in frame |
| 4 | The `Hills_Shire_council_Tandem_Axle_tag_trailer_1-4.jpg` set | Free ground truth — the filename already states the answer |

Then label the 40 by hand, once, into `goldset-labels.json`. Without human labels there
is no way to tell an improvement from a drift. This is the most valuable hour of the
week and it is not delegable.

## The tagging prompt

> You are tagging one photograph from Midland's sales photo library so that marketing
> and sales can find it later. Return a single JSON object conforming to the `vision`
> object of `trailer-photo-tags.schema.json`. Return nothing else — no prose, no
> preamble, no explanation outside the `notes` field.
>
> **Midland house vocabulary.** A trailer with two axles is a **Tandem**. Never write
> "bogie". It is not Midland's word — their own folders read `2. Tandem Axle Tag
> Trailer` — and it must not appear in any field, including `notes`. One axle is
> Single, two is Tandem, three is Tri, four is Quad.
>
> **Report only what you can see.** You are looking at a photograph. Suspension part
> numbers, kingpin locations, chassis centres, load restraint heights, ramp dimensions,
> ATM and GTM ratings are not legible in a photograph, and no field in this schema asks
> for them. Do not put them in `notes`. If you find yourself producing a plausible
> number, you are inventing it.
>
> **`unknown` is a correct answer and is never penalised.** Every enum in this schema
> accepts `unknown`, and most also accept `not_visible`. Use `not_visible` when the
> feature is confidently outside the frame or occluded; use `unknown` when it is in
> frame but you genuinely cannot judge it. A tagger that always commits to a value is
> less useful than one that says when it cannot tell, because a confident wrong tag is
> found by a search and acted on, while an `unknown` is filtered out.
>
> **On whose trailer this is.** `is_midland_product` should be `midland` only where
> Midland branding is visible or the build is unmistakably theirs, `competitor` where
> another manufacturer's branding or a distinctly different build is visible, and
> `unknown` otherwise. Most unbranded trailers are honestly `unknown`. Do not assume a
> trailer is Midland's because it is in Midland's library — the library contains
> competitor equipment on purpose.
>
> **Count axles on the trailer only**, excluding any prime mover in the frame. If the
> rear axles are hidden behind a load or cropped out, that is `not_visible`.
>
> **An axle group does not belong to the trailer it appears to sit under.** This is the
> single most reliable way to get a multi-trailer frame wrong. An **A-trailer** carries a
> fifth wheel mounted *above its own rear axle group*, and the following trailer's kingpin
> sits on that fifth wheel. So in an A-double the lead trailer's axle group sits directly
> beneath the **front of the second trailer's body** — and looks, to anyone reading the
> picture as a picture, like it belongs to the second unit. It does not.
>
> Assign an axle group by **tracing the chassis rail back to the body it is attached to**,
> never by which container or deck happens to be above it. If the chassis is obscured and
> you cannot trace it, the correct answer is `not_visible` on both units — not a guess
> based on position.
>
> The same caution applies to dog trailers and B-doubles, where the drawbar or the extended
> rear of the lead unit puts running gear in visually misleading places.
>
> Judge `marketing_usability` as a marketing manager would: `hero` for a frame you would
> lead a campaign with, `reject` for one you would not publish. Workshop clutter, people
> in shot, backlighting and partial crops all matter here, and belong in `defects` too.
>
> **Record what is in the picture, not just what kind of trailer it is.** Three fields
> carry this and they are the ones a person actually searches on:
>
> - `components_visible` — the parts of each unit you can see: control panel, air lines,
>   twist locks, kingpin, landing legs, wheels and rims, mudguards, marker lamps, coaming,
>   deck floor, and so on. **Positive only** — list what is there and omit the rest.
> - `features_present` — equipment visibly fitted: auto twist locks, a bifold ramp, a
>   toolbox, a tyre carrier, load racks, gates.
> - `demonstrates` — what this frame is *evidence of*. A close side view of a control
>   panel demonstrates `twist_lock_system`, whatever the folder says the trailer is.
>
> **Never record a feature you cannot see.** Do not infer a toolbox from the product
> category, from the folder name, or from what such a trailer usually has. A hallucinated
> feature is worse than a missing one: it will be found by a search and shown to a customer
> as the thing they are buying. An empty `features_present` is a fine answer.
>
> Note that a component can be visible while its property is not. The axle group is plainly
> in frame in a cropped side view — `components_visible` includes `axle_group` — and the
> axle count is still `not_visible` because the group runs off the edge. Those are
> different questions; answer them separately.
>
> Set `needs_human_review` true whenever you are unsure in a way that matters — a frame
> you think may be a competitor's, a render you are not certain is a render, a trailer
> you cannot categorise.

**Do not show the model the folder path or `path_derived`.** Tag blind. The path is
already known and is authoritative; the value of the vision pass is that it is
*independent*, which is what makes the `audit` comparison able to catch a photo filed
in the wrong folder. Show the model the path and it will simply restate it, and the
audit becomes a tautology.

## Each pass

1. Run the 40 through with the current prompt version. Record `prompt_version`.
2. Score against `goldset-labels.json`: per-field agreement, and separately the rate of
   `unknown` per field. A field that is almost always `unknown` is badly defined; a
   field that is never `unknown` is being guessed at. Both are prompt bugs.
   For `components_visible` and `features_present`, score **precision before recall**: a
   missed toolbox costs a search hit, an invented one gets shown to a customer. Any feature
   claimed that a human cannot find in the frame is a stop-and-fix, exactly like a
   competitor frame tagged `midland`.
3. Check the audit signals: `axle_agreement`, `category_agreement`, and every
   `provenance_conflict`. Any competitor frame tagged `midland` is a stop-and-fix.
4. Revise the prompt or the enums — one change at a time — and re-run **the same 40**.
5. Freeze when a pass produces no change worth making.

## Then, before scaling

With the schema frozen and the gold set labelled, one more cheap experiment settles the
model question for the long tail: run the same 40 on Haiku 4.5 and compare per-field
agreement against the Fable run.

| Model | Input /1M | Output /1M |
|---|---|---|
| Fable 5 | $10.00 | $50.00 |
| Sonnet 5 | $2.00 | $10.00 |
| Haiku 4.5 | $1.00 | $5.00 |

Fable is sanctioned for Thursday's labelling and for hard cases. But the frozen task is
closed-enum classification of a photograph, which is what the cheap models are good at,
and Haiku is 10× cheaper on both sides. Batch API is a further 50% off and this is
textbook batch work — roughly 20× combined. On ~250 GB of library, that difference
decides whether Fri–Sun covers the valuable categories or the whole thing.

Scale Fri–Sun through the manifest in priority order, checkpointing after every batch.
`z. Opposition Trailers`, `z.Tare Weights`, `Brochures` and `Trailer Drawings` go last.
