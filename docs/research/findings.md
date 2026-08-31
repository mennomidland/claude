# Findings — trailer domain knowledge for a photo tagger

Researched 31 August 2026. Every claim carries a source in `sources.md`. Where I could not
confirm something, it is in section 6, not smoothed over.

**Headline result:** Midland's own website answers more of this brief than any external source,
and it answers several questions *against* the current schema. Between February and August 2026
Midland published a set of "Complete Australian Guide" articles under `/news/` that read like
internal engineering documents. They are the highest-authority source available for this project
and they were not in scope in the brief. Start there, not with the regulator.

The second result: the A-trailer/B-trailer ambiguity is not a two-way conflict. It is a three-way
one, and Midland has publicly taken a side.

---

## 1. Combination geometry (Q1)

### 1.1 The axle-attribution rule, stated as a rule

Midland states it in the form a tagger needs: in a B-double the rear trailer has no front axle
group of its own, and rests on the lead trailer's rear fifth wheel exactly as the lead trailer
rests on the prime mover's.

So:

> **Rule 1.** In a B-double, the axle group that sits under the *front* of the rear trailer
> belongs to the **lead trailer**. The rear trailer owns only the axle group at its own rear.
> A B-double with two tri-axle trailers reads, front to back, as: prime mover axles → lead
> trailer's tri group (under the coupling point) → rear trailer's tri group.

This is exactly the failure described in the brief, and it generalises:

> **Rule 2.** Wherever one body appears to sit on top of another, the axle group under the join
> belongs to the **forward** unit. This applies at every B-type coupling — so in a B-triple it
> happens twice.

> **Rule 3.** The converse case is a **converter dolly**. Where two bodies are separated by a
> drawbar and a gap, the axle group immediately behind the gap belongs to the **dolly**, which is
> a separate registered unit and not part of either trailer. Both the NHVR and the ATA exclude
> dollies from the trailer count — the NHVR defines a road train as a motor vehicle towing two or
> more trailers, dollies excluded, and the ATA treats the dolly as part of the coupling system
> rather than a trailer.

Rule 3 is the mirror-image of the error in the brief. A tagger that learns "the group under the
front of a body belongs to the unit in front" will now over-apply it and assign dolly axles to the
lead trailer. Both rules need to be taught together, and the discriminator between them is the
gap: **no gap → forward unit owns it; drawbar and gap → the dolly owns it.**

### 1.2 The visual discriminator, confirmed

The brief's current best answer is correct. Confirmed independently by Midland, the NHVR and the
RAA:

| See this | It is |
|---|---|
| Two bodies close-coupled, the rear one's nose resting directly on the tail of the one in front, no drawbar, no gap | **B-double** (fifth wheel to fifth wheel) |
| Drawbar and a visible gap between bodies, with an axle group under the gap | **A-double / road train** (drawbar-coupled dolly) |
| Drawbar and gap, front axle group *steering* on a turntable, axle group at each end of the one body | **Dog trailer** |

The mechanism behind it: a B-double joins its trailers with a fifth wheel and kingpin, the same
coupling used between prime mover and semi; a road train links extra trailers with a drawbar and
turntable, letting each trailer steer somewhat independently. On an A-double the rear trailer's
front rests on a fifth wheel carried by the dolly, and the dolly is what the drawbar attaches to.

### 1.3 The single most useful discriminator for this library

Most factory photographs show **one trailer, not a combination**. For those, combination type is
unanswerable — but the *role* is not:

> **Rule 4.** A trailer photographed alone can be identified as a B-double lead unit by the
> presence of a **second fifth wheel mounted on a tail section at its own rear**. Midland states
> that an A-trailer needs that rear fifth wheel fitted and positioned for the specific B-trailer
> it will run with, and that a semi-trailer without one can only run standalone or in the rear
> position.

This is a high-value, easily-seen feature and it deserves its own boolean field
(`rear_fifth_wheel_fitted`). It is more reliable than trying to infer combination type from a
single-trailer photo, and it is the thing sales will actually search for.

### 1.4 Pig vs dog vs tag — three drawbar trailers, one visual test

The ATA gives crisp geometric definitions: a **pig trailer** has one axle or axle group in the
centre of the trailer; a **dog trailer** has an axle or axle group at each end. Midland defines a
**tag trailer** as connecting via a fixed drawbar and hitch with no independently steering front
axle group, so that part of the load transfers onto the towing truck's rear axle.

That gives a photographable test on **where the axle group sits along the deck**:

| Axle group position | Front group steers? | Configuration |
|---|---|---|
| One group, roughly centre of deck | No | **Pig trailer** |
| A group at each end | Yes — front on a turntable | **Dog trailer** |
| Group(s) toward the rear, fixed drawbar, no front group | No | **Tag trailer** |
| Rear only, kingpin at front, no drawbar | n/a | **Semi-trailer** |

Caveat, stated plainly: the pig/dog rows are directly sourced from the ATA. The tag row's *axle
position* is my inference from Midland's load-transfer mechanics, not a sourced statement — see
section 6. The *coupling* test for tag (fixed drawbar, no steering front group) is sourced.

### 1.5 Dog trailer sub-configurations — three named layouts, all countable

Midland names three, and all three are distinguishable by counting axles per group:

| Name | Front group | Rear group | Total |
|---|---|---|---|
| **Super dog** | single | tandem | 3 |
| **Standard dog** | tandem | tandem | 4 |
| **Quad dog** | — | extended rear | 5+ |

Midland notes "super dog" is industry shorthand rather than a formal NHVR classification, but says
it is used consistently across the Australian market. None of the three is in the schema.

### 1.6 Where a dog trailer is really two units

A trap worth knowing. The ATA notes that a dog trailer assembly is *usually* a semi-trailer with a
converter dolly as its forward axle group, and that only in the typical rigid-truck-and-dog tipper
case is the forward axle group fixed to the trailer. So a photograph of "a dog trailer" may in
fact be a semi-trailer plus a dolly — two registered units — and the front axle group belongs to
the dolly, not the trailer. The visual tell is whether the front axle group and drawbar form a
separable unit with its own fifth wheel, versus a turntable integral to the trailer frame. This is
genuinely hard in a photo and should default to `unknown`.

### 1.7 The ATA configuration code — recommend adopting it

The ATA publishes a compact notation that is almost perfectly suited to a photo tagger, because
every symbol in it is countable from a side-on photograph:

- `R` rigid truck, `A` prime mover + semi-trailer, `T` drawbar or converter-dolly trailer,
  `B` trailer coupled via a turntable on the forward trailer
- digits = number of axles in each group

So `B1233` is a B-double: single steer, tandem drive, tri lead, tri rear. `A123T23` is a Type 1
road train. `R12T11` is a three-axle rigid with a two-axle dog.

Recommendation: add a free-text `ata_configuration_code` field. It captures combination type,
axle counts *and* axle attribution in one string, it is checkable by a human, and it is the
notation engineers and regulators already use. It is also self-documenting about uncertainty — a
tagger that can only see part of the combination can emit a partial code.

### 1.8 Road train types, and a naming conflict on "pocket"

The NHVR labels an **A-double as a Type 1 road train** and an **A-triple as a Type 2 road train**,
and classes **B-triples as road trains** too. Midland adds that a rigid truck with two dog
trailers is a Type 2 road train. I found no authoritative definition of a "Type 3" road train — see
section 6.

**"Pocket" is contested.** The ATA uses it for a 19 m, 7-axle B-double. BTT Engineering uses
"pocket road train" for a 2-2-2 A-double up to 26 m. These are different vehicles. Do not add
`pocket_road_train` as an enum value without deciding which one Midland means.

---

## 2. Visual discriminators (Q2)

### 2.1 Air bag vs spring — yes, distinguishable

This is the one Q2 row that is reliably answerable, because the components are physically
different objects at the axle group and both sit in the open.

- **Spring (leaf):** a stack of curved steel leaves clamped together, U-bolted to the axle, with
  eyes at each end attached to the chassis via hangers and shackles.
- **Air bag:** a rubber bellows between the trailing arm and the chassis rail, plus air lines and
  a levelling valve. Air suspension is load-sharing, which is a requirement for Higher Mass Limits.

Midland advertise the choice as an option on almost every model, so it matters commercially. Note
that Midland's own airbag-vs-spring article is a *selection* guide and gives no visual test — the
visual description above is assembled from general suspension sources, several of them US-origin
(flagged in `sources.md`). The components are the same globally and Midland specify global brands
(BPW, Hendrickson, K-Hitch), so I rate this **medium-high**, not high.

Practical limit: it is visible only when the axle group is in frame and not hidden by mudguards or
a low camera angle. A three-quarter or low side-on shot usually shows it; a straight-on rear or a
loaded-deck shot usually does not. `not_visible` will be a common and correct answer.

### 2.2 Over-slung vs under-slung — do not tag this from a photo

Over-slung/under-slung describes where the spring sits relative to the axle beam: over-slung has
the spring above, under-slung below, and the difference in resulting deck height can be substantial.

Two problems for this project:

1. **Every source I found is US-origin and about light trailers** — RV suspension guides and
   American axle retailers. I found no Australian heavy-trailer source using these terms. That
   does not mean Australian builders don't use them, but the brief's own rule says flag this.
2. On an air-bag trailing-arm suspension the distinction becomes where the axle seat sits on the
   beam — near the top plate for under-slung — which is not visible from outside the assembly at all.

Recommendation: keep the enum for job-card data if it is already populated there, but **the vision
pass should always emit `not_visible`** for `suspension_mount`. This is a field a model would
guess at, which is precisely what the brief says to avoid.

### 2.3 Deck material — the brand is not visible, the surface is

This is the most important correction in this section.

Midland advertise the deck choice as Checker Plate or Bissaloy, and elsewhere as
Bissalloy/Hardox, and elsewhere as Hardox/checker or flat plate. But:

- **Bisalloy** (correct spelling) is an Australian brand from Bisalloy Steels Pty Ltd, product
  line Bisplate, grades BIS320–BIS600.
- **Hardox** is a Swedish brand from SSAB.
- Both are quenched-and-tempered abrasion-resistant wear plate, supplied smooth.

A Bisalloy deck and a Hardox deck are **visually identical**. A tagger cannot tell them apart, and
a tag claiming one or the other is exactly the invented-specification failure the brief warns
about. What *is* visible is the surface finish:

| Visible | Tag as |
|---|---|
| Raised repeating pattern across the deck | `checker_plate` |
| Smooth uniform plate, no pattern | `smooth_wear_plate` |
| Timber planking, visible grain and plank joints | `timber` |
| Frame rails with no continuous deck between them | `none_skeletal` |

Recommendation: `deck_material` should have `smooth_wear_plate` as a value and **must not have
`bisalloy` or `hardox` as values**. Brand belongs in a separate `deck_material_brand` field
populated from the job card only. Note also that "checker plate" (Midland's spelling), "chequer
plate" (also Midland's spelling) and "floor plate" (the BlueScope product name) are the same thing
and all three need to be search aliases.

Aluminium: Midland advertise removable alloy ramps but I found no Midland reference to an
aluminium *deck* — see section 6.

### 2.4 Ramps — stowed is the hard case

Midland's ramp vocabulary is wider than the schema's: single, bi-fold, H.D (heavy duty), flip-over
front ramps, pull-out steel ramps to the top deck, fixed or bi-fold rear, dual hydraulic ramp
spools, and beavertail-style rear ramps for plant on tag trailers.

Deployed is easy — the ramp is on the ground at an angle. Stowed is where it gets hard:

- **Bi-fold** stowed folds back on itself and stands roughly vertical or lies doubled at the rear;
  the hinge line across the middle of the ramp is the tell.
- **Slide-out / pull-out** stowed is retracted under the deck and may be almost invisible; look
  for the guide channels and a ramp end face at the rear.
- **Fixed / beavertail** is not a separate object — it is the rear section of the deck itself,
  angled down. The tell is the deck profile, not a ramp.
- **Flip-over front ramp** sits over the deck step on a drop deck.

`fixed` and `beavertail` are easy to confuse with "no ramp" because there is nothing ramp-shaped
to see. Recommend the tagger be instructed to read the *rear deck profile*, and to use
`not_visible` freely — a rear-quarter photo often cannot resolve slide-out vs none.

### 2.5 Container capability — partly yes

Twist lock count and spacing does carry real information. ISO 1161 fixes the corner-fitting
geometry and ISO 668 fixes container lengths, so lock positions must match. Midland's own guide
gives the lengths: 20 ft is 6.06 m, 40 ft is 12.19 m, 45 ft is 13.72 m high cube.

- **4 locks** at the extremes = 40 ft only (minimum configuration)
- **Locks at both 20 ft and 40 ft intervals** (up to 12 total) = can carry 1×40 ft or 2×20 ft;
  mid-position locks fold down for a single 40 ft box
- Midland's own option wording is **"up to 3-way container pins"** on drop decks and **"up to
  4-way container pins"** on skels, with **side loader pads** optional
- **45 ft** generally needs a retractable or extendable chassis rather than fixed locks

So: an **empty** skel frame photographed side-on is tag-able for capability by counting lock
positions. A **loaded** one is easier still — read the container. But note the honest limit: lock
positions tell you what the trailer *can* carry, not what it is rated or plated for. Tag
capability, never rating.

### 2.6 Extendable / widener retracted — yes, if you know where to look

Midland's low loaders widen from 2490 mm to 4000 mm and their retractable skels use a
10-tonne roller skate design with locking pins. Retracted, the tells are the **overlapping
sliding sections** of chassis or deck and the **row of locking pin holes** along the slide. On a
widener, retracted, the outer deck sections sit flush against the inner frame and the join line
runs the length of the deck. Medium confidence — I found no photo-annotated Australian source, so
this is assembled from the mechanism descriptions.

### 2.7 Split axle group — a strong new discriminator

Midland sell a **Split Axle Group with Steer Axle** across several models. Under PBS, splitting an
axle at least 2.5 m from the rest of the group raises legal mass. That 2.5 m gap is large and
unmistakable in a side-on photo: a visible run of chassis between one axle and the remaining
group, with the split axle steerable.

This is not in the schema at all, it is a Midland selling point, and it is one of the most
photographable features on this list. Add it.

### 2.8 Self-steer / lift axle

Midland offer Lift and Steer axles. A raised **lift axle** is unambiguous — the wheels are clearly
off the ground with the axle tucked up. A **lowered** lift axle and a **self-steer** axle are much
harder: a self-steer axle can sometimes be identified by the steering linkage and centring
mechanism visible at the axle, and it is often the rearmost axle of the group. The NHVR specifies
steerable rear axles with at least ±12 degrees of articulation and a centring mechanism.

Verdict: **`lift_axle_raised` is high confidence and worth a value of its own.** `self_steer` on a
straight, lowered axle is low confidence — recommend it stays on the job card.

### 2.9 Coaming — visible, but the vocabulary is a mess

See section 3 for the spelling problem. On visibility: coaming type is the profile of the rail
along the deck edge, seen best in a side-on or three-quarter shot. Midland's values are **Flush,
TFB and C-Channel** on drop decks, plus **Profile or standard** on dogs and **4 inch or 5 inch**
rails on flat tops and hay spec. Flush versus a raised channel is a clear visual difference. I
could not establish what TFB stands for or what it looks like — section 6.

### 2.10 Explicitly NOT distinguishable in a photograph

The brief asked for this list. Tag these `not_visible` or leave them to the job card:

- **Over-slung vs under-slung** (2.2) — and note this is on the current schema
- **Deck material brand** — Bisalloy vs Hardox vs any other smooth wear plate (2.3)
- **Deck plate thickness** — 3 mm vs 5 mm vs 6–8 mm chequer are indistinguishable
- **Self-steer axle when lowered and straight** (2.8)
- **Drum vs disc brakes** — behind the wheel; occasionally visible on a wheels-off or rear shot,
  never reliably
- **EBS vs ABS** — an electronics package, not a visible object
- **Kingpin 50 mm vs 90 mm**, and bolt-in vs drop-in — requires measurement, not observation
- **Single vs double position skid plate** — obscured by the coupling in almost every angle
- **Container pin *rating*** as opposed to position (2.5)
- **PBS approval status** — a certificate, not a feature. Nothing in a photo shows PBS approval.
  Any tag asserting it is fabrication.
- **Suspension brand** (BPW, Hendrickson, K-Hitch) — sometimes cast into the hanger and readable
  in a close-up, never in a general shot
- **Whether a trailer is Tow and Go or custom-engineered** — see 3.4; this is a commercially
  significant distinction with no visual signature

---

## 3. Midland's own vocabulary (Q3)

### 3.1 The product range as Midland names it

From the site navigation and footer. This is the search vocabulary that matters:

PBS Combination Trailers · Drop Deck Trailers · Low Loader Trailers · Tri Axle Low Loaders ·
Quad Axle Low Loaders · Skel Trailers · Container Skel Trailers · Retractable Skel Trailers ·
Hay Spec Combination Trailers · B Double Trailers · B Double Combination Trailers ·
Flat Top Trailers · Flat Top Extendable Trailers · Steel Spec Trailers · Tag Trailers ·
Dog Trailers · Pole Jinker Trailers · Beekeeper Trailers · Skip Bin Transfer Trailers ·
Pig Trailers · Tanker Trailers · Custom Trailers · Heavy Haulage Trailers · Lowboy Trailers ·
Drop Deck Widener · Tow and Go

Against the schema, the missing ones are: **pig trailer** (they sell it), **beekeeper**,
**tanker / water cart**, **double drop deck**, **super dog**, **quad dog**, **drop deck widener**,
**steel spec**, **PBS combination**, **B double combination**, **Tow and Go**.

### 3.2 Option vocabulary, in Midland's wording

| Midland's term | Notes for the schema |
|---|---|
| Air or Spring Suspension / Spring or Airbag | New field. They use both orderings and both spellings (airbag, air bag) |
| Combing Styles: Flush, TFB or C-channel | Their spelling. `TFB` is not in the schema |
| Coaming Rails: Profile or standard / 4 or 5 inch | Two more coaming vocabularies again |
| Checker Plate or Bissaloy / Bissalloy/Hardox / Chequer plate | Four spellings, two brands. See 2.3 |
| Up to 3-way / 4-way container pins, side loader pads | Schema says `twist_locks` |
| Lift and Steer axles | Schema has `self_steer_axle` only |
| Split Axle Group with Steer Axle | Missing entirely |
| Ring Feder / Ring feder / Ring feeder | Three spellings of Ringfeder. Missing from `coupling_type` |
| Pintle Hook / Pintel Hook | Their typo included. Missing from `coupling_type` |
| Bartlett Ball | Missing from `coupling_type` |
| 50 or 90 Kingpin, bolt or drop-in | Not photographable |
| Skid plate, single or double position | Not photographable |
| Outriggers | Missing |
| Container pins and pedestals | `pedestals` missing |
| Top decks / top deck | Missing |
| Bolsters — straight or stepped / adjustable load bolsters | Missing |
| Webrail / Web rail fall protection | Missing |
| Mez Deck / Mezz Decks with Folding Top and Bottom Gates | Both spellings on one page |
| In deck chain points / in deck tie bars / in-deck tie downs | Schema has `chain_anchor_points` |
| Various dog and chain storage | Note: "dog" here means a load-binder dog, not a trailer |
| Hydraulic front leg / drop down rear legs | Tag trailers. Missing |
| Jost landing legs | Brand; schema has `landing_legs` |
| Beavertail | Tag trailer plant ramps. Missing from ramp enum |
| Single, bi-fold or H.D ramps / flip over front ramps | `H.D` and `flip_over` missing |
| Dual hydraulic ramp spools | Dog trailers |
| Roller skate / skate mechanism, locking pins | Retractable skels |
| Perimeter frame construction | PBS A-double skel |
| Winch track, Load Binders on track | Hay spec |
| Plug and play wiring harness, multivolt LED lights | Standard across the range |
| Poly zinc undercoating, powder coating, sandblasting | Their "Prepare and Protect" system |

Note the pattern: Midland's own copy is internally inconsistent on **coaming/combing**,
**checker/chequer**, **Bissaloy/Bissalloy**, **Ring Feder/feeder**, **Mez/Mezz** and
**airbag/air bag**. Every one of those needs to be an alias in the search layer, not a separate
enum value.

### 3.3 Terms where Midland disagrees with generic usage

- **Drop deck = step deck.** Midland state directly that there is no difference between the two.
  They also say drop deck and semi drop deck are the same thing. The schema has `drop_deck` *and*
  `step_deck` as separate values — that should merge.
- **Lowboy is American.** Midland say the term originated in America and that a lowboy is the same
  as their Drop Deck Widener and Low Loaders. The Lowboy page exists for search traffic, not
  because it is a distinct product.
- **Low loader = float.** Midland use "float" as the alternative name for a low loader.
- **Tag trailer** means something specific to Midland — see 4.2, this is the worst trap on the list.

### 3.4 Tow and Go — a commercial distinction with no visual signature

Midland's **Tow and Go** range uses frames sourced offshore with fit-out and finishing done in
their Australian factory, as distinct from custom-engineered builds they describe as 100%
Australian-made. Both are Midland products and both will be in the photo library.

Flagging this because the whole point of the tagging project is marketing search, and "Australian
made" is Midland's central marketing claim. A Tow and Go photo captioned as Australian-made would
be a claim Midland's own site contradicts. There is no way to tell from a photograph. Recommend
this stays out of the vision schema entirely and is resolved from the job card.

---

## 4. Do-not-use list (Q4)

### 4.1 Terminology table

Confidence and sources per row are in `sources.md`. "True synonym?" is the important column.

| Australian term | Term to avoid | True synonym? |
|---|---|---|
| **Tandem** (two-axle group) | **the four-letter US/legacy term** | Yes, but never use the other. See 4.3 |
| **Low Loader** / **Float** | Lowboy (US), Low-bed (Canada/South Africa) | Close. Midland call lowboy an American term for the same thing. Wikipedia's lowboy specifies *two* drops in deck height, so a strict lowboy is closer to a double drop deck than to every low loader |
| **Drop deck** | — | `Step deck` is a **true synonym in Australia**, per Midland. Not a US/AU split — both are used here |
| **Flat top** | Flatbed | Effectively yes. Midland's own copy uses "flatbed semi-trailer" and "Flatbed Trailers" in places, so it is not forbidden, just not their primary term. Prefer **flat top** |
| **Skel** / **Skeletal** | Container chassis (US), Skeleton trailer | Yes. Midland use "Skel", Barker use "Skeletals". Both AU. `container chassis` is US |
| **Curtainsider** | — | **Tautliner is a British brand name** (Boalloy, Congleton, 1969), not a US term. Both are in ordinary Australian use. Krueger brand theirs **Kurtainer**. Prefer `curtainsider` as the canonical value |
| **Coaming** | Combing (Midland's own misspelling) | Same thing. Also spelled "combing" by Midland on the drop deck and hay spec pages |
| **Mudguards** | Fenders (US) | Yes |
| **Landing legs** | Jacks, dollies (US) | Yes — and note **"dolly" in Australia means a converter dolly**, a separate towed unit. Using "dolly" for a landing leg would be actively confusing here |
| **Chequer plate** / **Checker plate** | — | Same thing. Also **floor plate** (BlueScope product name). Midland use both spellings |
| **Bisalloy** | Bissalloy, Bissaloy (both Midland misspellings) | Correct brand is **Bisalloy**, from Bisalloy Steels Pty Ltd. Not interchangeable with **Hardox** (SSAB, Sweden) as a *brand*, but visually identical — see 2.3 |
| **Ringfeder** | Ring Feder, Ring feeder (Midland's spellings) | Same coupling. Ringfeder is the brand |
| **Pintle hook** | Pintel hook (Midland's typo) | Same |
| **Jinker** / **Pole jinker** | — | Australian term, no US equivalent in common use. Midland sell them |
| **Dog trailer** | — | Australian. Distinct from a **pig trailer** (centre axle group) and a **tag trailer**. Not a US term at all |
| **Widener** / **Deck widener** | — | Australian. Midland's Drop Deck Widener |
| **Mezz deck** / **Mez deck** | Mezzanine deck | Same. Both spellings on Midland's steel spec page |
| **Gates** | — | Australian usage. Midland: top and bottom gate systems, hanging gates |
| **Headboard** | Bulkhead (US) | Broadly yes |
| **Rope rails** | — | Australian. Midland list them on flat tops |
| **Catwalk** | Walkway | Both used; not a US/AU split |

### 4.2 The worst trap: "tag trailer" means three different things

This is a bigger risk than the A/B one, because unlike A/B it is not widely known to be ambiguous.

1. **Midland's product.** A drawbar plant trailer, single/tandem/tri axle, fixed drawbar and hitch,
   no steering front axle group, load transferred onto the tow truck's rear axle, pintle hook or
   Bartlett ball, bi-fold ramps, hydraulic front leg, drop-down rear legs. Runs behind a rigid or
   body truck, never a prime mover. This is Midland's Tag Trailers page and it is one of their
   top-five products.
2. **The rear semi-trailer in a multi-combination.** Midland's own Steel Spec page offers "lead and
   tag trailers" for B-double or road train setups. Here "tag" means the *rear* unit — a
   completely different vehicle from meaning 1, on the same website.
3. **Midland's folder naming**, per the brief: `2. Tandem Axle Tag Trailer`. Almost certainly
   meaning 1, but it needs confirming rather than assuming.

A tagger that sees "tag trailer" in a filename and applies meaning 2 to a photo of meaning 1 will
mislabel the axle attribution *and* the configuration. Recommend `tag_trailer` in the schema be
renamed to something unambiguous — `plant_tag_trailer` or `drawbar_plant_trailer` — with `tag
trailer` kept only as a search alias, and that meaning 2 be captured by the separate
`combination_role` field proposed in 1.3.

### 4.3 On the two-axle term

The brief's standing example holds and is confirmed: **Tandem** is the correct Australian term and
the only one that should appear as a tag value. Midland's customer-facing copy uses Tandem
consistently — Tandem, Tri or Quad Axle configurations.

One finding that matters operationally, though. **Midland's own website image filenames use the
deprecated term.** The drop deck showcase page serves files named
`Bogie+Axle+Semi+Drop+Deck+Trailer.0.JPG` through `.000000.JPG`, sitting alongside
`Tri+Axle+Semi+Drop+Deck+Trailer.0.JPG` on the same page. So Midland's legacy asset naming and
their current copy disagree.

Implication for the 40,000 photographs: **the deprecated string is very likely present in the
existing filenames and folder names.** Treat it as an input alias that maps to `tandem`, and never
as an output value. Do not let it into the enum.

### 4.4 The A-trailer / B-trailer collision, resolved three ways

The brief found two positions. There are three, and Midland has published its own.

**Position 1 — coupling type (regulators and engineers).** An A-type coupling is drawbar-based and
transfers neither roll nor load; a B-type coupling is a fifth wheel or turntable and always
transfers load. On this reading a B-double contains no A-trailer at all — both units are B-type —
and trucksales states flatly that calling the lead trailer an A-trailer is wrong. BTT Engineering
takes the same line.

**Position 2 — position in the combination (the workshop floor).** The lead trailer is the
A-trailer, the rear is the B-trailer. And crucially, **the ATA itself uses this**: in the same
document that defines A-type and B-type couplings, the B-double table notes that trailers are
sometimes described as an A or lead trailer with a following B or semi-trailer. So this is not
folk usage the ATA disowns — the ATA prints both senses on adjacent pages.

**Position 3 — Midland's published position.** Midland have taken side 2 explicitly and recently.
Their August 2026 guide is titled with A-Trailer/B-Trailer roles and defines the A-trailer as the
lead and the B-trailer as the rear. Their B Double Combination page names build options as Flat Top
A and B Trailers, Flat Top A and Drop Deck B, and Drop Deck A and Drop Deck B. Their Hay Spec page
quotes tare separately for the B Trailer and the A Trailer. AAA Trailers in Perth advertise
curtainsiders in A-trailer and B-trailer formats too, so it is standard trade usage.

**And a fourth sense, on Midland's own site.** The B Double Trailers page says operators call them
B trailers whether it is a single unit or a full B-double set. So on midlandind.com.au "B trailer"
can mean the rear unit *or* either unit of a B-double.

**Recommendation.** Do not use `a_trailer` or `b_trailer` as enum values — there is no reading that
is safe. Use positional values that cannot be misread: `lead_trailer`, `rear_trailer`,
`middle_trailer`, `standalone_semi`, `converter_dolly`. Keep "A trailer" and "B trailer" as search
aliases pointing at `lead_trailer` and `rear_trailer` respectively, because that is what Midland's
sales and marketing people will type. Note in the tagger prompt that a B-triple has **two** lead
trailers — the ATA describes a B-triple as two A-or-lead trailers followed by a B or semi-trailer —
so `lead_trailer` needs to be non-unique.

---

## 5. Competitors (Q5)

### 5.1 Who they are

Market share, where I have it, is from RAV registration data for Q2 2025: Vawdrey led truck
trailers with 406 entries and 10.1% of approvals, Maxitrans second at 293 and 7.3%, Bruce Rock
Engineering third at 175 and 4.4%, Jamieson fourth at 158 and 3.9%, with other makes accounting
for 45.8%. IBISWorld names Freighter Group, Vawdrey Australia and CIMC Group Australia as the
largest firms in the industry.

**In the brief and confirmed:** Krueger, Vawdrey, MaxiTRANS/Freighter, Barker, Tefco, Haulmark,
Drake.

**Not in the brief, and they should be:**

- **Bruce Rock Engineering** (WA) — third by registrations, ahead of most of the brief's list
- **Jamieson** — fourth by registrations
- **CIMC** — named by IBISWorld as one of the three largest; Chinese-owned, Australian operation
- **O'Phee Trailers** — part of the Drake Group, so an O'Phee-badged trailer is a Drake product
- **FWR Australia** (QLD) — direct overlap with Midland's range: tag trailers, low loaders, drop
  decks, dog trailers, plus super tilts and side tippers
- **Maxi-CUBE** — a MaxiTRANS brand alongside Freighter
- Also appearing in the dealer market: Howard Porter, Lusty EMS, Hamelex White, Loughlin,
  Southern Cross, Tristar, Sureweld, Interstate Trailers, Tuff Trailers, Freightmaster,
  Bruce Rock, Stonestar, Steelbro, Hercules

### 5.2 On visual branding cues — the honest answer

**I could not find sourced, reliable livery or build cues for these manufacturers, and I am not
going to invent any.** Trailer liveries are the *operator's*, not the builder's — a Krueger skel
runs in the colours of whoever bought it. Chassis colour, curtain artwork and signage identify the
fleet, not the manufacturer.

What actually identifies a builder in a photograph:

1. **The builder's decal or plate**, typically on the headboard, the front bulkhead or the chassis
   rail near the front. This is the only general-purpose cue, it is text, and it is readable when
   the resolution allows. Recommend a `manufacturer_decal_visible` field plus a free-text
   `manufacturer_decal_text` — read it, never infer it.
2. **Brand-specific product names**, which are effectively decals with high information content:
   - **"Kurtainer"** is Krueger's own name for their curtainsider range. If that word is on the
     curtain, it is a Krueger.
   - **"Moving Floor"** is Barker's signature category and one of only four they list; a moving
     floor trailer in this library is far more likely Barker than Midland.
   - **"Super Tilt"** and the **AZMEB** side-tipper range are FWR's.
   - **"AB Triple"**, **"Super B-Double"**, **"Ultra Low Neck PBS"**, **"Triple Drop PBS"** are
     Krueger model names.
3. **Range vocabulary differences**, which are weak signals but real: Krueger and Midland both say
   "Skel"; Barker says "Skeletals". Barker and Midland both use "Open Tops" as a family name.

Recommendation for the costly-failure case the brief names — a competitor trailer published as
Midland's own work: **do not rely on the vision pass for this.** Add a
`manufacturer_confidence` field, default it to `unknown`, and only ever populate `midland` where a
Midland decal is actually legible or the photo's provenance establishes it. An unknown-manufacturer
tag that blocks publication is cheap; a wrong `midland` tag is the failure.

---

## 6. Could not confirm

Not skipped. These are the gaps, and several change what should be built.

1. **What "TFB" stands for in Midland's coaming styles.** It appears once, on the drop deck page,
   as one of three values alongside Flush and C-channel. No definition found anywhere, no visual
   description, no other manufacturer using it. **This needs to come from Midland's engineering or
   drawing office, not research.** Until it does, do not add `tfb` with a
   `visual_discriminator` — a tagger cannot be asked to identify something nobody can describe.

2. **Whether Midland's Tag Trailer is legally a pig trailer.** Midland's tag trailer guide lists a
   tri-axle group limit "not a pig trailer" and gives tag trailers a 1:1.3 tow mass ratio against
   1:1 for dog and pig. The ATA's own table has separate, lower axle limits for pig trailers. So
   the two categories are legally distinct, but Midland also sell a separate Pig Trailers product,
   and I could not find an NHVR definition that cleanly separates "tag" from "pig" on geometry.
   My axle-position inference in 1.4 rests on this gap. **Confirm internally before building the
   pig/dog/tag discriminator into a prompt.**

3. **"Type 3 road train."** The brief lists road train types 1/2/3. The NHVR fact sheet defines
   Type 1 (A-double) and Type 2 (A-triple) only, and Midland reference Type 1 and Type 2. I found
   no authoritative source for a Type 3. It may be a state-specific or informal category.
   Recommend not adding it until someone can cite it.

4. **Over-slung/under-slung in Australian heavy-trailer usage.** Every source I found was
   US-origin and light-trailer. I cannot confirm the terms are used the same way by Australian
   heavy trailer builders, and Midland's site never uses either word. The schema has the field,
   so someone put it there — worth asking where it came from.

5. **Aluminium decks at Midland.** The brief lists aluminium as a deck material. Midland reference
   removable **alloy ramps** and stainless steel accessories, but I found no Midland reference to
   an aluminium deck. Possibly the brief's list is generic rather than Midland-derived.

6. **Bissalloy vs Bissaloy vs Bisalloy — which does Midland intend?** They use "Bissaloy" on the
   drop deck page and "Bissalloy" on the low loader and steel spec pages. The brand is Bisalloy.
   All three should be aliases, but if any Midland-facing output ever displays the term, someone
   should decide which spelling is house style.

7. **Whether the schema's `float_or_low_loader` should be split.** Midland treat low loader,
   float, lowboy and drop deck widener as broadly the same family, but Wikipedia's lowboy
   definition (two deck drops) describes something closer to a double drop deck. Whether Midland's
   Low Loaders and their Drop Deck Widener are one body type or two is a question for their
   engineering, not the web.

8. **Competitor visual cues** (5.2). This is a genuine research failure, not a partial answer. The
   information may not exist in published form — it may be tacit knowledge held by Midland's
   sales team, which would make a short internal session with them more productive than more
   searching.

9. **A conflict on Midland's own site worth knowing about, though out of scope.** Their May 2026
   split-axle article gives tandem GML as 16.5 t and tri as 20 t; their August 2026 guides give
   17 t and 21 t, citing the 1 August 2026 HVNL changes. Both are on the live site. Mass limits
   are out of scope for this project, but it is a reminder that Midland's site carries stale
   figures alongside current ones — so if the tagging project ever pulls numbers from it, date the
   source.

10. **A note on `not_visible` vs `unknown`.** The brief says most fields accept both. Nothing I
    found tells me how the tagger should choose between them, and the distinction matters a lot for
    this project: `not_visible` means "the answer exists, the camera didn't capture it" and
    `unknown` means "I can't tell". Recommend defining that explicitly in the tagger prompt, because
    a model will otherwise use them interchangeably and you lose the ability to find photos worth
    re-shooting.
