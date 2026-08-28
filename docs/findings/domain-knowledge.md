# Finding: the tagger needs trailer knowledge, not just a vocabulary

Date: 2026-08-27. Prompted by two corrections from Midland, both of which a bigger enum
would not have prevented.

## Why this file exists

The schema was built on the assumption that tagging is a labelling problem: give the model
the right words and it will apply them. Two failures show it is a *reading* problem — the
model has to understand how the equipment is put together before it can describe a picture
of it.

1. **Axle attribution.** A two-trailer frame was tagged with the visible tri-axle group
   assigned to the second trailer, because that is where it appears. It belongs to the
   lead trailer. Nothing in the enum was wrong; the reading was.
2. **Folder trust.** Photos are known to be filed in the wrong folders, so
   `path_derived` is a **hypothesis, not ground truth** — see below.

## Combination geometry — how to attribute an axle group

**The group does not belong to the trailer it appears to sit under.**

| Combination | Where the coupling is | What that does to the picture |
|---|---|---|
| **B-double** | Fifth wheel / turntable on a tail section mounted **directly above the lead trailer's rear axle group** | That group sits under the **front of the second body** while belonging to the **lead** trailer |
| **A-double / road train** | **Drawbar to a converter dolly**, which has **its own axles and its own fifth wheel** | A whole axle group belongs to **neither** trailer. Look for the drawbar and the gap |
| **Dog trailer** | Drawbar onto a front turntable | Has a **front** group under its own front end as well as a rear group |

Rule: trace the chassis rail back to the body it attaches to. Never attribute by what sits
above. If the chassis cannot be traced, `not_visible` on both units beats a guess.

### The A/B naming is genuinely ambiguous — keep it out of the tags

- **Workshop floor:** the lead trailer of a B-double is the *A-trailer*, the rear the
  *B-trailer*. Positional.
- **Regulator / engineering (ATA):** an *A-trailer* is any trailer with a **drawbar**
  coupling; a *B-trailer* has a **fifth-wheel** coupling. Which makes a B-double's lead
  trailer a "B-trailer" — the opposite sense.

Both are correct in their own context, which is exactly why neither belongs in an enum.
Record `trailer_configuration`, `coupling_type` and `axle_count`; let the words stay out.

## Consequence: the folder is a hypothesis, not an answer

Midland confirm that photos are sometimes filed in the wrong folder. That qualifies the
README's first rule. "Never ask a model for what the path already says" remains right about
**cost** — do not pay for a category the path states — but it was wrong to treat the path as
**truth**.

What changes:

- `path_derived` is a **prior**. Where vision and path disagree, the disagreement is the
  finding, not an error to be reconciled away.
- The `audit` block stops being a small redundancy check and becomes **the misfiling
  detector**, which is the main reason to keep vision fields that duplicate the path.
- Tagging **blind** — never showing the model the path, per `02-thursday-iteration.md` — is
  now essential rather than good practice. Show the model the path and the audit becomes a
  tautology and detects nothing.
- Expect real disagreements. `Midland Trailors CivicCast 13.jpg` sits under
  `2 Axle Dog Trailer` with three axles visible under the loaded deck. Given the geometry
  above that is **not** proof of misfiling — the group may belong to another unit — but it
  is exactly the kind of case the audit block exists to surface.

## Gaps the research exposed in schema v3

From Midland's own published range (Dog, Tag, Semi Drop Deck, Deck Wideners, Low Loaders,
**PBS Combination Trailers**, flat top, skel, retractable skel, hay spec):

| Missing | Why it matters | Visually taggable? |
|---|---|---|
| **Suspension type** — air bag vs spring | Midland advertise "Air or Spring Suspension" as a customer choice. `suspension_mount` records over/under slung, which is a different question | Yes — airbags and leaf packs look nothing alike |
| **Deck material** — checker plate, Bissalloy, timber | Advertised as a choice ("Checker Plate or Bissalloy"). `floor_type` records flush / raised coaming, not material | Yes — checker plate is unmistakable |
| **Container capability** — 20ft / 40ft / 45ft | The defining spec of a skel, and 45ft is called out as increasingly common | Partly — twist lock positions and chassis length |
| **PBS combination** | A named product line, absent from `trailer_configuration` | Only in combination shots |

These are the things a customer *chooses*, which makes them what sales will search for.
Worth adding before the gold set is labelled, since adding an enum afterwards means
re-tagging.

## Where research pays, and where it does not

Worth it: **combination geometry**, Australian configuration names, Midland's own product
and option vocabulary. All three change how a frame is read or what it can be found by.

Not worth it: spec detail that is not visible in a photograph — axle ratings, ATM/GTM,
suspension part numbers. The job card already carries those exactly
(`findings/join-discovery.md`), and asking a model to infer them is how the first attempt
produced invented specifications.

A caution on sources: generic (largely US) trailer references import the wrong words —
"bogie" for a Tandem is the standing example, and the same trap runs through deck, coupling
and body terminology. Prefer Midland's own material and Australian regulator sources.

Sources: [ATA configuration descriptions](https://new.truck.net.au/wp-content/uploads/2025/05/TAP-Description-of-Truck-Configurations-September-2024-final.pdf),
[Truck Dealers Australia — the ABCs of rig configuration](https://truckdealers.com.au/editorial/the-abcs-of-trailers-and-rig-configuration/),
[trucksales — do you know your A from your B](https://www.trucksales.com.au/editorial/details/do-you-know-your-a-from-your-b-118045/),
[Midland skel trailers](https://midlandind.com.au/showcase/skel-trailers),
[Midland drop deck trailers](https://midlandind.com.au/showcase/drop-deck-trailers).
