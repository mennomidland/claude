# Research brief — trailer domain knowledge for a photo tagger

**For a Claude session with unrestricted internet access.** This session's egress proxy
blocks `midlandind.com.au`, `truck.net.au` and most PDF hosts, so the research below could
not be done here. Everything in this brief is self-contained — the researcher needs no
prior context on the project.

---

## The job you are helping with

Midland Pty Ltd (Australian trailer manufacturer, Kyneton VIC) has ~40,000 photographs of
their trailers in SharePoint. Filenames are camera defaults and carry no meaning. We are
building a vision pass that tags each photo so sales and marketing can find images.

**We are not trying to extract specifications.** The build specs already exist in
Manufacturing Job Cards. The vision pass answers only what a photograph can answer:
what is in the frame, what equipment is visibly fitted, and what the photo would be
*useful for*.

Two rules govern the whole project, and they should govern your research too:

1. **Never invent.** A confidently wrong tag gets found by a search and shown to a
   customer as the thing they are buying. Every claim you return must carry a source URL.
   If you cannot confirm something, say so — a gap is far more useful than a guess.
2. **Australian usage only.** A general model reaches for US terminology constantly, and it
   is wrong here. The standing example: a trailer with two axles is a **Tandem**, never a
   "bogie". Midland's own folders read `2. Tandem Axle Tag Trailer`. Part of your job is to
   find the *other* traps like this one.

---

## Why this research is needed — two real failures

These are the failure modes to aim at. Both were mine; neither was a vocabulary gap.

**1. I misread a photograph because I did not understand the equipment.** A frame showed
two skel trailers carrying containers. A tri-axle group sat visibly under the front of the
second trailer, so I assigned it to the second trailer. Wrong: in a B-double the lead
trailer carries a fifth wheel on a tail section mounted *directly above its own rear axle
group*, so that group belongs to the lead unit. No enum change would have fixed this —
it needed knowledge of how the combination is assembled.

**2. The A/B naming is ambiguous and I only found it by accident.** On the workshop floor a
B-double's lead trailer is called the *A-trailer*. In ATA/regulator usage an *A-trailer* is
any **drawbar-coupled** trailer, making that same unit a *B-trailer*. Both correct in
context. We need to know where else this kind of collision exists.

**So the research target is not definitions. It is: what does a person who knows trailers
see in a photograph that a general model does not?**

---

## What we need — five questions

### Q1. Combination geometry, and how to tell configurations apart in a photo

For every Australian heavy combination — rigid, semi, **B-double, B-triple, A-double,
A-B combination, road train (types 1/2/3), pocket road train, truck-and-dog / dog trailer,
converter dolly, PBS combinations** — we need:

- Where the couplings sit, and **which unit each axle group physically belongs to**.
- **The visual discriminator**: in a side-on photograph, what tells you it is a B-double
  rather than an A-double? (Our current best answer: a drawbar and a gap means A-double or
  dog; two close-coupled bodies sharing one axle group at the join means B-double. Confirm
  or correct.)
- Any other case where an axle group sits under a body it does not belong to.

This is the highest-value question. Answer it first.

### Q2. Visual discriminators for spec options

For each of these, the question is **"how do you tell, from a photograph?"** — not what it
is. Where it is genuinely not distinguishable in a photo, say so; that is a valid and
useful answer, and it stops us adding a field a model would have to guess at.

| Option | What we need to be able to see |
|---|---|
| **Air bag vs spring (leaf) suspension** | Midland advertise "Air or Spring Suspension" as a customer choice. How do they differ visually? |
| **Over-slung vs under-slung** | We have this enum already but no reliable visual test |
| **Deck materials** — checker plate, Bissalloy, timber, aluminium | Midland advertise "Checker Plate or Bissalloy". How do they look different? |
| **Ramp types** — bifold, slide-out, fixed | How does each read when stowed, vs deployed? |
| **Container capability** — 20ft / 40ft / 45ft skel | Can twist lock positions or chassis length tell you? |
| **Self-steer axle** | Identifiable in a photo, or only from the job card? |
| **Coaming types** — channel, flush | Visual difference |
| **Extendable / widener chassis** | How does it read when retracted? |

### Q3. Midland's own product range and option vocabulary

Source: **https://midlandind.com.au** — the `/showcase/` pages, and the trailer range
brochure PDF (a copy is at
`https://admin.i-motor.com.au/ssl/CMS/files_cms/100542_midland_trailer_brochure.pdf`).

We want, **in Midland's exact wording**:

- Every model / product line they sell.
- Every option and feature they advertise per model.
- Any term they use that differs from generic industry usage.

This matters because these are the words sales and marketing will type into a search box.
Their vocabulary beats correct-but-unused industry vocabulary every time.

### Q4. Australian vs US terminology — build us a "do not use" list

We know one: **bogie → Tandem**. Find the rest. Specifically check:

drop deck / step deck (Midland's site appears to use both — are they synonyms in AU, or
different products?), flat top vs flatbed, skel vs chassis/container trailer, low loader vs
float vs lowboy, tautliner vs curtainsider, jinker, dolly, widener, mezz deck, landing legs
vs jacks/dollies, mudguards vs fenders, coaming, gates, headboard, rope rails, catwalk.

For each: the Australian term, the US term to avoid, and whether they are true synonyms or
subtly different things.

### Q5. Competitor manufacturers

The library deliberately contains competitor equipment, and a competitor's trailer
published as Midland's own work is the costly failure. We know **Krueger** appears.

We need the main Australian trailer manufacturers competing with Midland (Vawdrey,
MaxiTRANS/Freighter, Barker, Tefco, Haulmark, Drake and any others), and for each **any
visually distinctive branding, livery or build cue** that would show up in a photograph.

---

## Explicitly out of scope

Do not research these. We already have them, or they are not photographable:

- Axle/suspension part numbers, ATM/GTM ratings, brake specifications, dimensions. These
  come from the Manufacturing Job Card, exactly, and asking a model to infer them from a
  photo is what produced invented specifications on the first attempt.
- Regulatory mass and dimension limits, PBS approval processes, compliance rules.
- Anything about how to *build* a trailer.
- Pricing.

---

## What we already have — do not re-derive these

Current schema enums. Tell us what is **missing, wrong, or misnamed** — do not restate them.

```
trailer_configuration: semi_trailer, dog_trailer, tag_trailer, converter_dolly,
                       road_train_combination
body_type:             skeletal, skeletal_retractable, flat_top, drop_deck,
                       drop_deck_extendable, step_deck, float_or_low_loader, deck_widener,
                       plant_trailer, tipper, skip_bin_transfer, hay_spec, pole_jinker,
                       steel_mezz_deck, curtainsider, water_tank
axle_count:            single, tandem, tri, quad, five_or_more
suspension_mount:      over_slung, under_slung
coupling_type:         kingpin_fifth_wheel, ball_race, drawbar_pin
floor_type:            flush, raised_coaming, no_floor_skeletal
coaming_type:          channel, flush_only, none
front/rear_ramp:       none, fixed, slide_out, bifold
components_visible:    axle_group, wheels_rims, tyres, mudguards, chassis_rail, kingpin,
                       landing_legs, suspension, brake_components, control_panel,
                       air_lines, electrical_lines, marker_lamps, tail_lamps, mudflaps,
                       reflective_markings, deck_floor, coaming, headboard, rear_frame,
                       twist_locks, toolbox, tyre_carrier, ramps, gates, load_racks,
                       catwalk_walkway, ladder, spare_wheel, drawbar, turntable
features_present:      auto_twist_locks, manual_twist_locks, bifold_ramp, fixed_ramp,
                       slide_out_ramp, toolbox, tyre_carrier, load_racks,
                       chain_anchor_points, gates, rope_rails, catwalk_walkway, ladder,
                       spare_wheel_carrier, winches, headboard, curtain, mezz_deck,
                       extendable_chassis, self_steer_axle, water_tank
```

Every field also accepts `unknown`, and most accept `not_visible`. Keep that convention in
anything you propose.

---

## How to return it — three files

### 1. `enum-proposals.json`

The machine-mergeable part. One object per proposed value:

```json
{
  "proposals": [
    {
      "field": "suspension_type",
      "status": "new_field",
      "value": "air_bag",
      "label": "Air bag suspension",
      "visual_discriminator": "Rubber bellows visible between axle and chassis rail; ...",
      "confidence": "high",
      "sources": ["https://..."]
    },
    {
      "field": "body_type",
      "status": "rename",
      "value": "step_deck",
      "note": "Australian usage appears to treat this as ... rather than a separate body",
      "confidence": "medium",
      "sources": ["https://..."]
    }
  ]
}
```

- `status`: `new_field` | `new_value` | `rename` | `remove` | `merge`
- `visual_discriminator` is **required** for anything a tagger must see in a photo. If you
  cannot supply one, set `confidence: "low"` and say why — that tells us not to add it.
- `confidence`: `high` (stated by Midland or a regulator) | `medium` (consistent across
  independent industry sources) | `low` (single source or inference).

### 2. `findings.md`

Prose, for humans, in this order:

1. **Combination geometry** (Q1) — with the axle-attribution rules stated as rules a tagger
   can follow, and any diagrams you find linked.
2. **Visual discriminators** (Q2) — including an explicit list of *"not distinguishable in a
   photograph"* items.
3. **Midland's vocabulary** (Q3) — their wording, quoted.
4. **Do-not-use list** (Q4) — a table: Australian term | US term to avoid | true synonym?
5. **Competitors** (Q5).
6. **Could not confirm** — everything you looked for and did not find, or found only
   contradictory answers. **Do not skip this section.** A known gap is worth more to us
   than a confident guess, and we will act on it differently.

### 3. `sources.md`

Every URL used, with one line on what it supported and how authoritative it is. Prefer, in
order: Midland's own site → ATA / NHVR / state road authority → Australian manufacturer
sites → Australian trade press → general web. Flag anything US-origin explicitly, even if
you think it transfers.

---

## Two failure modes to avoid

- **Do not pad.** A short, sourced, honest answer beats a comprehensive-looking one. If Q5
  turns up nothing useful, three lines saying so is a good answer.
- **Do not smooth over conflicts.** Where sources disagree — as they do on A/B trailer
  naming — report the disagreement and who holds each position. Those conflicts are
  findings in their own right, and the A/B one directly caused a tagging error here.
