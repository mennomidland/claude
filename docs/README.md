# Midland sales photo tagging

Tagging the sales photo library so marketing and sales can find images. Filenames are
mostly camera defaults and carry no meaning.

**Scope: `sites/SalesMarketingTeam/Shared Documents/Sales/1. Trailer Photos` only.**

## Read in this order

1. `findings/library-structure.md` — what is actually in the library, and why
   enumeration has to recurse
2. `routines/01-enumeration.md` — the free pass that builds the work queue. Runs first
3. `schema/trailer-photo-tags.schema.json` — the tag record (**v3**)
4. `routines/02-thursday-iteration.md` — how the schema gets frozen before any volume

`findings/domain-knowledge.md` records what the tagger has to understand about trailers
before it can read a photo of one -- combination geometry, the A/B naming trap, and why
the folder is only a hypothesis.

`findings/join-discovery.md` is parked: it records that photo folder job numbers join
exactly to the Manufacturing Job Cards, which is out of scope for now but cheap when
wanted.

## House vocabulary

A trailer with two axles is a **Tandem**. Never "bogie". Midland's own folders read
`2. Tandem Axle Tag Trailer`. A general model reaches for "bogie" constantly on
Australian trailer photos, so the prohibition is stated explicitly in every prompt and
the word appears in no enum.

## Three rules the schema exists to enforce

- **Never ask a model for what the path already says.** Product category, variant, axle
  configuration, customer, build date and job number are all in the folder path. They
  are parsed, not inferred. **But the path is a hypothesis, not truth** — Midland confirm
  photos are sometimes filed in the wrong folder, so where vision and path disagree the
  disagreement is the finding. That is what the `audit` block is for, and why the vision
  pass is run **blind** to the path. See `findings/domain-knowledge.md`.
- **Every field accepts `unknown`.** A model forced to always emit a value invents one,
  and invented specifications are what made the first attempt read as garbage.
- **Tag what the photo shows, not just what the trailer is** (added in v3). The first two
  rules produced a schema that classified trailers accurately and left the library
  unsearchable: a close shot of the auto twist lock control panel came back as
  `subject:partial-view-cropped, shot:side-elevation, body:skeletal` — every word of it
  either derivable from the folder name or useless to a person looking for a photo of the
  twist lock system. `components_visible`, `features_present` and `demonstrates` carry
  what the frame actually contains and what it is good for.

## Two tag namespaces

Positive tags and absence tags go to **different namespaces**, written separately:

| Namespace | Holds | Read by |
|---|---|---|
| `trailer-photo:vision` | what the photo shows | people searching |
| `trailer-photo:state` | every `unknown` / `not_visible` | prompt evaluation |

On a real frame the absence tags were **43% of the bag** — worthless to a searcher, but
they are how you tell a badly defined field (always `unknown`) from a guessed one (never
`unknown`), and leaving the model free to say "cannot tell" is what stops it inventing
specifications. Keep them; keep them out of the search index.
