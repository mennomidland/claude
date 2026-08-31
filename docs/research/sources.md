# Sources

Ordered by the brief's authority hierarchy: Midland's own site → ATA / NHVR / state road authority
→ Australian manufacturer sites → Australian trade press → general web. **US-origin sources are
flagged explicitly**, including where I think the content transfers.

---

## Tier 1 — Midland's own site (highest authority)

### 1a. The `/news/` guides — the find of this research

These were not in the brief's scope and they are the best source available. Published Feb–Aug 2026,
authored by William Siebler and Sasha Kluss, and written at engineering rather than marketing depth.
**Recommend reading all of them before finalising the schema.**

| URL | Supported |
|---|---|
| `/news/64wci6egusrx2na3ez5krs7iw3ln8c` — *What is a B-Double? Configuration, Mass Limits, and A-Trailer/B-Trailer Roles* | THE key source. Midland's published position on A-trailer = lead / B-trailer = rear (findings 4.4). The axle-attribution rule — rear trailer has no front axle group and rests on the lead's rear fifth wheel (findings 1.1). The rear-fifth-wheel single-trailer discriminator (1.3). B-double vs road train coupling distinction (1.2) |
| `/news/ukuzxbf43uv5zr7ehu7aj7z2wb37xz` — *What is a Tag Trailer?* | Midland's definition of a tag trailer: fixed drawbar and hitch, no steering front axle group, load transferred to the tow truck's rear axle, rigid/body truck only. Beavertail ramps. Underpins the three-way "tag trailer" collision (4.2) |
| `/news/what-is-a-dog-trailer-your-complete-australian-guide` | Dog trailer geometry — front axle group on a steering turntable, group at each end. Dog vs tag vs semi comparison. Type 2 road train when a second dog is added |
| `/news/rdkh657ggdd99n7z6a4gi94vgt449b` — *What is a Super Dog Trailer?* | Super dog = single front group + tandem rear = 3 axles. Standard dog = tandem/tandem = 4. Quad dog. All three absent from the schema (1.5) |
| `/news/what-is-a-drop-deck-trailer-your-complete-australian-guide` | Deck heights: top deck ~1,500mm, drop deck ~1,020mm, step ~480mm, double drop well ~700mm on 19.5" axles. Well lengths 12/13.5/14.5m. Low loader = float. The most numerically precise visual discriminators in the whole set (2.3, body_type proposals) |
| `/news/va06vw06bm2dycqbl0bz58tjx8wycv` — *What is a Skeletal Trailer?* | Twist lock positions matching ISO corner castings. Container lengths 20ft 6.06m / 40ft 12.19m / 45ft 13.72m HC. Retractable skel adjusting lock positions (2.5) |
| `/news/pbs-split-axle-semi-trailers-increase-payload-without-increasing-tare` | Split axle requires ≥2.5m spacing — the basis for the split_axle_group visual discriminator (2.7). Also the source of the mass-figure conflict noted in findings 6.9 |
| `/news/optimised-a-double-skel-trailers-for-dg-iso-containers-midland-trailers` | Ball race as a lower-profile alternative to a dolly's fifth wheel (coupling_type clarification). Perimeter frame construction. A-double vs B-double roll stability |
| `/news/airbag-vs-spring-suspension-on-truck-trailers` | Confirms the commercial importance of the suspension choice and that airbag is load-sharing (an HML requirement). **Gives no visual test** — which is itself the finding behind the medium confidence rating in 2.1 |

Also present and not read in detail: *What is a Semi Trailer?*, *What is a Flat Top Trailer?*,
*What is a Low Loader Trailer?*, *What is a Heavy Haulage Trailer?*, *PBS and Mass Limit Changes 2026*,
*What Shortens a Trailer's Service Life?*. The flat top and low loader guides are the obvious next reads.

### 1b. Product showcase pages — the option vocabulary

All fetched 31 Aug 2026. These are where Q3's exact wording comes from, and where Midland's internal
spelling inconsistencies are visible.

| URL | Supported |
|---|---|
| `/showcase/drop-deck-trailers` | Richest single option list. Air or Spring Suspension; Lift and Steer axles; Checker Plate or **Bissaloy**; **Combing Styles: Flush, TFB or C-channel**; up to 3-way container pins; outriggers; single/bi-fold/H.D ramps; flip-over front ramps; skid plate; ring feeder; top decks. **Also the drop deck = step deck = semi drop deck FAQ.** **Also the legacy `Bogie+Axle+...JPG` image filenames** (findings 4.3) |
| `/showcase/tri-axle-low-loaders`, `/showcase/quad-axle-low-loaders`, `/showcase/low-loader-trailers` | Deck widening 2490→4000mm; Goose Neck or Step Deck; **Bissalloy**/Hardox 6-8mm; fixed or bi-fold rear; the full options-and-upgrades list |
| `/showcase/steel-spec-trailers` | **"lead and tag trailers for B-Double or Road Train setups"** — the second meaning of "tag trailer" (4.2). Mez Deck / Mezz Decks (both spellings); straight or stepped bolsters; Webrail / Web rail; folding top and bottom gates; Split Axle Group with Steer Axle |
| `/showcase/b-double-combination-trailers` | Build options named as **"Flat Top A and B Trailers"**, **"Flat Top A and Drop Deck B"**, **"Drop Deck A and Drop Deck B"** — Midland's A/B usage in product naming (4.4) |
| `/showcase/b-double-trailers` | The **fourth** sense of "B trailer" — operators calling any unit of a B-double set a B trailer (4.4) |
| `/showcase/hay-spec-combination-trailers` | Tare quoted separately for **"B Trailer"** and **"A Trailer"** (4.4). Suspension brands BPW, Hendrickson, K-Hitch. Jost landing legs. Winch track, load binders on track. 4 or 5 inch **Combing** options |
| `/showcase/dog-trailers` | Coaming Rails: Profile or standard. Ring Feder, Pintle or Bartlett Ball hitches. Dual hydraulic ramp spools. 2, 3 or 4 axles, step deck or flat top |
| `/showcase/tag-trailers` | Hydraulic front leg; drop-down rear legs; **"Pintel Hook"** (their typo) or Bartlett Ball; single or bi-fold ramps |
| `/showcase/pig-trailers` | Confirms Midland sell pig trailers — the schema's most significant configuration gap |
| `/showcase/container-skel-trailers`, `/showcase/retractable-skel-trailers` | Up to 4-way container pins with optional side loader pads; 10-tonne roller skate design; locking pins; airbag only on retractables |
| `/showcase/flat-top-trailers` | **"Hardox / checker or Flat plate decking with flush or raised coaming"** — three independent choices in one sentence, the basis for splitting `floor_type` |
| `/showcase/flat-top-extendable-trailers` | 350 Grade Mild Steel and 750 Q&T; Bolsters and Webrail Applications |
| `/showcase/tanker-trailers` | Bulk Tankers or Water Cart setup — the body_type gap |
| `/showcase/skip-bin-transfer-trailers` | Up to 6 axles (the real upper bound for `axle_count`); hydraulic bin locking |
| `/showcase/pole-jinker-trailers`, `/showcase/beekeeper-trailers` | Jinker and beekeeper vocabulary; adjustable load bolsters |
| `/lowboy-trailers` | **"A Lowboy Trailer is a term that originated in America"** and is the same as a Drop Deck Widener and their Low Loaders (3.3, 4.1) |
| `/showcase`, `/faqs`, `/what-we-do`, `/custom-trailers`, `/heavy-haulage-trailers` | Full product range list for Q3 (3.1) |

**Caveat on Tier 1:** Midland's site is marketing copy with SEO padding, and it contradicts itself
on spelling (coaming/combing, checker/chequer, Bissaloy/Bissalloy, Ring Feder/feeder, Mez/Mezz,
airbag/air bag) and on mass figures (findings 6.9). It is authoritative on *their vocabulary and
their product range*, which is what Q3 asked for. It is not authoritative on numbers.

---

## Tier 2 — ATA, NHVR, state road authority

| Source | Supported | Authority |
|---|---|---|
| **ATA Technical Advisory Procedure, *Description of truck configurations*, 1st ed. Sept 2016** — `truck.net.au/sites/default/files/TAPs - description of truck configuration September 2016.pdf` | The single most valuable non-Midland source. A-type vs B-type coupling definitions. The full **AnTnn configuration coding** (1.7). Pig = one group in the centre; dog = a group at each end (1.4). Dog assembly usually being a semi plus a converter dolly (1.6). B-triple = two lead trailers (4.4). Axle count ranges per trailer type. **And the ATA's own use of "A or lead trailer" in the B-double table — which is what makes the A/B question a genuine three-way rather than ATA-vs-floor** | Highest non-Midland. Industry body, peer-reviewed, named engineers. **Note: 1st edition 2016, review was expected by Sept 2020 — check for a 2nd edition before citing externally** |
| **NHVR, *Classes of heavy vehicles in the HVNL*** — `nhvr.gov.au/files/201409-0155-classes-of-heavy-vehicles.pdf` | The statutory B-double definition (two semitrailers, second mounted on a fifth wheel on the first). A-double = Type 1 road train, A-triple = Type 2, AB-triple. Road train excluding converter dollies from the trailer count (Rule 3, 1.1). Gooseneck dolly. Vehicle carrier class | Regulator, but **dated Sept 2014**, and NHVR's own current pages warn content may be outdated after the 1 Aug 2026 HVNL changes. The *shapes* are unchanged; do not use it for mass or dimension figures |
| **NHVR, quad-axle group vehicle combinations** — `nhvr.gov.au/road-access/performance-based-standards/quad-axle-group-vehicle-combinations` | Steerable rear axle requiring ≥±12° articulation and a centring mechanism; lift axles complying with ADR 43/04 (2.8) | Regulator, current |
| **NHVR, PBS vehicle approval — combination matrix** — `nhvr.gov.au/road-access/performance-based-standards/manage-a-pbs-vehicle-approval/pbs-va-explained-combination-matrix` | Trailer sets applying to A-double, B-double and road train, and to truck-and-dog where the dog consists of a dolly plus a semitrailer — corroborates 1.6 | Regulator, current |
| **NHVR, vehicle charts and fact sheets** / **PBS vehicle configurations chart** | Context on the range of approved PBS configurations. Carries the 1 Aug 2026 currency warning | Regulator |
| **Qld TMR, *Route Assessment for MCV and PBS Vehicles* guideline** | PBS B-doubles typically fitted with steerable trailer axles; B-triple classed as Type 1 road train; PBS Level 2B up to 30m; quad-axle B-doubles | State road authority |

---

## Tier 3 — Australian manufacturers and engineering consultancies

| Source | Supported | Notes |
|---|---|---|
| `krueger.com.au` | Q5. **"Kurtainer"** as Krueger's own curtainsider brand name — a genuine photo-identifiable cue. Model names: Super B-Double, Ultra Low Profile, Ultra Low Neck PBS, Triple Drop PBS, A-Double Lock, Roll Back, Mezz Deck, Lightweight Skel. Uses "Skel" like Midland | Direct competitor, named in the brief as appearing in the library |
| `barkertrailers.com.au` | Q5. Product categories are **Moving Floors, Curtainsiders, Open Tops, Skeletals** — so `moving_floor` is a Barker signature and "Skeletals" is their word where Midland say "Skel". Both use "Open Tops" as a family name | Direct competitor |
| `fwr.com.au` | Q5. Closest range overlap with Midland: Tag Trailers, Low Loaders, Drop Decks, Dog Trailers, plus **Super Tilt**, **Side Tippers**, **AZMEB** range, Car Carrier. Not in the brief's competitor list and should be | Direct competitor |
| `bttengineering.com.au/pbs-certification/combinations` and `/a-doubles-combination` | AB-triple as one A-type plus one B-type coupling. A-double defined by its drawbar coupling. 3A/4A/5A/6A dog nomenclature. **"Pocket road train" for a 2-2-2 A-double** — the conflict against the ATA's use of "pocket" (1.8) | PBS certification consultancy; engineering authority, commercial site |
| `thedrakegroup.com.au/drake-trailers-news/b-double-truck/` | Turntable at the end of the lead semi allowing coupling without a converter dolly. Confirms O'Phee Trailers is part of the Drake Group (5.1) | Competitor; corroborating only |
| `aaatrailers.com.au/curtainsider-trailers-perth` | Curtainsiders advertised in **A-trailer and B-trailer formats** — independent evidence that Midland's A/B usage is standard trade usage, not a Midland quirk (4.4). Also straight deck vs drop deck curtainsiders, K-Hitch airbag | Australian manufacturer/dealer |
| `vawdrey.com.au`, `thedrakegroup.com.au`, `freighter.com.au`, `cimc.com.au`, `tufftrailers.com.au`, `sloanebuilt.com.au`, `onlytrailers.com.au` | **Attempted and returned no usable content** — JavaScript-rendered single-page sites that curl cannot read. Listed here so the gap is visible rather than silent. A browser-based pass would recover these | Gap, not a finding |

---

## Tier 4 — Australian trade press and market data

| Source | Supported | Notes |
|---|---|---|
| `trucksales.com.au/editorial/details/do-you-know-your-a-from-your-b-118045/` | Position 1 in the A/B question: an A-type trailer is drawbar-coupled by worldwide engineering and legislative convention, therefore a B-double **cannot** have an A-trailer, and calling the lead trailer an A-trailer is wrong. Also B-triple, AB-triple, ABB-quad, BAB-quad, AB-quad | Australian trade press. Editorial, not standards — but it states the engineering convention clearly and matches the ATA's coupling definitions |
| `truckdealers.com.au/editorial/the-abcs-of-trailers-and-rig-configuration/` | Same position, independently. Dollies licensed as separate units | Australian trade press |
| `samove.raa.com.au/whats-a-b-double-truck/` | The A-double mechanism: drawbar to a converter dolly fitted with a fifth wheel/turntable, on which the rear trailer's front rests with no front wheels of its own — the clearest plain-language statement of Rule 3 (1.1) | RAA motoring body. Consumer-level but accurate and Australian |
| `retainmedia.com.au/market-reports/trailer-market/q2-2025-truck-trailer-small-trailer-market-report/` | Q5 market share from RAV registration data: Vawdrey 406 / 10.1%, Maxitrans 293 / 7.3%, **Bruce Rock Engineering 175 / 4.4%**, **Jamieson 158 / 3.9%**, other makes 45.8%. Source of the two competitors missing from the brief | Trade market report on registration data. The most defensible market figures found |
| `ibisworld.com/australia/industry/freight-trailer-manufacturing/5096/` | Freighter Group, Vawdrey Australia and CIMC Group Australia named as the largest firms | Industry research; summary page only, full report paywalled |
| `truckdealers.com.au/buy/trailers/` | The long tail of trailer makes appearing in the Australian dealer market (5.1) | Dealer inventory; useful as a name list, no analysis |
| `tegral.com.au`, `roadlinxtransport.com.au/blog/trailer-types-guide`, `spartanquip.com.au`, `trgroupau.com` | Q4 corroboration: tautliner = curtainsider; drop deck = step deck; flat top = flatbed | Australian operators/hire companies. Marketing content — used only where they corroborate a Tier 1 or 2 source |

---

## Tier 5 — General web, and the US-origin flags

### Materials

| Source | Supported | Notes |
|---|---|---|
| `industry.gov.au/.../037-verificationreport-australianindustry-bisalloysteelsptyltd.pdf` | **Bisalloy Steels Pty Ltd is Australian**; product line Bisplate, grades BIS320–BIS600; **Hardox is SSAB, Sweden**. The definitive spelling authority (2.3) | Australian Government Anti-Dumping Commission. Highest-authority source for this specific point |
| `blog.thepipingmart.com/metals/hardox-vs-bisalloy-whats-the-difference/` and `artizono.com/hardox-vs-bisalloy-...` | Both are abrasion-resistant quenched-and-tempered plate — the basis for the finding that they are **visually indistinguishable** (2.3) | General web, non-Australian. Corroborating only; the substantive point rests on the government source above |
| `steelprofilecutting.com.au/blog/grades-of-steel-plate/` | Checker plate = hot-rolled with a raised checkered surface on one side; typical use floorplate; "Bis" as the trade shorthand | Australian steel supplier |
| `australiansteel.com.au/product/wear-plate/bisalloy-steel/` | Bisalloy grade range as stocked in Melbourne | Australian supplier |

### Suspension — **all US-origin, all flagged**

These four are the entire evidential basis for the over-slung/under-slung answer, and **all of them
are American and about light trailers, not Australian heavy trailers**. This is why findings 2.2
recommends the tagger never populate `suspension_mount`, and why it is item 4 in the could-not-confirm list.

| Source | Supported | Flag |
|---|---|---|
| `mechanicalelements.com/overslung-underslung-trailer-springs/` | Over-slung = spring above the axle beam, under-slung = below; effect on deck height | **US-origin. Light trailer / DIY** |
| `blueswiftaxles.com/the-pros-and-cons-of-overslung-and-underslung-axles/` | Same definitions | **US-origin.** Self-describes as "America's Top Trailer Axle and Components Store" |
| `rv.com/archive/suspension-basics/` | Same definitions | **US-origin. Recreational vehicles**, not heavy trailers |
| `loadsensescales.com/types-of-mechanical-spring-suspension-for-trucks-and-trailers/` | Over/under-slung deck height difference; drop axles using under-slung springs | **US-origin** |
| `patents.justia.com/patent/9050875` | The key limitation: on an air-bag trailing-arm suspension the over/under-slung distinction becomes the axle seat position on the beam — **not externally visible** (2.2) | US patent. Technical and reliable on mechanism, but a patent, not a standard |
| `blog.premiertrailerleasing.com/airride` | The leaf-spring pack description used in the air-bag-vs-spring visual discriminator: spring pack bow, hangers, axle U-bolted beneath the low point (2.1) | **US-origin.** Components are the same globally and Midland specify global brands (BPW, Hendrickson, K-Hitch), so I judge it transfers — but the brief says flag it, so: flagged |

### Containers

| Source | Supported | Notes |
|---|---|---|
| `genrontrucktrailer.com/40ft-skeleton-trailer-dimensions/` | Twist lock counts 4 to 12; locks at both 20ft and 40ft intervals for dual capability; retractable mid locks folding down for a single 40ft; ISO 1161 corner fittings, ISO 3874 securing (2.5) | **Non-Australian (Chinese manufacturer).** ISO standards are international so the geometry transfers; used because Midland's own skel guide covers the principle but not the lock counts |
| `hz-containers.com/en/glossary/dimensions-of-twist-lock-locks-on-the-trailer/`, `pandamech.com`, `lionkar.com/skeletal-trailer-dimensions/` | Corroboration on lock spacing and the caution that nominal 20/40/45ft descriptions don't determine actual dimensions | **Non-Australian.** Corroborating only |
| `en.wikipedia.org/wiki/Twistlock` | Background on twist lock origin and the 40ft stacking rule | General reference |

### Terminology

| Source | Supported | Notes |
|---|---|---|
| `en.wikipedia.org/wiki/Lowboy_(trailer)` | **lowboy (US) = low-loader (British) = low-bed (Canada/South Africa) = float (Australia)** — direct support for the Q4 row (4.1). Also the strict lowboy definition of *two* deck drops, which is the basis for the caveat that a lowboy is closer to a double drop deck than to every low loader | General reference, but it independently corroborates Midland's own statement that lowboy is an American term |
| `en.wikipedia.org/wiki/Tautliner` | **Tautliner is a trade name — Boalloy of Congleton, Cheshire, England.** So it is a *British brand*, not a US term, which corrects the framing in the brief's Q4 (4.1) | General reference; corroborated by three Australian trade sources |
| `en.wiktionary.org/wiki/B-double` | The load-transfer distinction: a B-trailer shares its rear wheelset with the following semi-trailer, while an A dolly-converter places no significant load or roll force into the leading trailer. Also B-doubles originating as Canadian B-trains | General reference. Useful mechanism explanation; **not cited for any load-bearing claim** |
| `driverknowledgetests.com`, `mocktheorytest.com` | Curtainsider construction: headboard, roof rails, curtain straps to a rope rail, mezzanine/"mezz" floors | General web, driver education. Corroborating only |

---

## Source trace — claims that do NOT have a source

Per the anti-fabrication standard, these are flagged as blockers rather than presented as findings:

1. **Tag trailer axle position** (findings 1.4, `axle_group_layout` proposal) — the coupling test is
   sourced to Midland; the *rearward axle group* is my inference from their load-transfer mechanics.
   **Not sourced. Confirm with Midland engineering.**
2. **TFB coaming** — appears once on Midland's site, defined nowhere. **No source exists that I could find.**
3. **Type 3 road train** — asserted in the brief, **no source found**.
4. **Timber deck at Midland** — in the brief, **no Midland source found**.
5. **Aluminium deck at Midland** — in the brief, **no Midland source found** (alloy *ramps* are sourced).
6. **Extendable/widener retracted appearance** (2.6) — assembled from mechanism descriptions, **no
   photo-annotated source**. Medium confidence, flagged in the findings.
7. **Competitor livery and build cues** (5.2) — **no source found for any manufacturer.** Reported as
   a research failure with a recommended alternative (decal text + confidence field), not filled with
   plausible-sounding guesses.
8. **Over-slung/under-slung in Australian heavy-trailer usage** — sourced only from US light-trailer
   material, as flagged above.
